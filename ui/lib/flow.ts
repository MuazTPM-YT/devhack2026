// how one incident moves through the real services: each bus event becomes a path between components
// (flow map) and a plain sentence (timeline). Pure functions, fed by Incident.events from live.ts.

import { type IncidentEvent, STAGE_OF, STAGES, type Stage } from "./live.ts";

export type NodeId = "shop" | "observer" | "brain" | "llm" | "gateway" | "notifier" | "k8s" | "verifier";
export type NodeState = "idle" | "done" | "active" | "failed";
export type Tone = "info" | "ok" | "warn" | "bad";

export const NODES: Record<NodeId, { title: string; sub: string }> = {
  shop: { title: "Shop telemetry", sub: "Prometheus · Jaeger" },
  observer: { title: "Observer", sub: ":7001 · detect" },
  brain: { title: "Brain", sub: ":7002 · diagnose" },
  llm: { title: "Model", sub: "OpenCode Go" },
  gateway: { title: "Gateway", sub: ":7003 · checklist" },
  notifier: { title: "Notifier", sub: "Discord · humans" },
  k8s: { title: "Kubernetes", sub: "namespace shop" },
  verifier: { title: "Verifier", sub: "watch · undo" },
};

// what really travels on each link (shown on hover and under the map)
export const EDGE_LABEL: Record<string, string> = {
  "shop>observer": "PromQL every 5 s",
  "observer>brain": "POST /incidents",
  "shop>brain": "Jaeger traces + dependency graph",
  "brain>llm": "redacted evidence bundle",
  "llm>brain": "diagnosis + prediction",
  "brain>gateway": "MCP tool call (/mcp)",
  "gateway>notifier": "event bus → Discord card",
  "notifier>gateway": "POST /approvals/{id}/decide",
  "gateway>k8s": "patch as agent (dry run first)",
  "k8s>gateway": "dry-run diff",
  "observer>verifier": "GET /health/now",
  "verifier>k8s": "apply the receipt's inverse",
  "k8s>verifier": "spec hashes for the harm check",
};

const TERMINAL = new Set(["incident_resolved", "escalated", "handed_off"]);
const BRAIN_SIDE = new Set<NodeId>(["brain", "llm"]);

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const list = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);
const words = (s: string) => s.replace(/_/g, " ");

// the components an event passed through, in order; one entry = work inside that component
export function pathOf(ev: IncidentEvent, prev: IncidentEvent | null): NodeId[] {
  const p = ev.payload;
  switch (ev.type) {
    case "incident_opened":
    case "alerts_grouped":
      return ["shop", "observer", "brain"];
    case "culprit_found":
      return ["shop", "brain"];
    case "llm_called":
      return p.cached === true ? ["brain"] : ["brain", "llm", "brain"];
    case "checklist_step":
      if (p.name === "dry_run") return ["gateway", "k8s", "gateway"];
      return prev?.type === "checklist_step" ? ["gateway"] : ["brain", "gateway"];
    case "approval_requested":
      return ["gateway", "notifier"];
    case "approval_decided":
      return ["notifier", "gateway"];
    case "action_executed":
    case "blocked":
      return ["gateway", "k8s"];
    case "verify_tick":
      return ["observer", "verifier"];
    case "early_abort":
      return ["verifier"];
    case "action_undone":
      return ["verifier", "k8s"];
    case "harm_check":
      return ["k8s", "verifier"];
  }
  if (TERMINAL.has(ev.type)) {
    // the brain escalates itself when no safe action exists; everything else ends in the gateway
    const from = prev ? pathOf(prev, null).at(-1) : null;
    return from && BRAIN_SIDE.has(from) ? ["brain", "gateway", "notifier"] : ["gateway", "notifier"];
  }
  return ["brain"]; // major_incident, bundle_built, rule_matched, diagnosis_ready, injection_quarantined
}

// a failed gate that hands the action to a human (trust gate, or net benefit / freshness asking first),
// or a human's own no: neither is a fault in the gateway
function asksHuman(ev: IncidentEvent, next: IncidentEvent | null): boolean {
  return ev.payload.name === "trust_gate" || ev.payload.name === "approval" || next?.type === "approval_requested";
}

// the component that went wrong on this event, if any
export function failedAt(ev: IncidentEvent, next: IncidentEvent | null = null): NodeId | null {
  const p = ev.payload;
  if (ev.type === "checklist_step" && p.passed === false) return asksHuman(ev, next) ? null : "gateway";
  if (ev.type === "blocked") return "k8s";
  if (ev.type === "early_abort" || ev.type === "action_undone") return "verifier";
  if (ev.type === "llm_called" && str(p.error)) return "llm";
  if (ev.type === "harm_check" && p.clean === false) return "verifier";
  return null;
}

