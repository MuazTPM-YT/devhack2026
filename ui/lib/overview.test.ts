import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { ServiceHealth } from "./chaos-api.ts";
import { type BusRecord, initialState, type LiveState, reduce } from "./live.ts";
import { incidentStats, incidentStatus, latencyLimit, parsePolicy, parseServices, serviceSentence, serviceStatus, verdict } from "./overview.ts";

const policyText = readFileSync(new URL("../../config/policy.yaml", import.meta.url), "utf8");
const servicesText = readFileSync(new URL("../../config/services.yaml", import.meta.url), "utf8");
const policy = parsePolicy(policyText);

const health = (over: Partial<ServiceHealth> = {}): ServiceHealth => ({
  err_ratio: 0, p95_ms: 10, baseline_p95_ms: 10, breaching: false, bad_pods: 0, unhealthy: false, ...over,
});

test("reads the real policy and service list", () => {
  assert.deepEqual(policy, { errThreshold: 0.05, latencyMultiplier: 2, latencyFloorMs: 100, maxAgeS: 2400 });
  const services = parseServices(servicesText);
  assert.deepEqual(services.payment, { kind: "stateless", critical: true, actable: true, protected: false });
  assert.equal(Object.keys(services).length, 11);
});

test("latency limit is the larger of the multiplier and the floor", () => {
  assert.equal(latencyLimit(4.8, policy), 104.8);
  assert.equal(latencyLimit(300, policy), 600);
  assert.equal(latencyLimit(null, policy), null);
});

test("service status and sentence follow the observer's flags", () => {
  assert.equal(serviceStatus(undefined), "nodata");
  assert.equal(serviceStatus(health({ err_ratio: null, p95_ms: null })), "nodata");
  assert.equal(serviceStatus(health({ breaching: true })), "breaching");
  assert.equal(serviceStatus(health({ breaching: true, unhealthy: true })), "unhealthy");
  assert.equal(serviceSentence(health(), policy), "Inside its error and latency baselines.");
  assert.equal(serviceSentence(health({ err_ratio: 0.43, bad_pods: 1 }), policy),
    "Errors 43.0%, over the 5% line; 1 pod not ready.");
});

function run(...recs: [string, string, number, Record<string, unknown>?][]): LiveState {
  return recs.reduce<LiveState>((s, [type, id, ts, payload], i) =>
    reduce(s, { seq: i + 1, ts, event: { type, incident_id: id, payload: payload ?? {} } } as BusRecord), initialState);
}

test("incident stats count outcomes, lost incidents and median fix time", () => {
  const card = { status: "x", text: "x", evidence_ids: [] };
  const s = run(
    ["incident_opened", "a", 0], ["incident_resolved", "a", 100, { card }],
    ["incident_opened", "b", 10], ["incident_resolved", "b", 210, { card }],
    ["incident_opened", "c", 20], ["escalated", "c", 50, { card }],
    ["incident_opened", "d", 30],
    ["incident_opened", "e", 4000],
  );
  const st = incidentStats(s, 4100, 1200);
  assert.deepEqual(st, { total: 5, open: 1, resolved: 2, verified: 0, escalated: 1, handedOff: 0, lost: 1, medianFixS: 150 });
  assert.equal(incidentStatus(s.incidents.d, 4100, 1200), "lost");
  assert.equal(incidentStatus(s.incidents.d, 4100, null), "open");
});

test("unknown telemetry never reads as healthy", () => {
  // blind: the observer is serving old numbers, however good they look
  assert.equal(serviceStatus(health(), true), "unknown");
  assert.equal(serviceStatus(health({ unhealthy: true }), true), "unknown");
  assert.equal(serviceSentence(health(), policy, true), "Monitoring unavailable; health unknown.");
  assert.equal(serviceSentence(undefined, policy), "No reading for this service; health unknown.");
  assert.equal(serviceSentence(health({ err_ratio: null, p95_ms: null }), policy), "No requests measured in the last window; health not proven.");
  // the observer says breaching but our copy of the limits shows nothing over: still not "inside baselines"
  assert.equal(serviceSentence(health({ breaching: true }), policy), "Over a limit the observer measured.");
});

test("resolved is not the same as fixed", () => {
  const closed = (status: string, held?: boolean) => run(
    ["incident_opened", "v", 0], ["incident_resolved", "v", 90, { card: { status, text: "t", evidence_ids: [] }, prediction_held: held }],
  ).incidents.v;
  assert.equal(verdict(closed("FIXED", true)), "verified");
  assert.equal(verdict(closed("RECOVERED, FIX NOT PROVEN", false)), "unproven");
  assert.equal(verdict(closed("MITIGATED, NOT FIXED", true)), "mitigated");
  assert.equal(verdict(closed("resolved")), "unproven");
  assert.equal(verdict(run(["incident_opened", "o", 0]).incidents.o), null);
  const stats = incidentStats(run(
    ["incident_opened", "a", 0], ["incident_resolved", "a", 90, { card: { status: "FIXED", text: "t", evidence_ids: [] }, prediction_held: true }],
    ["incident_opened", "b", 5], ["incident_resolved", "b", 95, { card: { status: "RECOVERED, FIX NOT PROVEN", text: "t", evidence_ids: [] }, prediction_held: false }],
  ), 100, 1200);
  assert.deepEqual([stats.resolved, stats.verified], [2, 1]);
});

test("a protected data store is approval-only, not watch-only", () => {
  const parsed = parseServices(servicesText);
  assert.deepEqual([parsed["valkey-cart"].protected, parsed["valkey-cart"].actable], [true, false]);
  assert.deepEqual([parsed.accounting.protected, parsed.accounting.actable], [false, false]);
  assert.equal(parsed.payment.protected, false);
});
