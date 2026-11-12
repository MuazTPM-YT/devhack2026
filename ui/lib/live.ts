// one reducer for everything the live page shows; fed by gateway SSE records (plan §6.8)

export type Stage = "detect" | "group" | "diagnose" | "check" | "act" | "verify";
export type StageState = "idle" | "active" | "done" | "failed";
export const STAGES: Stage[] = ["detect", "group", "diagnose", "check", "act", "verify"];

export type Outcome = "resolved" | "escalated" | "handed_off";

// schemas/models.py EventType; the gateway sends each as a named SSE event
export const EVENT_TYPES = [
  "incident_opened", "alerts_grouped", "culprit_found", "major_incident", "bundle_built",
  "rule_matched", "llm_called", "diagnosis_ready", "checklist_step", "approval_requested",
  "approval_decided", "action_executed", "verify_tick", "early_abort", "action_undone",
  "harm_check", "incident_resolved", "escalated", "handed_off", "injection_quarantined", "blocked",
] as const;

// one SSE data line from gateway /events
export interface BusRecord {
  seq: number;
  ts: number;
  event: { type: string; incident_id?: string | null; payload?: Record<string, unknown> };
}

export interface Step { name: string; passed: boolean; reason: string | null; ts: number }
export interface Tick { ts: number; severity: number | null; recovered: boolean }
export interface Card { status: string; text: string; evidence_ids: string[] }

export interface Incident {
  id: string;
  openedAt: number;
  onsetAt: number | null;
  severityAtOpen: number | null;
  unhealthy: string[];
  groupings: number;
  culprit: string | null;
  victims: string[];
  fromTraces: boolean | null;
  bundle: Record<string, number>;
  pattern: string | null;
  tools: string[];
  llmCalls: number;
  checklist: Step[];
  approval: { id: string; forecast: string; diff: string; expiresAt: number; decision: string | null } | null;
  action: { receiptId: number; tool: string; target: string; ts: number } | null;
  ticks: Tick[];
  harmClean: boolean | null;
  outcome: Outcome | null;
  closedAt: number | null;
  card: Card | null;
  briefing: string;
  quarantined: number;
  blocked: number;
  stages: Record<Stage, StageState>;
}

export interface LiveState {
  lastSeq: number;
  current: string | null;
  incidents: Record<string, Incident>;
  order: string[];
  feed: { seq: number; ts: number; type: string; incidentId: string | null }[];
}

export const initialState: LiveState = { lastSeq: 0, current: null, incidents: {}, order: [], feed: [] };

const FEED_SIZE = 40;

// which stage each event type lights up
const STAGE_OF: Record<string, Stage> = {
  incident_opened: "detect",
  alerts_grouped: "group",
  major_incident: "group",
  culprit_found: "diagnose",
  bundle_built: "diagnose",
  rule_matched: "diagnose",
  llm_called: "diagnose",
  diagnosis_ready: "diagnose",
  checklist_step: "check",
  approval_requested: "act",
  approval_decided: "act",
  action_executed: "act",
  verify_tick: "verify",
  early_abort: "verify",
  action_undone: "verify",
  harm_check: "verify",
};

const TERMINAL: Record<string, Outcome> = {
  incident_resolved: "resolved",
  escalated: "escalated",
  handed_off: "handed_off",
};

function blank(id: string, ts: number): Incident {
  return {
    id, openedAt: ts, onsetAt: null, severityAtOpen: null, unhealthy: [], groupings: 0,
    culprit: null, victims: [], fromTraces: null, bundle: {}, pattern: null, tools: [], llmCalls: 0,
    checklist: [], approval: null, action: null, ticks: [], harmClean: null, outcome: null,
    closedAt: null, card: null, briefing: "", quarantined: 0, blocked: 0,
    stages: { detect: "idle", group: "idle", diagnose: "idle", check: "idle", act: "idle", verify: "idle" },
  };
}

// light `stage`, settle everything before it; a failed tile stays failed
function advance(stages: Record<Stage, StageState>, stage: Stage): Record<Stage, StageState> {
  const at = STAGES.indexOf(stage);
  const next = { ...stages };
  STAGES.forEach((s, i) => {
    if (next[s] === "failed") return;
    if (i < at) next[s] = "done";
    else if (i === at) next[s] = "active";
  });
  return next;
}

