import type { HealthNow } from "./chaos-api.ts";
import { duration } from "./format.ts";
import type { Incident } from "./live.ts";

// chaos lab: types of the experiment API (chaos/experiments.py, chaos/registry.py) and the pure
// wording around them. Nothing here predicts what Akira will do.

export interface Capability {
  id: string;
  primitive: "flag_variant" | "bad_image" | "broken_env" | "scale_zero";
  family: string;
  label: string;
  field: { kind: string; name: string; key: string | null };
  choices: string[];
  values: Record<string, unknown>;
  meaning: Record<string, unknown>;
  current: unknown;
  available: boolean;
  reason: string | null;
  tested: boolean;
  unit: string | null;
  what: string | null;
  decoy: boolean;
}

export type Standing = "actable" | "approval_only" | "watch_only" | "unwatched";

export interface Target { kind: string | null; critical: boolean; policy: Standing; journeys: string[]; capabilities: Capability[] }

export interface Baseline { ok: boolean | null; reason: string | null; severity?: number; age_s?: number }

export interface Limits { max_active: number; max_delay_s: number; min_duration_s: number; max_duration_s: number; max_lifetime_s: number }

export interface Registry {
  version: number;
  limits: Limits;
  decoy: { env: string; value: string; gap_s: number };
  targets: Record<string, Target>;
  pending_review: string[];
  baseline: Baseline;
  open: Experiment[];
}

export interface Spec {
  target: string;
  capability: string;
  choice: string;
  delay_s: number;
  duration_s: number | null;
  decoy: boolean;
  blind: boolean;
  skip_baseline: boolean;
}

export interface DrawOptions { seed: number | null; blind: boolean; decoy: boolean; tested_only: boolean }

export interface Change { role: "fault" | "decoy"; place: string; before: unknown; after: unknown; after_s: number }

export interface Preview {
  ok: boolean;
  problems: string[];
  changes: Change[];
  family: string | null;
  tested: boolean;
  journeys: string[];
  target_policy: Standing | null;
  ends_after_s: number;
  baseline: Baseline;
}

export interface Mutation { role: "fault" | "decoy"; place: string; before: unknown; injected: unknown; state: string; after_s: number }

export type RunStatus = "scheduled" | "applying" | "active" | "cleanup_required" | "verifying" | "finished" | "needs_operator" | "rejected";

export interface Experiment {
  id: string;
  status: RunStatus;
  spec: Spec | null;
  target: string | null;
  hidden: boolean;
  legacy: boolean;
  seed: number | null;
  family: string | null;
  created_at: number;
  start_at: number;
  applied_at: number | null;
  expires_at: number | null;
  ended_at: number | null;
  ended_by: string | null;
  error: string | null;
  revealed: boolean;
  healthy: boolean | null;
  mutations: Mutation[] | null;
}

export const OPEN: RunStatus[] = ["scheduled", "applying", "active", "cleanup_required", "verifying"];

export const FAMILY: Record<string, string> = {
  bad_deployment: "Bad deployment",
  broken_configuration: "Broken configuration",
  resource_exhaustion: "Resource exhaustion",
  dependency_failure: "Failing dependency",
  workload_change: "Workload change",
};

// what Akira may do to this target, from config/services.yaml
export const STANDING: Record<Standing, { label: string; hint: string }> = {
  actable: { label: "Akira may act", hint: "inside policy, after its safety checks" },
  approval_only: { label: "Approval only", hint: "protected data store: a human approves every change" },
  watch_only: { label: "Watch only", hint: "Akira diagnoses but never changes it; expect an escalation" },
  unwatched: { label: "Not watched", hint: "the observer has no readings for it" },
};

const show = (v: unknown): string => (v == null ? "not set" : typeof v === "string" ? v : JSON.stringify(v));

export const value = show;

// one intensity choice, in the judge's words, with its real meaning
export function choiceLabel(cap: Capability, choice: string): string {
  if (cap.primitive === "flag_variant") {
    const real = cap.meaning[choice];
    const same = String(real) === choice || real === true;
    return same ? choice : `${choice} (flag value ${show(real)})`;
  }
  if (cap.primitive === "broken_env") return `${choice.replace("_", " ")}: ${show(cap.values[choice])}`;
  if (cap.primitive === "scale_zero") return "0 replicas";
  return choice;
}

