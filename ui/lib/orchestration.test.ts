import assert from "node:assert/strict";
import { test } from "node:test";

import { type BusRecord, initialState, reduce } from "./live.ts";
import { agentLanes, modeLabel, nowLine, orchSummary, type OrchestrationStatus, reasonText } from "./orchestration.ts";

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

test("reason codes read as words", () => {
  assert.equal(reasonText("dependency:valkey-cart"), "cause: valkey-cart");
  assert.equal(reasonText("change:journal:41"), "change: journal:41");
  assert.equal(reasonText("shared_dependency"), "shared dependency");
});

test("overview sees every open incident and which one blames a service", async () => {
  const { openIncidentIds, culpritIncident } = await import("./orchestration.ts");
  const s = [
    rec("incident_opened", { opened_at: 100, unhealthy: ["payment"] }, "inc-pay"),
    rec("culprit_found", { culprit: "payment", victims: [] }, "inc-pay"),
    rec("incident_opened", { opened_at: 101, unhealthy: ["ad"] }, "inc-ad"),
    rec("culprit_found", { culprit: "ad", victims: [] }, "inc-ad"),
    rec("incident_opened", { opened_at: 90, unhealthy: ["cart"] }, "inc-old"),
    rec("incident_resolved", { card: { incident_id: "inc-old", status: "FIXED", text: "x", evidence_ids: [] } }, "inc-old"),
  ].reduce(reduce, initialState);
  const open = openIncidentIds(s, 120, 1200);
  assert.deepEqual([...open].sort(), ["inc-ad", "inc-pay"]);
  assert.equal(culpritIncident(s, open, "ad"), "inc-ad");
  assert.equal(culpritIncident(s, open, "payment"), "inc-pay");
  assert.equal(culpritIncident(s, open, "cart"), null);  // its incident is closed
});

// events at chosen times, so spans and the axis can be checked
function incident(steps: [number, string, Record<string, unknown>][], id = "inc-l") {
  const s = steps.map(([ts, type, payload], i): BusRecord => ({ seq: i + 1, ts, event: { type, incident_id: id, payload } }))
    .reduce(reduce, initialState);
  return s.incidents[id];
}

test("now line: the most urgent thing wins, nothing once closed", () => {
  const opened: [number, string, Record<string, unknown>][] = [[100, "incident_opened", { unhealthy: ["cart"] }]];
  assert.deepEqual(nowLine(incident(opened)), { text: "Grouping alerts", tone: "idle" });
  assert.equal(nowLine(incident([...opened, [101, "rule_matched", { pattern: "recent_change" }]]))!.text, "Agent investigating");
  const scoped: typeof opened = [...opened, [101, "incident_scope_changed", { scope_revision: 0, services: ["cart"] }],
    [102, "tool_called", { tool: "get_pods" }]];
  assert.equal(nowLine(incident(scoped))!.text, "Commander investigating");
  const asked: typeof opened = [...scoped, [103, "investigation_task_changed", { task_id: "t1", question_id: "q", state: "running", attempt: 1 }]];
  assert.equal(nowLine(incident(asked))!.text, "Commander waiting on a specialist");
  const approval: typeof opened = [...asked, [104, "approval_requested", { approval_id: "a1", expires_at: 400 }]];
  assert.deepEqual(nowLine(incident(approval)), { text: "Fix waiting for approval", tone: "warn" });
  const unknown: typeof opened = [...approval, [105, "action_intent_changed", { intent_id: "i1", status: "execution_unknown", plan_revision: 1 }]];
  assert.equal(nowLine(incident(unknown))!.tone, "bad");
  assert.equal(nowLine(incident([...opened, [106, "action_executed", { receipt_id: 1, tool: "scale", target: "cart" }],
    [107, "verify_tick", { severity: 3 }]]))!.text, "Verifying the fix");
  assert.equal(nowLine(incident([...unknown, [108, "escalated", {}]])), null);
});

