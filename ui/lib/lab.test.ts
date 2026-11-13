import assert from "node:assert/strict";
import { test } from "node:test";

import type { HealthNow } from "./chaos-api.ts";
import { attribution, byFamily, type Capability, choiceLabel, type Experiment, incidentFor, milestones, revealRows, runState, symptomAt, type Target, telemetry } from "./lab.ts";
import { type BusRecord, type Incident, initialState, reduce } from "./live.ts";

function cap(over: Partial<Capability> = {}): Capability {
  return { id: "flag:paymentFailure", primitive: "flag_variant", family: "broken_configuration", label: "flag paymentFailure",
    field: { kind: "flag", name: "paymentFailure", key: null }, choices: ["10%", "50%"], values: { "10%": "10%", "50%": "50%" },
    meaning: { "10%": 0.1, "50%": 0.5 }, current: "off", available: true, reason: null, tested: true, unit: null, what: null,
    decoy: true, ...over };
}

function exp(over: Partial<Experiment> = {}): Experiment {
  return { id: "exp-0123456789", status: "active", target: "payment", hidden: false, legacy: false, seed: null,
    family: "broken_configuration", created_at: 100, start_at: 100, applied_at: 100, expires_at: 1900, ended_at: null,
    ended_by: null, error: null, revealed: false, healthy: null,
    spec: { target: "payment", capability: "flag:paymentFailure", choice: "50%", delay_s: 0, duration_s: null, decoy: false, blind: false, skip_baseline: false },
    mutations: [{ role: "fault", place: "configmap/flagd-config flags[paymentFailure].defaultVariant", before: "off", injected: "50%", state: "applied", after_s: 0 }],
    ...over };
}

let seq = 0;
function incident(openedAt: number, ...events: [string, Record<string, unknown>, number][]): Incident {
  const recs: BusRecord[] = [["incident_opened", { opened_at: openedAt, onset_at: openedAt - 20, severity: 4, unhealthy: ["payment"] }, openedAt] as [string, Record<string, unknown>, number], ...events]
    .map(([type, payload, ts]) => ({ seq: ++seq, ts, event: { type, incident_id: `inc-${openedAt}`, payload } }));
  return recs.reduce(reduce, initialState).incidents[`inc-${openedAt}`];
}

const health = (over: Partial<HealthNow> = {}): HealthNow => ({ ts: 1000, last_ok_ts: 1000, severity: 0, prometheus_ok: true, services: {}, ...over });

test("unknown telemetry is never fresh", () => {
  assert.equal(telemetry(health(), null, 1005).state, "fresh");
  assert.equal(telemetry(null, null, 1005).state, "waiting");
  assert.equal(telemetry(null, "fetch failed", 1005).state, "offline");
  // a new response time over old numbers is still blind
  const blind = telemetry(health({ ts: 1100, prometheus_ok: false }), null, 1100);
  assert.deepEqual([blind.state, blind.ok], ["blind", false]);
  assert.match(blind.text, /health unknown.*1m 40s ago/);
  assert.equal(telemetry(health(), null, 1100).state, "stale");
  assert.equal(telemetry(health(), "fetch failed", 1005).ok, false);
});

test("choices keep their real meaning and units", () => {
  assert.equal(choiceLabel(cap(), "50%"), "50% (flag value 0.5)");
  assert.equal(choiceLabel(cap({ meaning: { on: true } }), "on"), "on");
  assert.equal(choiceLabel(cap({ primitive: "broken_env", values: { wrong_port: "payment:9999" } }), "wrong_port"), "wrong port: payment:9999");
  assert.equal(choiceLabel(cap({ primitive: "scale_zero" }), "0"), "0 replicas");
  assert.equal(choiceLabel(cap({ primitive: "replica_reduction" }), "1"), "1 replica");
  assert.equal(choiceLabel(cap({ primitive: "memory_limit" }), "32Mi"), "32Mi memory limit");
});

test("unavailable capabilities stay listed, after the usable ones", () => {
  const target: Target = { kind: "stateless", critical: true, policy: "actable", journeys: [], capabilities: [
    cap({ id: "image", family: "bad_deployment", available: false, reason: "no reviewed bad image for this service" }),
    cap({ id: "flag:b", available: false, reason: "flag not in the deployed flagd file" }),
    cap({ id: "flag:a", tested: false }), cap()] };
  const groups = byFamily(target);
  assert.deepEqual(groups.map((g) => g.family), ["bad_deployment", "broken_configuration"]);
  assert.deepEqual(groups[1].caps.map((c) => c.id), ["flag:paymentFailure", "flag:a", "flag:b"]);
  assert.deepEqual(byFamily(undefined), []);
});

test("the run's incident is the first opened while the fault was applied", () => {
  const before = incident(50), mine = incident(160), later = incident(900);
  const all = { [before.id]: before, [mine.id]: mine, [later.id]: later };
  const order = [later.id, mine.id, before.id];
  assert.equal(incidentFor(exp(), all, order)?.id, mine.id);
  assert.equal(incidentFor(exp({ ended_at: 150 }), all, order)?.id, mine.id);
  assert.equal(incidentFor(exp({ ended_at: 150 }), { [later.id]: later }, [later.id]), null);
  assert.equal(incidentFor(exp({ applied_at: null }), all, order), null);
  assert.equal(incidentFor(null, all, order), null);
});