export interface Line { title: string; detail: string | null; tone: Tone }

// one human sentence per event; detail is the second line under it
export function describe(ev: IncidentEvent, next: IncidentEvent | null = null): Line {
  const p = ev.payload;
  const line = (title: string, detail: string | null = null, tone: Tone = "info"): Line => ({ title, detail, tone });
  switch (ev.type) {
    case "incident_opened": {
      const bad = list(p.unhealthy);
      return line(`Incident opened · ${bad.length} unhealthy`, [bad.join(", "), num(p.severity) != null ? `severity ${num(p.severity)}` : null].filter(Boolean).join(" · ") || null, "warn");
    }
    case "alerts_grouped":
      return line("Alert folded into this incident", list(p.unhealthy).join(", ") || null, "warn");
    case "culprit_found": {
      const culprit = str(p.culprit);
      const how = p.from_traces === true ? "from error traces" : "deepest unhealthy service";
      const moved = str(p.moved_from) ? ` · moved from ${str(p.moved_from)} (dependency change)` : "";
      const victims = list(p.victims);
      return culprit
        ? line(`Culprit: ${culprit}`, `${how}${moved}${victims.length ? ` · victims ${victims.join(", ")}` : ""}`)
        : line("No culprit found", how, "warn");
    }
    case "major_incident": {
      const ranked = Array.isArray(p.ranked) ? (p.ranked as Record<string, unknown>[]) : [];
      const top = ranked[0];
      return line(`Major incident${p.regrouped === true ? " (after regroup)" : ""}`,
        top ? `shared cause: ${str(top.target) ?? "?"} (${words(str(top.kind) ?? "unknown")})` : "no shared cause ranked", "warn");
    }
    case "bundle_built": {
      const parts = ["changes", "metrics", "traces", "events", "logs"].map((k) => `${num(p[k]) ?? 0} ${k}`);
      return line("Evidence bundle built, redacted", parts.join(" · "));
    }
    case "rule_matched": {
      const tools = list(p.tools);
      return line(`Rule matched: ${words(str(p.pattern) ?? "unknown")}`, tools.length ? `proposes ${tools.join(", ")}` : "no safe action for this pattern", tools.length ? "info" : "warn");
    }
    case "injection_quarantined":
      return line("Log line quarantined", "looked like an instruction; kept out of the model prompt", "warn");
    case "llm_called": {
      if (str(p.error)) return line("Model call failed", words(str(p.error)!), "bad");
      if (p.cached === true) return line("Used cached diagnosis", "same evidence seen before");
      const usage = (p.usage ?? {}) as Record<string, unknown>;
      const tokens = num(usage.total_tokens);
      const bits = [str(p.model), num(p.attempt) != null ? `attempt ${num(p.attempt)}` : null, tokens != null ? `${tokens} tokens` : null];
      return line("Model answered", bits.filter(Boolean).join(" · ") || null);
    }
    case "diagnosis_ready":
      return line(`Diagnosis: ${words(str(p.pattern) ?? "unknown")}`, str(p.culprit) ? `on ${str(p.culprit)}` : null);
    case "checklist_step": {
      const name = words(str(p.name) ?? "?");
      if (p.passed === true) return line(`Gate passed: ${name}`, str(p.reason), "ok");
      const ask = asksHuman(ev, next);
      return line(`${ask ? "Gate needs a human" : "Gate failed"}: ${name}`, str(p.reason), ask ? "warn" : "bad");
    }
    case "approval_requested":
      return line("Asked a human for approval", [str(p.diff), str(p.forecast)].filter(Boolean).join(" · ") || null, "warn");
    case "approval_decided": {
      const d = str(p.decision) ?? "decided";
      return line(`Approval ${d}`, null, d === "approved" ? "ok" : "bad");
    }
    case "action_executed":
      return line(`Executed ${str(p.tool) ?? "?"} on ${str(p.target) ?? "?"}`,
        [num(p.receipt_id) != null ? `receipt #${num(p.receipt_id)}` : null, str(p.tier) ? `tier ${str(p.tier)}` : null].filter(Boolean).join(" · ") || null, "ok");
    case "blocked":
      return line(`Blocked by the API server${str(p.step) ? ` at ${words(str(p.step)!)}` : ""}`, str(p.reason), "bad");
    case "verify_tick":
      return line(`Health check · severity ${num(p.severity) ?? "?"}`, p.recovered === true ? "recovered" : null, p.recovered === true ? "ok" : "info");
    case "early_abort":
      return line("Early abort: severity rose", `${num(p.before) ?? "?"} → ${num(p.severity) ?? "?"}`, "bad");
    case "action_undone":
      return line(`Undid receipt #${num(p.receipt_id) ?? "?"}`, str(p.reason), "bad");
    case "harm_check":
      return p.clean === true ? line("Harm check clean", "nothing else changed or got worse", "ok")
        : line("Harm check found side effects", null, "bad");
    case "incident_resolved":
      return line("Resolved", str(p.briefing), "ok");
    case "escalated":
      return line("Escalated to a human", str(p.briefing), "bad");
    case "handed_off":
      return line("Handed off to a human", str(p.briefing), "warn");
  }
  return line(words(ev.type));
}

