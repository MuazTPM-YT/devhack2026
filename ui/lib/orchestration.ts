// orchestration run mode for the UI (gateway GET /orchestration/status); pure helpers, tested in node
import type { Incident, LiveState } from "./live.ts";
import { incidentStatus } from "./overview.ts";

export interface OrchestrationStatus {
  mode: "disabled" | "shadow" | "coordinated";
  delegation_enabled: boolean;
  max_active_commanders: number;
  max_model_requests: number;
  phases: Record<string, number>;
  specialists_running: number;
  unknown_writes: number;
}

export type ModeTone = "idle" | "accent" | "warn" | "bad";

// one tag for the page header: which path handles incidents right now
export function modeLabel(s: OrchestrationStatus | null): { label: string; tone: ModeTone; title: string } | null {
  if (!s) return null;
  if (s.unknown_writes > 0) {
    return { label: `${s.unknown_writes} fix outcome unknown`, tone: "bad",
      title: "A write got no answer. Nothing else runs until an approver checks the cluster and clears it." };
  }
  if (s.mode === "disabled") return { label: "Single agent", tone: "idle", title: "One incident at a time, the classic path." };
  if (s.mode === "shadow") return { label: "Shadow grouping", tone: "warn", title: "Classic path acts; grouping decisions are only recorded." };
  const open = Object.values(s.phases).reduce((a, b) => a + b, 0);
  return {
    label: `Coordinated · ${s.delegation_enabled ? "specialists on" : "specialists off"}${open ? ` · ${open} open` : ""}`,
    tone: "accent",
    title: `Each cause gets its own investigation (up to ${s.max_active_commanders} at once, ${s.max_model_requests} model requests each).`,
  };
}

// the row line under an incident in the list: how many services, why grouped, where its fix stands
export function orchSummary(inc: Incident): string | null {
  const o = inc.orch;
  if (!o) return null;
  const parts: string[] = [];
  if (o.services.length) parts.push(`${o.services.length} service${o.services.length === 1 ? "" : "s"}`);
  const why = o.reasons.find((r) => r === "shared_dependency" || r === "shared_change");
  if (why) parts.push(why === "shared_dependency" ? "shared dependency" : "shared change");
  if (o.related.length) parts.push(`${o.related.length} related`);
  const fix = Object.values(o.intents).at(-1)?.status;
  if (fix === "queued") parts.push("fix queued");
  else if (fix === "execution_unknown") parts.push("fix outcome unknown");
  const running = Object.values(o.tasks).filter((t) => t.state === "running").length;
  if (running) parts.push("specialist on it");
  return parts.length ? parts.join(" · ") : null;
}

// "dependency:payment" -> "cause: payment"; reason codes read as words
export function reasonText(reason: string): string {
  const at = reason.indexOf(":");
  const kind = at < 0 ? reason : reason.slice(0, at);
  const rest = at < 0 ? "" : reason.slice(at + 1);
  if (rest && (kind === "dependency" || kind === "change")) return `${kind === "dependency" ? "cause" : "change"}: ${rest}`;
  return reason.replace(/_/g, " ");
}

// every incident still open, newest first (coordinated mode can hold several; the classic path one)
export function openIncidentIds(state: LiveState, now: number, maxAgeS: number | null): string[] {
  return state.order.filter((id) => incidentStatus(state.incidents[id], now, maxAgeS) === "open");
}

// the open incident that names this service as its culprit, if any
export function culpritIncident(state: LiveState, openIds: string[], service: string): string | null {
  return openIds.find((id) => state.incidents[id].culprit === service) ?? null;
}

