import assert from "node:assert/strict";
import { test } from "node:test";

import { describe, failedAt, flowAt, pathOf, rows, stageTimes } from "./flow.ts";
import type { IncidentEvent } from "./live.ts";

let seq = 0;
function ev(type: string, payload: Record<string, unknown> = {}): IncidentEvent {
  seq += 1;
  return { seq, ts: 100 + seq, type, payload };
}

test("events travel the real service path", () => {
  assert.deepEqual(pathOf(ev("incident_opened"), null), ["shop", "observer", "brain"]);
  assert.deepEqual(pathOf(ev("llm_called", { model: "m" }), null), ["brain", "llm", "brain"]);
  assert.deepEqual(pathOf(ev("llm_called", { cached: true }), null), ["brain"]);
  assert.deepEqual(pathOf(ev("action_executed"), null), ["gateway", "k8s"]);
  assert.deepEqual(pathOf(ev("verify_tick"), null), ["observer", "verifier"]);
  assert.deepEqual(pathOf(ev("checklist_step", { name: "dry_run" }), null), ["gateway", "k8s", "gateway"]);
});

test("first gate comes from the brain, later gates stay in the gateway", () => {
  const first = ev("checklist_step", { name: "schema", passed: true });
  assert.deepEqual(pathOf(first, ev("diagnosis_ready")), ["brain", "gateway"]);
  assert.deepEqual(pathOf(ev("checklist_step", { name: "policy" }), first), ["gateway"]);
});

test("terminal event starts where the last one ended", () => {
  assert.deepEqual(pathOf(ev("escalated"), ev("rule_matched")), ["brain", "gateway", "notifier"]);
  assert.deepEqual(pathOf(ev("incident_resolved"), ev("harm_check")), ["gateway", "notifier"]);
  assert.deepEqual(pathOf(ev("escalated"), null), ["gateway", "notifier"]);
});

test("a gate that asks a human is not a fault, a refused gate is", () => {
  const ask = ev("checklist_step", { name: "net_benefit", passed: false, reason: "costly" });
  assert.equal(failedAt(ask, ev("approval_requested")), null);
  assert.equal(describe(ask, ev("approval_requested")).tone, "warn");
  const refused = ev("checklist_step", { name: "policy", passed: false, reason: "payment is protected" });
  assert.equal(failedAt(refused, ev("escalated")), "gateway");
  assert.equal(describe(refused).tone, "bad");
  assert.equal(failedAt(ev("checklist_step", { name: "trust_gate", passed: false })), null);
});

test("failures land on the component that failed", () => {
  assert.equal(failedAt(ev("llm_called", { error: "deadline_exceeded" })), "llm");
  assert.equal(failedAt(ev("blocked", { reason: "API server refused" })), "k8s");
  assert.equal(failedAt(ev("early_abort")), "verifier");
  assert.equal(failedAt(ev("harm_check", { clean: false })), "verifier");
  assert.equal(failedAt(ev("harm_check", { clean: true })), null);
});

test("sentences read the payload and survive junk", () => {
  assert.equal(describe(ev("culprit_found", { culprit: "payment", from_traces: true, victims: ["checkout"] })).detail,
    "from error traces · victims checkout");
  assert.equal(describe(ev("llm_called", { error: "deadline_exceeded" })).title, "Model call failed");
  assert.equal(describe(ev("llm_called", { model: "glm", attempt: 1, usage: { total_tokens: 900 } })).detail,
    "glm · attempt 1 · 900 tokens");
  assert.equal(describe(ev("rule_matched", { pattern: "unknown", tools: [] })).tone, "warn");
  assert.equal(describe(ev("culprit_found", { culprit: 5, victims: "x" })).title, "No culprit found");
  assert.equal(describe(ev("something_new")).title, "something new");
});

test("flowAt marks done, active and failed components and counts edges", () => {
  const events = [
    ev("incident_opened"), ev("rule_matched"), ev("llm_called", { error: "deadline_exceeded" }),
    ev("checklist_step", { name: "schema", passed: true }), ev("action_executed", { tool: "rollback_deploy" }),
  ];
  const open = flowAt(events, events.length - 1, true);
  assert.equal(open.nodes.llm.state, "failed");
  assert.equal(open.nodes.gateway.state, "active");
  assert.equal(open.nodes.k8s.state, "active");
  assert.equal(open.nodes.observer.state, "done");
  assert.equal(open.nodes.verifier.state, "idle");
  assert.equal(open.edges["brain>llm"], 1);
  assert.equal(open.edges["llm>brain"], 1);
  assert.deepEqual(open.path, ["gateway", "k8s"]);
  assert.equal(open.nodes.k8s.last?.title, "Executed rollback_deploy on ?");
  assert.equal(open.nodes.llm.last?.title, "Model call failed");
  assert.equal(open.nodes.llm.count, 1);
  assert.equal(open.nodes.brain.count, 3); // opened, rule matched, model answer back; not the gate it sent

  const past = flowAt(events, 0, true);
  assert.equal(past.nodes.brain.state, "active");
  assert.equal(past.nodes.gateway.state, "idle");
  assert.equal(past.focus?.type, "incident_opened");

  const closed = flowAt(events, events.length - 1, false);
  assert.equal(closed.nodes.gateway.state, "done");
  assert.deepEqual(flowAt([], 0, true).path, []);
});

test("consecutive verify ticks collapse into one row", () => {
  const events = [ev("action_executed"), ev("verify_tick", { severity: 9 }), ev("verify_tick", { severity: 4 }),
    ev("verify_tick", { severity: 0, recovered: true }), ev("harm_check", { clean: true }), ev("verify_tick")];
  const r = rows(events);
  assert.deepEqual(r.map((x) => x.kind), ["event", "ticks", "event", "event"]);
  const ticks = r[1];
  assert.ok(ticks.kind === "ticks" && ticks.count === 3 && ticks.first.payload.severity === 9 && ticks.index === 3);
});

test("stage times run from a stage's first event to the next stage", () => {
  const events = [
    { seq: 1, ts: 10, type: "incident_opened", payload: {} },
    { seq: 2, ts: 14, type: "culprit_found", payload: {} },
    { seq: 3, ts: 20, type: "checklist_step", payload: {} },
    { seq: 4, ts: 21, type: "blocked", payload: {} },
    { seq: 5, ts: 22, type: "escalated", payload: {} },
  ];
  const t = stageTimes(events, 99);
  assert.deepEqual(t.detect, { start: 10, took: 4 });
  assert.deepEqual(t.diagnose, { start: 14, took: 6 });
  assert.deepEqual(t.check, { start: 20, took: 2 });
  assert.deepEqual(t.outcome, { start: 22, took: 0 });
  assert.equal(t.act, undefined);
  assert.deepEqual(stageTimes(events.slice(0, 2), 30).diagnose, { start: 14, took: 16 });
});
