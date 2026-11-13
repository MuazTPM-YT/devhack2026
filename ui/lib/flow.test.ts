import assert from "node:assert/strict";
import { test } from "node:test";

import { flowState, liveEdge } from "./flow.ts";
import { type BusRecord, type LiveState, initialState, reduce } from "./live.ts";

let seq = 0;
function run(...events: [string, Record<string, unknown>?][]): LiveState {
  return events.reduce<LiveState>((s, [type, payload]) => {
    seq += 1;
    const r: BusRecord = { seq, ts: 100 + seq, event: { type, incident_id: "inc-1", payload: payload ?? {} } };
    return reduce(s, r);
  }, initialState);
}
const inc = (s: LiveState) => s.incidents["inc-1"];

test("nothing open: everything idle", () => {
  const f = flowState(null, null);
  assert.equal(f.active, null);
  assert.ok(Object.values(f.nodes).every((n) => n === "idle"));
});

test("an opened incident lights the observer and the edge into it", () => {
  const s = run(["incident_opened", { unhealthy: ["payment"] }]);
  const f = flowState(inc(s), "incident_opened");
  assert.equal(f.active, "observer");
  assert.equal(f.nodes.observer, "active");
  assert.equal(f.nodes.brain, "idle");
  assert.deepEqual(liveEdge(f), { from: "shop", to: "observer", label: "metrics, pods, changes" });
});

test("checklist gates and the verifier follow the events", () => {
  const s = run(["incident_opened"], ["culprit_found", { culprit: "payment" }], ["llm_called"],
    ["checklist_step", { name: "schema", passed: true }], ["checklist_step", { name: "trust_gate", passed: false }],
    ["approval_requested", { approval_id: "a" }]);
  const f = flowState(inc(s), "approval_requested");
  assert.equal(f.gates.schema, "passed");
  assert.equal(f.gates.trust_gate, "failed");
  assert.equal(f.gates.execute, "idle");
  assert.equal(f.active, "human");
  assert.equal(liveEdge(f)?.from, "gateway");
});

test("resolved: all reached parts done, nothing active", () => {
  const s = run(["incident_opened"], ["culprit_found", { culprit: "payment" }],
    ["checklist_step", { name: "execute", passed: true }], ["action_executed", { receipt_id: 1 }],
    ["verify_tick", { severity: 0 }], ["incident_resolved", { card: { status: "FIXED", text: "x", evidence_ids: [] } }]);
  const f = flowState(inc(s), "incident_resolved");
  assert.equal(f.active, null);
  assert.equal(f.nodes.verifier, "done");
  assert.equal(f.nodes.kube, "done");
});

test("escalated at policy: the gateway shows the failure", () => {
  const s = run(["incident_opened"], ["culprit_found", { culprit: "valkey-cart" }],
    ["checklist_step", { name: "policy", passed: false }],
    ["escalated", { card: { status: "WOKE YOU BECAUSE", text: "x", evidence_ids: [] } }]);
  const f = flowState(inc(s), "escalated");
  assert.equal(f.nodes.gateway, "failed");
  assert.equal(f.nodes.human, "active");
  assert.equal(f.nodes.verifier, "idle");
});

test("a fix that did not hold fails the verifier and wakes a human", () => {
  const s = run(["incident_opened"], ["checklist_step", { name: "execute", passed: true }],
    ["action_executed", { receipt_id: 1 }], ["verify_tick", { severity: 9 }], ["action_undone", {}],
    ["escalated", { card: { status: "WOKE YOU BECAUSE", text: "x", evidence_ids: [] } }]);
  const f = flowState(inc(s), "escalated");
  assert.equal(f.nodes.verifier, "failed");
  assert.equal(f.active, "human");
});
