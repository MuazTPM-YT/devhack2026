import assert from "node:assert/strict";
import { test } from "node:test";

import { type BusRecord, EVENT_TYPES, type LiveState, initialState, reduce } from "./live.ts";

let seq = 0;
function rec(type: string, payload: Record<string, unknown> = {}, incident_id: string | null = "inc-1", ts = 100 + seq): BusRecord {
  seq += 1;
  return { seq, ts, event: { type, incident_id, payload } };
}

function run(...records: BusRecord[]): LiveState {
  return records.reduce(reduce, initialState);
}

const card = { incident_id: "inc-1", status: "resolved", text: "payment rolled back", evidence_ids: ["e1"] };

test("happy path lights every stage and ends resolved", () => {
  const s = run(
    rec("incident_opened", { opened_at: 100, onset_at: 95, severity: 6, unhealthy: ["payment"] }),
    rec("alerts_grouped", { unhealthy: ["checkout", "payment"] }),
    rec("culprit_found", { culprit: "payment", victims: ["checkout"], from_traces: true }),
    rec("bundle_built", { changes: 1, metrics: 4, traces: 3, events: 0, logs: 2 }),
    rec("rule_matched", { pattern: "recent_change", tools: ["rollback_deploy"] }),
    rec("diagnosis_ready", { pattern: "recent_change", culprit: "payment" }),
    rec("checklist_step", { name: "allowlist", passed: true }),
    rec("action_executed", { receipt_id: 7, tool: "rollback_deploy", target: "payment" }),
    rec("verify_tick", { receipt_id: 7, severity: 4, recovered: false }),
    rec("verify_tick", { receipt_id: 7, severity: 0, recovered: true }),
    rec("harm_check", { receipt_id: 7, clean: true }),
    rec("incident_resolved", { card, receipt_url: "/receipts/7" }),
  );
  const inc = s.incidents["inc-1"];
  assert.equal(s.current, "inc-1");
  assert.equal(inc.onsetAt, 95);
  assert.deepEqual(inc.unhealthy, ["checkout", "payment"]);
  assert.equal(inc.groupings, 1);
  assert.equal(inc.culprit, "payment");
  assert.deepEqual(inc.victims, ["checkout"]);
  assert.deepEqual(inc.bundle, { changes: 1, metrics: 4, traces: 3, events: 0, logs: 2 });
  assert.equal(inc.pattern, "recent_change");
  assert.equal(inc.action?.receiptId, 7);
  assert.deepEqual(inc.ticks.map((t) => t.severity), [4, 0]);
  assert.equal(inc.harmClean, true);
  assert.equal(inc.outcome, "resolved");
  assert.equal(inc.card?.text, "payment rolled back");
  assert.ok(Object.values(inc.stages).every((v) => v === "done"));
});

test("stages light in order and settle the ones before", () => {
  const s = run(rec("incident_opened"), rec("culprit_found", { culprit: "cart" }));
  const st = s.incidents["inc-1"].stages;
  assert.equal(st.detect, "done");
  assert.equal(st.group, "done");
  assert.equal(st.diagnose, "active");
  assert.equal(st.check, "idle");
});

test("failed checklist step marks check failed and escalation keeps it failed", () => {
  const s = run(
    rec("incident_opened"),
    rec("checklist_step", { name: "hands_off", passed: false, reason: "human edited payment" }),
    rec("escalated", { card: { ...card, status: "escalated" } }),
  );
  const inc = s.incidents["inc-1"];
  assert.equal(inc.stages.check, "failed");
  assert.equal(inc.checklist[0].reason, "human edited payment");
  assert.equal(inc.outcome, "escalated");
  assert.equal(inc.stages.verify, "idle");
});

test("handed off during verify fails the verify tile", () => {
  const s = run(rec("incident_opened"), rec("verify_tick", { severity: 3 }), rec("handed_off", { card }));
  assert.equal(s.incidents["inc-1"].stages.verify, "failed");
  assert.equal(s.incidents["inc-1"].outcome, "handed_off");
});

test("replayed records are ignored", () => {
  const first = rec("incident_opened");
  const s = run(first, rec("alerts_grouped", { unhealthy: ["a"] }));
  assert.equal(reduce(s, first), s);
});

test("a new incident becomes current and older ones stay listed", () => {
  const s = run(rec("incident_opened", {}, "inc-1"), rec("incident_opened", {}, "inc-2"), rec("verify_tick", {}, "inc-1"));
  assert.equal(s.current, "inc-2");
  assert.deepEqual(s.order, ["inc-2", "inc-1"]);
});

test("events without an incident only reach the feed", () => {
  const s = run(rec("blocked", {}, null));
  assert.deepEqual(s.incidents, {});
  assert.equal(s.feed[0].type, "blocked");
});

test("bad payload values fall back instead of crashing", () => {
  const s = run(rec("culprit_found", { culprit: 5, victims: "x" }), rec("verify_tick", { severity: "high" }));
  const inc = s.incidents["inc-1"];
  assert.equal(inc.culprit, null);
  assert.deepEqual(inc.victims, []);
  assert.equal(inc.ticks[0].severity, null);
});

test("demo script ends resolved with every tile done", async () => {
  const { DEMO_SCRIPT } = await import("./demo.ts");
  const s = DEMO_SCRIPT.reduce<LiveState>((acc, step, i) => reduce(acc, {
    seq: i + 1, ts: 1000 + step.at, event: { type: step.type, incident_id: "inc-demo-1", payload: step.payload },
  }), initialState);
  const inc = s.incidents["inc-demo-1"];
  assert.equal(inc.outcome, "resolved");
  assert.ok(Object.values(inc.stages).every((v) => v === "done"));
  assert.equal(inc.groupings, 2);
  assert.equal(inc.checklist.length, 8);
  assert.ok(DEMO_SCRIPT.every((step, i) => i === 0 || step.at >= DEMO_SCRIPT[i - 1].at));
});

