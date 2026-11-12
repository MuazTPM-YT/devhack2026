// shortcut: scripted bad-deploy incident for ?demo=1 so the UI works without the spine; remove before submission
// (Anirudh asked for a reminder: see team/anirudh/STATE.md "Next")

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
        text: "payment v2-bad rolled back to 3.1.0. Errors on payment, checkout and frontend back to baseline in 14 s.",
        evidence_ids: ["change:payment-image", "metric:payment-err", "trace:checkout-payment"],
      },
      receipt_url: "/receipts/1",
    },
  },
];

// receipt the gateway would return for receipt 1
export const DEMO_RECEIPT = { forecast_s: 18, elapsed_s: 14, prediction_held: true };
