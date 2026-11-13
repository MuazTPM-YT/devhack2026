import assert from "node:assert/strict";
import { test } from "node:test";

import { type BusRecord, initialState, reduce } from "./live.ts";
import { modeLabel, orchSummary, type OrchestrationStatus } from "./orchestration.ts";

const base: OrchestrationStatus = { mode: "disabled", delegation_enabled: false, max_active_commanders: 2,
  max_model_requests: 9, phases: {}, specialists_running: 0, unknown_writes: 0 };

test("mode tag says which path handles incidents", () => {
  assert.equal(modeLabel(null), null);
  assert.equal(modeLabel(base)!.label, "Single agent");
  assert.equal(modeLabel({ ...base, mode: "shadow" })!.tone, "warn");
  assert.equal(modeLabel({ ...base, mode: "coordinated", phases: { investigating: 1, awaiting_gateway: 1 } })!.label,
    "Coordinated · specialists off · 2 open");
  // an unknown write outranks everything: nothing runs until a human clears it
  const stuck = modeLabel({ ...base, mode: "coordinated", unknown_writes: 1 })!;
  assert.equal(stuck.tone, "bad");
  assert.match(stuck.label, /outcome unknown/);
});

let seq = 0;
const rec = (type: string, payload: Record<string, unknown>, id = "inc-a"): BusRecord =>
  ({ seq: ++seq, ts: seq, event: { type, incident_id: id, payload } });

test("incident row summary: services, why grouped, related, fix and specialist", () => {
  const s = [
    rec("incident_opened", { unhealthy: ["cart", "checkout"] }),
    rec("incident_scope_changed", { scope_revision: 0, services: ["cart", "checkout"],
      reasons: ["shared_dependency", "dependency:valkey-cart"], related: [{ incident_id: "inc-b", reason: "unknown_topology" }] }),
    rec("investigation_task_changed", { task_id: "t1", question_id: "q", state: "running", attempt: 1 }),
    rec("action_intent_changed", { intent_id: "i1", status: "queued", plan_revision: 0 }),
  ].reduce(reduce, initialState);
  const inc = s.incidents["inc-a"];
  assert.deepEqual(inc.orch!.related, [{ incidentId: "inc-b", reason: "unknown_topology" }]);
  assert.equal(orchSummary(inc), "2 services · shared dependency · 1 related · fix queued · specialist on it");
  const legacy = [rec("incident_opened", { unhealthy: ["payment"] }, "inc-old")].reduce(reduce, initialState);
  assert.equal(orchSummary(legacy.incidents["inc-old"]), null);
});
