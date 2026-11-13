// shortcut: scripted bad-deploy incident for ?demo=1 so the UI works without the spine; remove before submission
// (Anirudh asked for a reminder: see team/anirudh/STATE.md "Next")

import type { OrchestrationStatus } from "./orchestration.ts";

export interface DemoStep {
  at: number;
  type: string;
  payload: Record<string, unknown>;
}

// verify window: severity falls as the rollback lands
const TICKS = [9, 9, 7, 4, 2, 0, 0].map((severity, i) => ({
  at: 22 + i * 2,
  type: "verify_tick",
  payload: { receipt_id: 1, severity, recovered: severity === 0 },
}));

const STEPS: [string, string | null][] = [
  ["schema", null],
  ["hands_off", null],
  ["policy", null],
  ["dry_run", "1 spec paths change"],
  ["net_benefit", "rollback forecast 40 s, cost 2 pods"],
  ["freshness", null],
  ["trust_gate", "bound 0.905"],
  ["execute", null],
];

export const DEMO_SCRIPT: DemoStep[] = [
  { at: 0.5, type: "incident_opened", payload: { severity: 9, unhealthy: ["payment"] } },
  { at: 2.5, type: "alerts_grouped", payload: { unhealthy: ["checkout", "payment"] } },
  { at: 4, type: "alerts_grouped", payload: { unhealthy: ["checkout", "frontend", "payment"] } },
  { at: 5.5, type: "culprit_found", payload: { culprit: "payment", victims: ["checkout", "frontend"], from_traces: true } },
  { at: 7, type: "bundle_built", payload: { changes: 1, metrics: 6, traces: 4, events: 2, logs: 3 } },
  { at: 8, type: "rule_matched", payload: { pattern: "recent_change", tools: ["rollback_deploy"] } },
  { at: 9, type: "llm_called", payload: { provider: "opencode_go", attempt: 1 } },
  { at: 11, type: "diagnosis_ready", payload: { pattern: "recent_change", culprit: "payment" } },
  ...STEPS.map(([name, reason], i) => ({
    at: 12.5 + i * 0.9, type: "checklist_step", payload: { name, passed: true, reason },
  })),
  { at: 20.5, type: "action_executed", payload: { receipt_id: 1, tool: "rollback_deploy", target: "payment" } },
  ...TICKS,
  { at: 36, type: "harm_check", payload: { receipt_id: 1, clean: true } },
  {
    at: 37, type: "incident_resolved", payload: {
      card: {
        incident_id: "", status: "resolved",
        text: "payment v2-bad rolled back to 3.1.0. Errors on payment, checkout and frontend back to baseline in 12 s.",
        evidence_ids: ["change:payment-image", "metric:payment-err", "trace:checkout-payment"],
      },
      receipt_url: "/receipts/1", prediction_held: true,
    },
  },
];

// receipt the gateway would return for receipt 1
export const DEMO_RECEIPT = { forecast_s: 18, elapsed_s: 11.5, prediction_held: true, trust: { lower_bound: 0.905 } };

const TASK = "task-demo-1";
const QUESTION = "q-change-1";
const INTENT = "int-demo-1";
const MODEL = { provider: "opencode_go", model: "deepseek-v4.1-flash" };

// one provider request as coordinated mode reports it: sent when it ends, with how long it took
function call(at: number, role: "commander" | "specialist", ms: number, tokensIn: number, tokensOut: number): DemoStep {
  return {
    at, type: "llm_called", payload: {
      ...MODEL, kind: "call", role, ms, ...(role === "specialist" ? { task_id: TASK } : {}),
      usage: { prompt_tokens: tokensIn, completion_tokens: tokensOut, requests: 1 },
    },
  };
}

function reads(at: number, tool: string, args: Record<string, unknown>, evidence_ids: string[], specialist = false): DemoStep {
  return { at, type: "tool_called", payload: { tool, args, ms: 30, evidence_ids, ...(specialist ? { task_id: TASK } : {}) } };
}

const GATES: [string, boolean, string | null][] = [
  ["schema", true, null],
  ["hands_off", true, null],
  ["policy", true, null],
  ["dry_run", true, "1 spec paths change"],
  ["net_benefit", true, "forecast 0 s"],
  ["freshness", true, null],
  ["trust_gate", false, "the agent chose this fix itself, not the rule's first pick; a human must approve"],
];