test("applied, symptom and detected are separate states", () => {
  assert.equal(runState(exp(), null, null).label, "Fault live, no measurable symptom yet");
  assert.equal(runState(exp(), null, 130).label, "Fault live, symptom seen");
  assert.equal(runState(exp(), incident(160), 130).label, "Fault live, incident open");
  assert.equal(runState(exp({ status: "rejected" }), null, null).label, "Rejected, nothing changed");
  assert.equal(runState(exp({ status: "cleanup_required" }), null, null).tone, "bad");
  assert.equal(runState(exp({ status: "finished", healthy: null }), null, null).label, "Ended, health not checked");
  assert.equal(runState(exp({ status: "finished", healthy: true }), null, null).tone, "ok");
});

test("symptom is the first breach after the fault, not an older one", () => {
  const h = health({ services: {
    payment: { err_ratio: 0.4, p95_ms: 1, baseline_p95_ms: 1, breaching: true, first_breach_ts: 140, bad_pods: 0, unhealthy: true },
    cart: { err_ratio: 0, p95_ms: 1, baseline_p95_ms: 1, breaching: true, first_breach_ts: 40, bad_pods: 0, unhealthy: false } } });
  assert.equal(symptomAt(exp(), h, null), 140);
  assert.equal(symptomAt(exp(), health(), incident(160)), 140);
  assert.equal(symptomAt(exp(), health(), null), null);
});

test("milestones show one current step and never a step the backend did not confirm", () => {
  const fresh = milestones(exp(), null, null);
  assert.deepEqual(fresh.map((m) => m.state), ["done", "now", "todo", "todo", "todo", "todo", "todo"]);
  const inc = incident(160, ["tool_called", { tool: "get_pods" }, 165], ["tool_called", { tool: "get_recent_changes" }, 166],
    ["diagnosis_ready", { pattern: "recent_change", culprit: "payment" }, 180],
    ["approval_requested", { approval_id: "a1", expires_at: 500 }, 182]);
  const waiting = milestones(exp(), inc, 140);
  assert.deepEqual(waiting.map((m) => [m.key, m.state]), [["applied", "done"], ["symptom", "done"], ["detected", "done"],
    ["diagnosed", "done"], ["approval", "now"], ["acted", "todo"], ["closed", "todo"], ["ended", "todo"]]);
  assert.equal(waiting[3].note, "2 telemetry reads");
  assert.equal(waiting[4].note, "waiting in Discord");
  // stopped before Akira acted: the remaining steps are skipped, not shown as done
  const stopped = milestones(exp({ status: "verifying", ended_at: 200, ended_by: "judge_stop" }), inc, 140);
  assert.deepEqual(stopped.slice(4).map((m) => m.state), ["skip", "skip", "skip", "done"]);
  assert.equal(stopped.at(-1)?.note, "stopped by the judge");
});

// live, exp-30876b397e: the flag was back at +3m13s, Akira's verdict came at +5m15s after verification
test("a fault that ended before the verdict is listed before it", () => {
  const inc = incident(160, ["action_executed", { receipt_id: 3, tool: "revert_config", target: "payment" }, 290],
    ["incident_resolved", { card: { incident_id: "inc-160", status: "FIXED", text: "t", evidence_ids: [] }, prediction_held: true }, 415]);
  const done = milestones(exp({ status: "finished", ended_at: 293, ended_by: "repaired" }), inc, 150);
  assert.deepEqual(done.map((m) => m.key).slice(-3), ["acted", "ended", "closed"]);
  assert.ok(done.every((m, i) => i === 0 || m.at == null || done[i - 1].at == null || done[i - 1].at! <= m.at));
});

test("expiry, stop and reset are never credited to Akira", () => {
  const acted = incident(160, ["action_executed", { receipt_id: 3, tool: "revert_config", target: "payment" }, 220]);
  assert.equal(attribution(exp({ ended_by: "repaired", ended_at: 225 }), acted), "Akira's revert_config reversed the cause");
  assert.match(attribution(exp({ ended_by: "repaired", ended_at: 225 }), incident(160)), /outside Akira/);
  for (const by of ["expiry", "judge_stop", "reset"]) {
    assert.match(attribution(exp({ ended_by: by, ended_at: 225 }), acted), /Not credited to Akira/);
  }
  assert.equal(attribution(exp(), acted), "Fault still applied");
});

test("reveal puts the injected cause next to what Akira concluded, also when it found nothing", () => {
  const silent = Object.fromEntries(revealRows(exp({ ended_by: "expiry", ended_at: 1900, seed: 7 }), null).map((r) => [r.label, r.value]));
  assert.equal(silent["Injected cause"], "configmap/flagd-config flags[paymentFailure].defaultVariant: off -> 50%");
  assert.equal(silent["Akira's suspect"], "no incident opened");
  assert.equal(silent["Akira's action"], "none");
  assert.equal(silent.Seed, "7");
  const decoy = revealRows(exp({ mutations: [...exp().mutations!, { role: "decoy", place: "deployment/payment env PROMO_BANNER", before: null, injected: "autumn", state: "planned", after_s: 15 }] }), null);
  assert.equal(decoy[1].value, "deployment/payment env PROMO_BANNER: not set -> autumn (never applied)");
});

test("two faults at once: each run takes the incident about its own target", () => {
  const ad = { ...incident(150), id: "inc-ad", unhealthy: ["ad"] };
  const pay = { ...incident(170), id: "inc-pay" };
  const all = { [ad.id]: ad, [pay.id]: pay };
  assert.equal(incidentFor(exp(), all, [pay.id, ad.id])?.id, "inc-pay");  // payment run, not the earlier ad incident
  assert.equal(incidentFor(exp({ target: "ad" }), all, [pay.id, ad.id])?.id, "inc-ad");
  assert.equal(incidentFor(exp({ target: "email" }), all, [pay.id, ad.id])?.id, "inc-ad");  // no match: earliest
});