function close(stages: Record<Stage, StageState>, outcome: Outcome): Record<Stage, StageState> {
  const next = { ...stages };
  if (outcome === "resolved") {
    STAGES.forEach((s) => { if (next[s] !== "failed") next[s] = "done"; });
    return next;
  }
  // escalated / handed off: the tile that was working when it stopped is the one that failed
  const active = STAGES.filter((s) => next[s] === "active");
  active.forEach((s) => { next[s] = "failed"; });
  return next;
}

const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const strs = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x) => typeof x === "string") : []);

function apply(inc: Incident, type: string, p: Record<string, unknown>, ts: number): Incident {
  const stage = STAGE_OF[type];
  let next: Incident = stage ? { ...inc, stages: advance(inc.stages, stage) } : { ...inc };
  switch (type) {
    case "incident_opened":
      next.openedAt = num(p.opened_at) ?? ts;
      next.onsetAt = num(p.onset_at);
      next.severityAtOpen = num(p.severity);
      next.unhealthy = strs(p.unhealthy);
      break;
    case "alerts_grouped":
      next.unhealthy = strs(p.unhealthy);
      next.groupings += 1;
      break;
    case "culprit_found":
      next.culprit = str(p.culprit);
      next.victims = strs(p.victims);
      next.fromTraces = typeof p.from_traces === "boolean" ? p.from_traces : null;
      break;
    case "bundle_built":
      next.bundle = Object.fromEntries(Object.entries(p).filter(([, v]) => typeof v === "number")) as Record<string, number>;
      break;
    case "rule_matched":
      next.pattern = str(p.pattern);
      next.tools = strs(p.tools);
      break;
    case "llm_called":
      next.llmCalls += 1;
      break;
    case "diagnosis_ready":
      next.pattern = str(p.pattern) ?? next.pattern;
      next.culprit = str(p.culprit) ?? next.culprit;
      break;
    case "checklist_step": {
      const passed = p.passed === true;
      next.checklist = [...next.checklist, { name: str(p.name) ?? "?", passed, reason: str(p.reason), ts }];
      if (!passed) next.stages = { ...next.stages, check: "failed" };
      break;
    }
    case "approval_requested":
      next.approval = {
        id: str(p.approval_id) ?? "", forecast: str(p.forecast) ?? "", diff: str(p.diff) ?? "",
        expiresAt: num(p.expires_at) ?? 0, decision: null,
      };
      break;
    case "approval_decided":
      if (next.approval) next.approval = { ...next.approval, decision: str(p.decision) ?? "decided" };
      break;
    case "action_executed":
      next.action = { receiptId: num(p.receipt_id) ?? 0, tool: str(p.tool) ?? "?", target: str(p.target) ?? "?", ts };
      break;
    case "verify_tick":
      next.ticks = [...next.ticks, { ts, severity: num(p.severity), recovered: p.recovered === true }];
      break;
    case "harm_check":
      next.harmClean = typeof p.clean === "boolean" ? p.clean : null;
      break;
    case "injection_quarantined":
      next.quarantined += 1;
      break;
    case "blocked":
      next.blocked += 1;
      break;
  }
  const outcome = TERMINAL[type];
  if (outcome) {
    const card = p.card as Card | undefined;
    next = {
      ...next, outcome, closedAt: ts, stages: close(next.stages, outcome),
      card: card && typeof card.text === "string" ? card : null, briefing: str(p.briefing) ?? "",
    };
  }
  return next;
}

export function reduce(state: LiveState, record: BusRecord): LiveState {
  // the bus replays from Last-Event-ID; ignore anything already seen
  if (record.seq <= state.lastSeq) return state;
  const { type, incident_id, payload } = record.event;
  const id = incident_id ?? null;
  const feed = [{ seq: record.seq, ts: record.ts, type, incidentId: id }, ...state.feed].slice(0, FEED_SIZE);
  if (!id) return { ...state, lastSeq: record.seq, feed };
  const known = state.incidents[id];
  const inc = apply(known ?? blank(id, record.ts), type, payload ?? {}, record.ts);
  return {
    lastSeq: record.seq,
    current: type === "incident_opened" || !state.current ? id : state.current,
    incidents: { ...state.incidents, [id]: inc },
    order: known ? state.order : [id, ...state.order],
    feed,
  };
}