test("single agent: one lane, the run as one span holding its requests, no budget limit", () => {
  const inc = incident([
    [100, "incident_opened", { unhealthy: ["payment"] }],
    [102, "rule_matched", { pattern: "recent_change", tools: ["rollback_deploy"] }],
    [104, "tool_called", { tool: "get_pods", args: { service: "payment" } }],
    [104.2, "tool_called", { tool: "get_service_health" }],
    [107, "tool_called", { tool: "get_recent_changes" }],
    [110, "llm_called", { usage: { requests: 4, total_tokens: 900 } }],
    [111, "diagnosis_ready", { pattern: "recent_change", culprit: "payment" }],
  ]);
  const v = agentLanes(inc, 120, 9);
  assert.deepEqual(v.lanes.map((l) => [l.kind, l.title]), [["agent", "Agent"]]);
  const [lane] = v.lanes;
  // two reads 0.2 s apart share a tick; the third stands alone
  assert.deepEqual(lane.marks.map((m) => [m.kind, m.n, m.t0, m.t1]),
    [["reads", 2, 104, 104.2], ["reads", 1, 107, 107], ["run", 4, 102, 110]]);
  assert.equal(lane.marks[0].title, "Read pods of payment\nRead service health");
  assert.equal(lane.sub, "4 requests · 3 reads");
  assert.deepEqual(v.notes, []);
  // max_model_requests is the coordinated budget; a single agent has no meter
  assert.deepEqual([v.budget.used, v.budget.max, v.budget.left, v.budget.tokens, v.budget.reads], [4, null, null, 900, 3]);
  assert.deepEqual([v.t0, v.t1], [100, 120]);
  assert.match(lane.summary, /^Agent: 4 model requests, 3 reads/);
});

test("single agent still thinking shows an open run, not invented requests", () => {
  const inc = incident([[100, "incident_opened", {}], [102, "rule_matched", {}], [103, "tool_called", { tool: "get_pods" }]]);
  const run = agentLanes(inc, 110).lanes[0].marks.at(-1)!;
  assert.deepEqual([run.kind, run.n, run.live, run.t0, run.t1], ["run", 0, true, 102, 110]);
});

test("coordinated demo: commander, specialist and fix lanes, hand-offs, 5 of 9 requests", async () => {
  const { DEMO_COORDINATED } = await import("./demo.ts");
  const inc = incident(DEMO_COORDINATED.map((s) => [1000 + s.at, s.type, s.payload]));
  const v = agentLanes(inc, 2000, 9);
  assert.deepEqual(v.lanes.map((l) => [l.kind, l.title]), [["commander", "Commander"], ["specialist", "Specialist"], ["fix", "Fix"]]);
  const [main, spec, fix] = v.lanes;
  assert.deepEqual([main.requests, spec.requests, main.reads, spec.reads], [3, 2, 4, 2]);
  // a request is a span: it was sent ms before the event that reports it
  const first = main.marks.find((m) => m.kind === "request")!;
  assert.deepEqual([first.t0, first.t1], [1005 - 2.4, 1005]);
  assert.deepEqual(spec.state, { label: "supported", tone: "ok" });
  assert.equal(fix.sub, "revert_config → payment");
  assert.deepEqual(fix.state, { label: "done", tone: "ok" });
  assert.deepEqual(fix.marks.map((m) => [m.kind, m.t0, m.t1, m.live]), [["wait", 1021.5, 1024.5, false], ["verify", 1025, 1039.5, false]]);
  assert.equal(fix.marks[0].title, "Approval approved");
  assert.deepEqual(v.notes.map((n) => [n.kind, n.from, n.to]), [["ask", "main", "task-demo-1"], ["finding", "task-demo-1", "main"]]);
  assert.equal(v.notes[0].title, "Change check started: 2 recorded changes still plausible");
  assert.deepEqual([v.budget.used, v.budget.commander, v.budget.specialist, v.budget.max, v.budget.left, v.budget.reused],
    [5, 3, 2, 9, 4, 2]);
  assert.equal(v.budget.tokens, 3980 + 80 + 4410 + 120 + 2100 + 60 + 2600 + 140 + 5200 + 310);
  // closed: the axis ends at the fix's own late record, not at the wall clock
  assert.deepEqual([v.t0, v.t1, v.now, v.truncated], [1000.5, 1040, null, false]);
});

test("no specialist: the decision is a note, never an empty lane", () => {
  const none = { status: "none_needed", explanation: "No specialist needed: shared cause valkey-cart already supported" };
  const inc = incident([
    [100, "incident_opened", {}],
    [101, "incident_scope_changed", { scope_revision: 0, services: ["cart"] }],
    [102, "delegation_decided", none],
    [103, "delegation_decided", none],
    [104, "delegation_decided", { status: "denied", explanation: "All specialist slots are busy", reason: "fleet_busy" }],
  ]);
  const v = agentLanes(inc, 110, 9);
  assert.deepEqual(v.lanes.map((l) => l.kind), ["commander"]);
  assert.deepEqual(v.notes.map((n) => [n.kind, n.to, n.tone, n.title, n.detail]), [
    ["decision", null, "idle", none.explanation, null],
    ["decision", null, "warn", "All specialist slots are busy", "fleet busy"],
  ]);
});