// capabilities of one target, grouped by failure family, usable ones first
export function byFamily(target: Target | undefined): { family: string; caps: Capability[] }[] {
  const groups = new Map<string, Capability[]>();
  for (const cap of target?.capabilities ?? []) groups.set(cap.family, [...(groups.get(cap.family) ?? []), cap]);
  return [...groups].map(([family, caps]) => ({
    family,
    caps: [...caps].sort((a, b) => Number(b.available) - Number(a.available) || Number(b.tested) - Number(a.tested)),
  }));
}

export interface Telemetry { state: "fresh" | "stale" | "blind" | "offline" | "waiting"; text: string; ok: boolean }

const STALE_S = 30;

// can the numbers on this page be trusted right now? an answer with old numbers is not fresh
export function telemetry(health: HealthNow | null, error: string | null, now: number): Telemetry {
  if (!health) return error ? { state: "offline", text: `Observer unreachable (${error}); health unknown`, ok: false }
    : { state: "waiting", text: "Waiting for the first reading", ok: false };
  const age = Math.max(0, now - (health.last_ok_ts ?? health.ts));
  if (health.prometheus_ok === false) {
    return { state: "blind", text: `Monitoring unavailable; health unknown. Last good reading ${health.last_ok_ts ? `${duration(age)} ago` : "never"}`, ok: false };
  }
  if (error || age > STALE_S) return { state: "stale", text: `Readings are ${duration(age)} old; health unknown`, ok: false };
  return { state: "fresh", text: `Monitoring fresh, read ${duration(age)} ago`, ok: true };
}

// the incident this run caused: the first one opened while the fault was applied
export function incidentFor(exp: Experiment | null, incidents: Record<string, Incident>, order: string[]): Incident | null {
  if (!exp?.applied_at) return null;
  const from = exp.applied_at;
  const until = exp.ended_at == null ? Infinity : exp.ended_at + 120;
  const hits = order.map((id) => incidents[id]).filter((i) => i && i.openedAt != null && i.openedAt >= from && i.openedAt <= until);
  return hits.sort((a, b) => (a.openedAt ?? 0) - (b.openedAt ?? 0))[0] ?? null;
}

// first breach of any service after the fault landed: the symptom, before Akira calls it an incident
export function symptomAt(exp: Experiment, health: HealthNow | null, incident: Incident | null): number | null {
  if (!exp.applied_at) return null;
  const breaches = Object.values(health?.services ?? {})
    .map((s) => s.first_breach_ts).filter((t): t is number => t != null && t >= exp.applied_at!);
  if (incident?.onsetAt != null && incident.onsetAt >= exp.applied_at) breaches.push(incident.onsetAt);
  return breaches.length ? Math.min(...breaches) : null;
}

export type Tone = "bad" | "warn" | "ok" | "idle" | "accent";

// where the run stands, never ahead of what the backend confirmed
export function runState(exp: Experiment, incident: Incident | null, symptom: number | null): { label: string; tone: Tone } {
  switch (exp.status) {
    case "rejected": return { label: "Rejected, nothing changed", tone: "idle" };
    case "scheduled": return { label: "Scheduled, not applied yet", tone: "idle" };
    case "applying": return { label: "Applying", tone: "warn" };
    case "cleanup_required": return { label: "Partly applied, cleaning up", tone: "bad" };
    case "needs_operator": return { label: "Needs an operator", tone: "bad" };
    case "verifying": return { label: "Fault ended, checking recovery", tone: "warn" };
    case "finished": return exp.healthy === true ? { label: "Ended, shop healthy", tone: "ok" }
      : { label: "Ended, health not checked", tone: "idle" };
    default:
      if (incident) return { label: "Fault live, incident open", tone: "accent" };
      return symptom != null ? { label: "Fault live, symptom seen", tone: "warn" }
        : { label: "Fault live, no measurable symptom yet", tone: "idle" };
  }
}

export interface Milestone { key: string; label: string; at: number | null; state: "done" | "now" | "todo" | "skip"; note?: string }

const first = (incident: Incident | null, ...types: string[]): number | null =>
  incident?.events.find((e) => types.includes(e.type))?.ts ?? null;