export interface NodeView { state: NodeState; count: number; last: Line | null }
export interface FlowView {
  nodes: Record<NodeId, NodeView>;
  edges: Record<string, number>; // "a>b" -> times a pulse went that way
  path: NodeId[]; // the focused event's path, for the pulse
  focus: IncidentEvent | null;
}

// state of every component after events[0..upto]; the focused event's components are active while open
export function flowAt(events: IncidentEvent[], upto: number, open: boolean): FlowView {
  const nodes = Object.fromEntries(
    (Object.keys(NODES) as NodeId[]).map((id) => [id, { state: "idle", count: 0, last: null }]),
  ) as Record<NodeId, NodeView>;
  const edges: Record<string, number> = {};
  const end = Math.min(upto, events.length - 1);
  let path: NodeId[] = [];
  for (let i = 0; i <= end; i++) {
    const ev = events[i];
    path = pathOf(ev, i ? events[i - 1] : null);
    const next = events[i + 1] ?? null;
    const line = describe(ev, next);
    // every component the event reached takes its line; the sender only lights up
    const reached = new Set(path.length === 1 ? path : path.slice(1));
    path.forEach((id, k) => {
      if (nodes[id].state !== "failed") nodes[id].state = "done";
      if (k) edges[`${path[k - 1]}>${id}`] = (edges[`${path[k - 1]}>${id}`] ?? 0) + 1;
    });
    reached.forEach((id) => { nodes[id].count += 1; nodes[id].last = line; });
    const bad = failedAt(ev, next);
    if (bad) nodes[bad].state = "failed";
  }
  const focus = end >= 0 ? events[end] : null;
  if (focus && open) path.forEach((id) => { if (nodes[id].state !== "failed") nodes[id].state = "active"; });
  return { nodes, edges, path: focus ? path : [], focus };
}

export type Row =
  | { kind: "event"; ev: IncidentEvent; index: number }
  | { kind: "ticks"; first: IncidentEvent; last: IncidentEvent; count: number; index: number };

// consecutive verify ticks collapse into one row (a window polls every few seconds)
export function rows(events: IncidentEvent[]): Row[] {
  const out: Row[] = [];
  events.forEach((ev, index) => {
    const prev = out.at(-1);
    if (ev.type === "verify_tick" && prev && (prev.kind === "ticks" || prev.ev.type === "verify_tick")) {
      if (prev.kind === "ticks") out[out.length - 1] = { ...prev, last: ev, count: prev.count + 1, index };
      else out[out.length - 1] = { kind: "ticks", first: prev.ev, last: ev, count: 2, index };
      return;
    }
    out.push({ kind: "event", ev, index });
  });
  return out;
}

export type Phase = Stage | "outcome";
export const PHASES: Phase[] = [...STAGES, "outcome"];

export function phaseOf(type: string): Phase {
  if (TERMINAL.has(type)) return "outcome";
  if (type === "injection_quarantined") return "diagnose";
  if (type === "blocked") return "check";
  return STAGE_OF[type] ?? "diagnose";
}

// when each stage started and how long it ran (until the next stage's first event, or `now` if still running)
export function stageTimes(events: IncidentEvent[], now: number): Partial<Record<Phase, { start: number; took: number }>> {
  const starts: [Phase, number][] = [];
  for (const ev of events) {
    const phase = phaseOf(ev.type);
    if (!starts.some(([p]) => p === phase)) starts.push([phase, ev.ts]);
  }
  const out: Partial<Record<Phase, { start: number; took: number }>> = {};
  starts.forEach(([phase, start], i) => {
    const end = phase === "outcome" ? start : (starts[i + 1]?.[1] ?? now);
    out[phase] = { start, took: Math.max(0, end - start) };
  });
  return out;
}