// coordinated mode: two services, one cause, a commander that asks one specialist, a fix a human approves.
// Shaped after a real k3d run (flag flip on payment, decoy env change); the finding is scripted
export const DEMO_COORDINATED: DemoStep[] = [
  { at: 0.5, type: "incident_opened", payload: { severity: 8, unhealthy: ["payment"] } },
  { at: 0.6, type: "incident_scope_changed", payload: { scope_revision: 0, services: ["payment"], reasons: ["independent"] } },
  { at: 1.2, type: "culprit_found", payload: { culprit: "payment", victims: ["checkout"], from_traces: true } },
  { at: 1.8, type: "bundle_built", payload: { changes: 2, metrics: 6, traces: 4, events: 1, logs: 3 } },
  { at: 2.4, type: "rule_matched", payload: { pattern: "recent_change", tools: ["rollback_deploy"] } },
  call(5, "commander", 2400, 3980, 80),
  reads(5.1, "get_service_health", {}, ["metric:payment-err", "metric:checkout-err"]),
  reads(5.2, "get_recent_changes", { object: "deployment/payment" }, ["journal:81", "journal:82"]),
  { at: 6, type: "alerts_grouped", payload: { unhealthy: ["checkout", "payment"] } },
  {
    at: 6.1, type: "incident_scope_changed", payload: {
      scope_revision: 1, services: ["checkout", "payment"], reasons: ["shared_dependency", "dependency:payment"],
    },
  },
  call(9, "commander", 2800, 4410, 120),
  reads(9.1, "get_metric_history", { service: "payment", metric: "err_ratio" }, ["query:payment-err"]),
  reads(9.15, "get_service_health", {}, ["metric:payment-err", "metric:checkout-err"]),
  { at: 9.2, type: "evidence_reused", payload: { query_key: "health", source: "cache", age_s: 4.1, evidence_ids: ["metric:payment-err"] } },
  {
    at: 9.6, type: "delegation_decided", payload: {
      status: "admitted", explanation: "Change check started: 2 recorded changes still plausible",
      question_id: QUESTION, task_id: TASK,
    },
  },
  { at: 9.7, type: "investigation_task_changed", payload: { task_id: TASK, question_id: QUESTION, state: "running", attempt: 1 } },
  call(11.6, "specialist", 1900, 2100, 60),
  reads(11.7, "get_recent_changes", { object: "configmap/flagd-config" }, ["journal:81"], true),
  reads(11.8, "get_metric_history", { service: "payment", metric: "err_ratio" }, ["query:payment-err"], true),
  { at: 11.85, type: "evidence_reused", payload: { query_key: "payment-err", source: "cache", age_s: 2.7, evidence_ids: ["query:payment-err"] } },
  call(14.2, "specialist", 2400, 2600, 140),
  { at: 14.3, type: "investigation_task_changed", payload: { task_id: TASK, question_id: QUESTION, state: "succeeded", attempt: 1 } },
  {
    at: 14.4, type: "finding_recorded", payload: {
      task_id: TASK, finding_id: "f-demo-1", question_id: QUESTION, verdict: "supported",
      summary: "The paymentFailure flag flip 52 s before onset fits the errors; the PROMO_BANNER env change does not.",
      evidence_ids: ["journal:81"],
    },
  },
  call(18, "commander", 3500, 5200, 310),
  { at: 18.1, type: "llm_called", payload: { ...MODEL, kind: "summary", usage: { requests: 5, tool_calls: 6 } } },
  {
    at: 18.2, type: "diagnosis_ready", payload: {
      pattern: "recent_change", culprit: "payment", decision: "other", origin: "model",
      chosen: { tool: "revert_config", target: "payment" }, rule_choice: { tool: "rollback_deploy", target: "payment" },
      reason: "The flag flip explains the errors; the image did not change.",
    },
  },
  ...GATES.map(([name, passed, reason], i) => ({
    at: 18.6 + i * 0.4, type: "checklist_step", payload: { name, passed, reason },
  })),
  {
    // expires_at is seconds after the replay starts; use-live turns it into a clock time
    at: 21.5, type: "approval_requested", payload: {
      approval_id: "appr-demo-1", diff: "revert_config payment: flag paymentFailure -> off",
      forecast: "about 0 s of lost capacity (2 replicas, surge on)", expires_at: 321,
    },
  },
  { at: 21.6, type: "action_intent_changed", payload: { intent_id: INTENT, status: "awaiting_approval", plan_revision: 1, approval_id: "appr-demo-1" } },
  { at: 24.5, type: "approval_decided", payload: { approval_id: "appr-demo-1", decision: "approved" } },
  { at: 24.6, type: "action_intent_changed", payload: { intent_id: INTENT, status: "executing", plan_revision: 1 } },
  { at: 24.8, type: "checklist_step", payload: { name: "execute", passed: true, reason: null } },
  { at: 25, type: "action_executed", payload: { receipt_id: 1, tool: "revert_config", target: "payment" } },
  { at: 25.1, type: "action_intent_changed", payload: { intent_id: INTENT, status: "verifying", plan_revision: 1, receipt_id: 1 } },
  ...[8, 8, 5, 2, 0, 0].map((severity, i) => ({
    at: 27 + i * 2, type: "verify_tick", payload: { receipt_id: 1, severity, recovered: severity === 0 },
  })),
  { at: 38.5, type: "harm_check", payload: { receipt_id: 1, clean: true } },
  {
    at: 39.5, type: "incident_resolved", payload: {
      card: {
        incident_id: "", status: "resolved",
        text: "payment flag paymentFailure put back to off. Errors on payment and checkout back to baseline in 10 s.",
        evidence_ids: ["journal:81", "metric:payment-err", "trace:checkout-payment"],
      },
      receipt_url: "/receipts/1", prediction_held: true,
    },
  },
  // the fix's own record closes after the incident, as on the real bus
  { at: 40, type: "action_intent_changed", payload: { intent_id: INTENT, status: "terminal", plan_revision: 1, receipt_id: 1, reason: "receipt #1: success" } },
];

// first load shows the coordinated run; "Replay demo" alternates with the single-agent one
export const DEMO_RUNS: DemoStep[][] = [DEMO_COORDINATED, DEMO_SCRIPT];

// what the gateway would answer on /orchestration/status during the coordinated run
export const DEMO_STATUS: OrchestrationStatus = {
  mode: "coordinated", delegation_enabled: true, max_active_commanders: 2, max_model_requests: 9,
  phases: {}, specialists_running: 0, unknown_writes: 0,
};