// the run as separate, timed facts: applied is not symptom, symptom is not detected, action is not recovery
export function milestones(exp: Experiment, incident: Incident | null, symptom: number | null): Milestone[] {
  const reads = incident?.events.filter((e) => e.type === "tool_called" || (e.type === "llm_called" && e.payload.tool)).length ?? 0;
  const diagnosed = first(incident, "diagnosis_ready");
  const asked = first(incident, "approval_requested");
  const decided = first(incident, "approval_decided");
  const acted = incident?.action?.ts ?? null;
  const closed = incident?.closedAt ?? null;
  const steps: Omit<Milestone, "state">[] = [
    { key: "applied", label: "Fault applied", at: exp.applied_at },
    { key: "symptom", label: "Symptom measured", at: symptom },
    { key: "detected", label: "Incident opened", at: incident?.openedAt ?? null },
    { key: "diagnosed", label: "Investigated", at: diagnosed, note: reads ? `${reads} telemetry reads` : undefined },
    ...(asked != null ? [{ key: "approval", label: "Human approval", at: decided,
      note: decided == null ? "waiting in Discord" : (incident?.approval?.decision ?? undefined) }] : []),
    { key: "acted", label: "Action executed", at: acted, note: incident?.action ? `${incident.action.tool} ${incident.action.target}` : undefined },
    { key: "closed", label: "Akira's verdict", at: closed, note: incident?.outcome ? incident.outcome.replace("_", " ") : undefined },
    { key: "ended", label: "Fault ended", at: exp.ended_at, note: exp.ended_by ? ENDED[exp.ended_by] ?? exp.ended_by : undefined },
  ];
  // the list reads top to bottom in time: a fault that ended before Akira's verdict goes above it
  if (exp.ended_at != null && closed != null && exp.ended_at < closed) {
    const ended = steps.pop()!;
    steps.splice(steps.findIndex((s) => s.key === "closed"), 0, ended);
  }
  const over = !OPEN.includes(exp.status);
  let live = !over;
  return steps.map((s) => {
    if (s.at != null) return { ...s, state: "done" as const };
    if (over || exp.ended_at != null) return { ...s, state: "skip" as const };
    const state = live ? "now" as const : "todo" as const;
    live = false;
    return { ...s, state };
  });
}

const ENDED: Record<string, string> = {
  repaired: "cause reversed",
  changed: "field changed to a third value",
  judge_stop: "stopped by the judge",
  expiry: "expired, cleaned up by the lab",
  reset: "full reset",
  error: "injection failed part way",
};

// who gets credit for the fault ending. Expiry, stop and reset are never Akira's success
export function attribution(exp: Experiment, incident: Incident | null): string {
  if (!exp.ended_by) return "Fault still applied";
  if (exp.ended_by === "repaired") {
    const acted = incident?.action?.ts;
    return acted != null && exp.ended_at != null && acted <= exp.ended_at + 15
      ? `Akira's ${incident!.action!.tool} reversed the cause`
      : "Reversed outside Akira (a human, or a tool Akira did not report)";
  }
  if (exp.ended_by === "expiry") return "The run expired and the lab restored the field. Not credited to Akira";
  if (exp.ended_by === "judge_stop") return "You stopped the run and the lab restored the field. Not credited to Akira";
  if (exp.ended_by === "reset") return "A full reset restored the shop. Not credited to Akira";
  return ENDED[exp.ended_by] ?? exp.ended_by;
}

export interface RevealRow { label: string; value: string }

// what was injected next to what Akira concluded; rows stay even when Akira was wrong or silent
export function revealRows(exp: Experiment, incident: Incident | null): RevealRow[] {
  const rows: RevealRow[] = [];
  for (const m of exp.mutations ?? []) {
    rows.push({ label: m.role === "decoy" ? "Decoy change (harmless)" : "Injected cause",
      value: `${m.place}: ${show(m.before)} -> ${show(m.injected)}${m.state === "planned" ? " (never applied)" : ""}` });
  }
  rows.push({ label: "Failure family", value: exp.family ? FAMILY[exp.family] ?? exp.family : "unknown" });
  rows.push({ label: "Akira's suspect", value: incident ? incident.culprit ?? "none named" : "no incident opened" });
  rows.push({ label: "Akira's action", value: incident?.action ? `${incident.action.tool} on ${incident.action.target}`
    : incident?.outcome ? "none; it handed the incident to a human" : incident ? "none yet" : "none" });
  rows.push({ label: "Akira's verdict", value: incident?.card?.status ?? (incident?.outcome ? incident.outcome.replace("_", " ") : "none") });
  rows.push({ label: "Why the fault ended", value: attribution(exp, incident) });
  if (exp.seed != null) rows.push({ label: "Seed", value: String(exp.seed) });
  return rows;
}

// a fresh key per press of Start
export function runKey(): string {
  return `lab-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
