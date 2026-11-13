import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { ServiceHealth } from "./chaos-api.ts";
import { type BusRecord, initialState, type LiveState, reduce } from "./live.ts";
import { incidentStats, incidentStatus, latencyLimit, parsePolicy, parseServices, serviceSentence, serviceStatus } from "./overview.ts";

const policyText = readFileSync(new URL("../../config/policy.yaml", import.meta.url), "utf8");
const servicesText = readFileSync(new URL("../../config/services.yaml", import.meta.url), "utf8");
const policy = parsePolicy(policyText);

const health = (over: Partial<ServiceHealth> = {}): ServiceHealth => ({
  err_ratio: 0, p95_ms: 10, baseline_p95_ms: 10, breaching: false, bad_pods: 0, unhealthy: false, ...over,
});

test("reads the real policy and service list", () => {
  assert.deepEqual(policy, { errThreshold: 0.05, latencyMultiplier: 2, latencyFloorMs: 100, maxAgeS: 1200 });
  const services = parseServices(servicesText);
  assert.deepEqual(services.payment, { kind: "stateless", critical: true, actable: true });
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
  assert.deepEqual(st, { total: 5, open: 1, resolved: 2, escalated: 1, handedOff: 0, lost: 1, medianFixS: 150 });
  assert.equal(incidentStatus(s.incidents.d, 4100, 1200), "lost");
  assert.equal(incidentStatus(s.incidents.d, 4100, null), "open");
});
