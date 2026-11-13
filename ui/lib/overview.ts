// pure helpers for the Overview page and incident status; config text comes from lib/config.ts

import type { ServiceHealth } from "./chaos-api.ts";
import type { Incident, LiveState } from "./live.ts";

export interface Policy {
  errThreshold: number | null;
  latencyMultiplier: number | null;
  latencyFloorMs: number | null;
  maxAgeS: number | null;
}

export interface ServiceInfo { kind: string; critical: boolean; actable: boolean; protected: boolean }

const num = (text: string, key: string): number | null => {
  const m = text.match(new RegExp(`^\\s*${key}:\\s*([0-9.]+)`, "m"));
  return m ? Number(m[1]) : null;
};

// shortcut: reads four flat numeric keys from config/policy.yaml by regex, no YAML parser; upgrade if the keys nest
export function parsePolicy(text: string): Policy {
  return {
    errThreshold: num(text, "error_ratio_threshold"),
    latencyMultiplier: num(text, "latency_multiplier"),
    latencyFloorMs: num(text, "latency_floor_ms"),
    maxAgeS: num(text, "incident_max_age_seconds"),
  };
}

// shortcut: config/services.yaml rows are one-line flow maps (`name: {kind: x, critical: y, actable: z}`)
export function parseServices(text: string): Record<string, ServiceInfo> {
  const out: Record<string, ServiceInfo> = {};
  const row = /^ {2}([\w-]+):\s*\{([^}]*)\}/gm;
  for (const m of text.matchAll(row)) {
    const field = (k: string) => m[2].match(new RegExp(`${k}:\\s*([\\w-]+)`))?.[1];
    out[m[1]] = { kind: field("kind") ?? "unknown", critical: field("critical") === "true", actable: field("actable") === "true",
      protected: field("protected") === "true" };
  }
  return out;
}

// unknown: monitoring is blind or stale, so the last numbers prove nothing. nodata: no measurement at all.
// Neither is "ok": only a fresh reading inside the limits is
export type ServiceStatus = "unhealthy" | "breaching" | "ok" | "nodata" | "unknown";

export function serviceStatus(s: ServiceHealth | undefined, blind = false): ServiceStatus {
  if (blind) return "unknown";
  if (!s) return "nodata";
  if (s.unhealthy) return "unhealthy";
  if (s.breaching) return "breaching";
  if (s.err_ratio == null && s.p95_ms == null) return "nodata";
  return "ok";
}

// the observer's latency rule: p95 above multiplier × baseline AND at least floor ms above it
export function latencyLimit(base: number | null, p: Policy): number | null {
  if (base == null || p.latencyMultiplier == null) return null;
  return Math.max(p.latencyMultiplier * base, base + (p.latencyFloorMs ?? 0));
}

// one line per service card, worst news first
export function serviceSentence(s: ServiceHealth | undefined, p: Policy, blind = false): string {
  const st = serviceStatus(s, blind);
  if (st === "unknown") return "Monitoring unavailable; health unknown.";
  if (!s) return "No reading for this service; health unknown.";
  if (st === "nodata") return "No requests measured in the last window; health not proven.";
  const parts: string[] = [];
  if (p.errThreshold != null && s.err_ratio != null && s.err_ratio > p.errThreshold) {
    parts.push(`errors ${(s.err_ratio * 100).toFixed(1)}%, over the ${(p.errThreshold * 100).toFixed(0)}% line`);
  }
  const limit = latencyLimit(s.baseline_p95_ms, p);
  if (limit != null && s.p95_ms != null && s.p95_ms > limit) parts.push(`p95 ${Math.round(s.p95_ms)} ms, limit ${Math.round(limit)} ms`);
  if (s.bad_pods > 0) parts.push(`${s.bad_pods} pod${s.bad_pods === 1 ? "" : "s"} not ready`);
  if (parts.length) return `${parts.join("; ")}.`.replace(/^./, (c) => c.toUpperCase());
  // the observer says it is over a limit even when our own copy of the limits does not show which
  if (st !== "ok") return "Over a limit the observer measured.";
  return "Inside its error and latency baselines.";
}

export type IncidentStatus = "open" | "resolved" | "escalated" | "handed_off" | "lost";

// an incident with no terminal event past the observer's max age was closed without one reaching the bus
export function incidentStatus(inc: Incident, now: number, maxAgeS: number | null): IncidentStatus {
  if (inc.outcome) return inc.outcome;
  return maxAgeS != null && now - inc.openedAt > maxAgeS ? "lost" : "open";
}

// what "resolved" really proved. verified: recovery matched the prediction made before the fix.
// unproven: the shop recovered, the cause was not proven. mitigated: a restart bought time, the cause stays
export type Verdict = "verified" | "unproven" | "mitigated";

export function verdict(inc: Incident): Verdict | null {
  if (inc.outcome !== "resolved") return null;
  const status = inc.card?.status ?? "";
  if (status.startsWith("MITIGATED")) return "mitigated";
  return inc.predictionHeld === true || status.startsWith("FIXED") ? "verified" : "unproven";
}

export const VERDICT: Record<Verdict, { label: string; tone: "ok" | "warn"; phrase: string }> = {
  verified: { label: "Fix verified", tone: "ok", phrase: "fixed" },
  unproven: { label: "Recovered, cause unproven", tone: "warn", phrase: "recovered, fix not proven" },
  mitigated: { label: "Mitigated, not fixed", tone: "warn", phrase: "mitigated, permanent fix needed" },
};

export interface IncidentStats {
  total: number; open: number; resolved: number; verified: number; escalated: number; handedOff: number; lost: number;
  medianFixS: number | null;
}

export function incidentStats(state: LiveState, now: number, maxAgeS: number | null): IncidentStats {
  const out: IncidentStats = { total: 0, open: 0, resolved: 0, verified: 0, escalated: 0, handedOff: 0, lost: 0, medianFixS: null };
  const fix: number[] = [];
  for (const id of state.order) {
    const inc = state.incidents[id];
    out.total += 1;
    const st = incidentStatus(inc, now, maxAgeS);
    if (st === "handed_off") out.handedOff += 1;
    else out[st] += 1;
    if (verdict(inc) === "verified") out.verified += 1;
    if (st === "resolved" && inc.closedAt != null) fix.push(inc.closedAt - inc.openedAt);
  }
  if (fix.length) {
    fix.sort((a, b) => a - b);
    const mid = Math.floor(fix.length / 2);
    out.medianFixS = fix.length % 2 ? fix[mid] : (fix[mid - 1] + fix[mid]) / 2;
  }
  return out;
}