test("a specialist that never got a call is a lane with a state and no marks; retries stay one lane", () => {
  const inc = incident([
    [100, "incident_opened", {}],
    [101, "delegation_decided", { status: "admitted", explanation: "Change check started", task_id: "t1" }],
    [102, "investigation_task_changed", { task_id: "t1", question_id: "q", state: "running", attempt: 1 }],
    [105, "investigation_task_changed", { task_id: "t1", question_id: "q", state: "running", attempt: 2 }],
    [109, "investigation_task_changed", { task_id: "t1", question_id: "q", state: "failed", attempt: 2 }],
  ]);
  const v = agentLanes(inc, 130);
  const spec = v.lanes[1];
  assert.deepEqual([v.lanes.length, spec.marks.length, spec.t0, spec.t1], [2, 0, 101, 109]);
  assert.deepEqual(spec.state, { label: "failed", tone: "bad" });
  assert.equal(spec.sub, "0 requests · 0 reads · attempt 2");
});

test("open incident: live lanes and marks run to now", () => {
  const inc = incident([
    [100, "incident_opened", {}],
    [101, "delegation_decided", { status: "admitted", explanation: "Change check started", task_id: "t1" }],
    [102, "investigation_task_changed", { task_id: "t1", question_id: "q", state: "running", attempt: 1 }],
    [103, "approval_requested", { approval_id: "a1", expires_at: 500 }],
  ]);
  const v = agentLanes(inc, 140);
  assert.equal(v.t1, 140);
  assert.equal(v.lanes[1].t1, 140);
  const wait = v.lanes[2].marks[0];
  assert.deepEqual([wait.kind, wait.t0, wait.t1, wait.live], ["wait", 103, 140, true]);
  assert.deepEqual(v.lanes[2].state, { label: "awaiting approval", tone: "warn" });
});

test("a write with no answer is marked bad on the fix lane and said in a note", () => {
  const inc = incident([
    [100, "incident_opened", {}],
    [101, "action_intent_changed", { intent_id: "i1", status: "queued", plan_revision: 1 }],
    [104, "action_intent_changed", { intent_id: "i1", status: "executing", plan_revision: 1 }],
    [105, "action_intent_changed", { intent_id: "i1", status: "execution_unknown", plan_revision: 1, reason: "timeout after send" }],
  ]);
  const v = agentLanes(inc, 120);
  const fix = v.lanes.at(-1)!;
  assert.deepEqual(fix.marks.map((m) => [m.t0, m.t1, m.bad, m.live]), [[101, 104, false, false], [105, 120, true, true]]);
  assert.deepEqual(fix.state, { label: "execution unknown", tone: "bad" });
  assert.deepEqual(v.notes.map((n) => [n.from, n.tone, n.title, n.detail]), [["fix", "bad", "Fix execution unknown", "timeout after send"]]);
});

test("old audit logs: a read logged as llm_called is a read, and a cut-off start says so", () => {
  const inc = incident([
    [100, "incident_opened", {}],
    [101, "incident_scope_changed", { scope_revision: 0, services: ["cart"] }],
    [102, "llm_called", { tool: "get_pods", args: {} }],
    [103, "llm_called", { kind: "call", ms: 500, usage: { prompt_tokens: 10, completion_tokens: 2 } }],
    [104, "llm_called", { kind: "call", ms: 500, usage: { prompt_tokens: 10, completion_tokens: 2 } }],
  ]);
  const whole = agentLanes(inc, 110, 9);
  assert.deepEqual(whole.lanes[0].marks.map((m) => m.kind), ["reads", "request", "request"]);
  assert.equal(whole.truncated, false);
  // the reducer's event cap dropped the start: totals come from its counters, the axis from what is left
  const cut = agentLanes({ ...inc, events: inc.events.slice(4) }, 110, 9);
  assert.deepEqual([cut.truncated, cut.t0, cut.lanes[0].requests, cut.budget.used, cut.budget.tokens], [true, 104, 1, 2, 24]);
});