test("each incident keeps its own events in order with payloads", () => {
  const s = run(
    rec("incident_opened", { severity: 4 }, "inc-1"),
    rec("incident_opened", {}, "inc-2"),
    rec("culprit_found", { culprit: "cart" }, "inc-1"),
    rec("blocked", {}, null),
  );
  assert.deepEqual(s.incidents["inc-1"].events.map((e) => e.type), ["incident_opened", "culprit_found"]);
  assert.deepEqual(s.incidents["inc-1"].events[1].payload, { culprit: "cart" });
  assert.deepEqual(s.incidents["inc-2"].events.map((e) => e.type), ["incident_opened"]);
});

test("a gate that asks a human does not leave check stopped", () => {
  const s = run(
    rec("incident_opened"),
    rec("checklist_step", { name: "trust_gate", passed: false, reason: "trust bound 0.0 < 0.9" }),
    rec("approval_requested", { approval_id: "a1", diff: "", forecast: "", expires_at: 0, card }),
    rec("approval_decided", { approval_id: "a1", decision: "approved" }),
    rec("action_executed", { receipt_id: 1, tool: "rollback_deploy", target: "payment" }),
    rec("incident_resolved", { card }),
  );
  assert.equal(s.incidents["inc-1"].stages.check, "done");
});

test("a telemetry read is a read, never a model call", () => {
  const s = run(
    rec("incident_opened", { opened_at: 100, severity: 4, unhealthy: ["payment"] }, "inc-r"),
    rec("tool_called", { tool: "get_pods", args: { service: "payment" }, ms: 12, evidence_ids: ["event:1", "event:2"] }, "inc-r"),
    // audit logs written before tool_called existed carry reads as llm_called with a tool name
    rec("llm_called", { tool: "get_recent_changes", args: {}, ms: 9, evidence_ids: [] }, "inc-r"),
    rec("llm_called", { provider: "opencode_go", attempt: 4, usage: { requests: 4, tool_calls: 2, prompt_tokens: 900, completion_tokens: 100 } }, "inc-r"),
  );
  const inc = s.incidents["inc-r"];
  assert.deepEqual(inc.reads.map((r) => [r.tool, r.evidence, r.ms]), [["get_pods", 2, 12], ["get_recent_changes", 0, 9]]);
  assert.equal(inc.llmCalls, 4);
  assert.equal(inc.stages.diagnose, "active");
});

test("the agent's choice is kept next to what the rule would have done", () => {
  const ready = (payload: Record<string, unknown>) => run(
    rec("incident_opened", { opened_at: 100, severity: 4, unhealthy: ["payment"] }, "inc-c"),
    rec("diagnosis_ready", { pattern: "recent_change", culprit: "payment", ...payload }, "inc-c"),
  ).incidents["inc-c"].choice;
  assert.equal(ready({}), null);  // advise and bundle mode send no decision
  assert.deepEqual(ready({ decision: "accept", origin: "model", chosen: { tool: "revert_config", target: "payment" },
    rule_choice: { tool: "rollback_deploy", target: "payment" }, reason: "The flag fits.", alternative: "The env change is harmless." }),
  { decision: "accept", origin: "model", chosen: { tool: "revert_config", target: "payment" },
    ruleChoice: { tool: "rollback_deploy", target: "payment" }, reason: "The flag fits.", alternative: "The env change is harmless." });
  const declined = ready({ decision: "decline", origin: null, chosen: null, rule_choice: null, reason: "Too thin." });
  assert.deepEqual([declined?.decision, declined?.chosen, declined?.origin], ["decline", null, null]);
});

test("resolved keeps whether the fix was proven", () => {
  const closed = (held: unknown) => run(
    rec("incident_opened", { opened_at: 100, severity: 4, unhealthy: ["payment"] }, "inc-p"),
    rec("incident_resolved", { card: { ...card, incident_id: "inc-p" }, prediction_held: held }, "inc-p"),
  ).incidents["inc-p"].predictionHeld;
  assert.equal(closed(true), true);
  assert.equal(closed(false), false);
  assert.equal(closed(undefined), null);
});

test("retry_started sends the later tiles back to idle for the next fix", () => {
  const recs: BusRecord[] = [
    { seq: 1, ts: 1, event: { type: "incident_opened", incident_id: "r", payload: { opened_at: 1 } } },
    { seq: 2, ts: 2, event: { type: "checklist_step", incident_id: "r", payload: { name: "policy", passed: true } } },
    { seq: 3, ts: 3, event: { type: "action_executed", incident_id: "r", payload: { receipt_id: 1, tool: "rollback_deploy", target: "payment" } } },
    { seq: 4, ts: 4, event: { type: "verify_tick", incident_id: "r", payload: { severity: 4 } } },
    { seq: 5, ts: 5, event: { type: "retry_started", incident_id: "r", payload: { attempt: 2, max_attempts: 3 } } },
  ];
  const inc = recs.reduce(reduce, initialState).incidents.r;
  assert.equal(inc.outcome, null);
  assert.deepEqual([inc.stages.diagnose, inc.stages.check, inc.stages.act, inc.stages.verify], ["active", "idle", "idle", "idle"]);
  assert.deepEqual(inc.ticks, []);
  assert.ok(EVENT_TYPES.includes("retry_started"));
});
