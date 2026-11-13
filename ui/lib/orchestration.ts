// orchestration run mode for the UI (gateway GET /orchestration/status); pure helpers, tested in node
import { duration, plural, since, words } from "./format.ts";
import { type Incident, type LiveState, STAGES } from "./live.ts";
import { incidentStatus } from "./overview.ts";
import { readTitle } from "./request-flow.ts";

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

export type LaneTone = ModeTone | "ok";
export type LaneKind = "agent" | "commander" | "specialist" | "fix";
export type MarkKind = "request" | "run" | "reads" | "wait" | "verify";

// one thing drawn on a lane; t0 === t1 is a point. n = requests in a request/run, reads in reads
export interface Mark { kind: MarkKind; t0: number; t1: number; n: number; title: string; bad: boolean; live: boolean }
export interface Lane {
  id: string; // "main" | task id | "fix"
  kind: LaneKind;
  title: string;
  sub: string | null;
  state: { label: string; tone: LaneTone } | null;
  t0: number;
  t1: number;
  marks: Mark[];
  requests: number;
  reads: number;
  summary: string; // the track in words, for screen readers
}
// a hand-off between lanes (to set) or a decision that made no lane (to null)
export interface LaneNote {
  t: number; kind: "ask" | "finding" | "decision"; from: string; to: string | null;
  tone: LaneTone; title: string; detail: string | null;
}
export interface LaneBudget {
  used: number; commander: number; specialist: number; max: number | null; left: number | null;
  tokens: number; reads: number; reused: number;
}
export interface LaneView {
  t0: number;
  t1: number;
  lanes: Lane[];
  notes: LaneNote[];
  budget: LaneBudget;
  now: { text: string; tone: LaneTone } | null;
  truncated: boolean;
}

const text = (v: unknown): string | null => (typeof v === "string" && v ? v : null);
const count = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

const TASK_TONE: Record<string, LaneTone> = {
  succeeded: "ok", running: "accent", pending: "accent", failed: "bad", timed_out: "bad", lease_expired: "warn",
};
const TASK_OVER = new Set(["succeeded", "failed", "timed_out", "cancelled"]);
const VERDICT_TONE: Record<string, LaneTone> = { supported: "ok", refuted: "warn", inconclusive: "idle" };
const FIX_TONE: Record<string, LaneTone> = {
  execution_unknown: "bad", superseded: "warn", refused: "warn", queued: "warn", awaiting_approval: "warn",
  executing: "accent", verifying: "accent",
};
const CLOSERS = new Set(["incident_resolved", "escalated", "handed_off"]);
// reads the agent fires together land on one tick
const MERGE_S = 0.5;

// what the incident is doing right now, in plain words; null once it closed
export function nowLine(inc: Incident): { text: string; tone: LaneTone } | null {
  if (inc.outcome != null) return null;
  const who = inc.orch ? "Commander" : "Agent";
  const fixes = Object.values(inc.orch?.intents ?? {});
  if (fixes.some((f) => f.status === "execution_unknown")) return { text: "Fix outcome unknown, a human must check", tone: "bad" };
  if (inc.approval && inc.approval.decision == null) return { text: "Fix waiting for approval", tone: "warn" };
  if (Object.values(inc.orch?.tasks ?? {}).some((t) => t.state === "running" || t.state === "pending")) {
    return { text: "Commander waiting on a specialist", tone: "accent" };
  }
  if (fixes.at(-1)?.status === "queued") return { text: "Fix queued behind another fix", tone: "warn" };
  const stage = STAGES.findLast((s) => inc.stages[s] === "active");
  if (stage === "verify") return { text: "Verifying the fix", tone: "accent" };
  if (stage === "act") return { text: "Applying the fix", tone: "accent" };
  if (stage === "check") return { text: "Gateway checking the fix", tone: "accent" };
  if (stage === "diagnose") return { text: `${who} investigating`, tone: "accent" };
  return { text: "Grouping alerts", tone: "idle" };
}

function fixState(inc: Incident): Lane["state"] {
  const last = Object.values(inc.orch?.intents ?? {}).at(-1)?.status;
  if (last && last !== "terminal") return { label: words(last), tone: FIX_TONE[last] ?? "idle" };
  if (inc.outcome === "resolved") return { label: "done", tone: "ok" };
  if (inc.outcome != null || last === "terminal") return { label: "closed", tone: "idle" };
  if (inc.action) return { label: "verifying", tone: "accent" };
  if (inc.approval?.decision == null) return { label: "awaiting approval", tone: "warn" };
  return { label: words(inc.approval.decision), tone: inc.approval.decision === "approved" ? "accent" : "warn" };
}

// who worked on an incident and when: one lane per agent on a shared time axis, plus the fix.
// Single-agent incidents get one "Agent" lane; a specialist lane exists only for a real task id
export function agentLanes(inc: Incident, now: number, maxRequests: number | null = null): LaneView {
  const events = inc.events;
  // the reducer keeps the newest 400 events; a long incident lost its start
  const truncated = events.length > 0 && events[0].type !== "incident_opened";
  const t0 = truncated ? events[0].ts : Math.min(inc.openedAt, events[0]?.ts ?? inc.openedAt);
  const last = events.at(-1)?.ts ?? t0;
  const open = inc.outcome == null;
  // the fix's own record reports after the close, so a closed axis runs to the last event
  const t1 = Math.max(open ? now : inc.closedAt ?? last, last, t0 + 1);
  const at = (t: number) => Math.min(t1, Math.max(t0, t));

  const blank = (id: string, kind: LaneKind, title: string, ts: number): Lane =>
    ({ id, kind, title, sub: null, state: null, t0: at(ts), t1: at(ts), marks: [], requests: 0, reads: 0, summary: "" });
  const main = blank("main", inc.orch ? "commander" : "agent", inc.orch ? "Commander" : "Agent", t0);
  const tasks = new Map<string, Lane>();
  const verdicts = new Map<string, string>();
  const notes: LaneNote[] = [];
  let fix: Lane | null = null;
  let queue: Mark | null = null;
  let wait: Mark | null = null;
  let verify: Mark | null = null;
  let runFrom: number | null = null;
  let tokens = 0;
  let specialist = 0;
  let commander = 0;

  const task = (id: string, ts: number): Lane => {
    const known = tasks.get(id);
    if (known) return known;
    const made = blank(id, "specialist", "Specialist", ts);
    tasks.set(id, made);
    return made;
  };
  const touch = (l: Lane, ts: number) => { l.t1 = Math.max(l.t1, at(ts)); };
  const onFix = (ts: number): Lane => {
    fix ??= blank("fix", "fix", "Fix", ts);
    touch(fix, ts);
    return fix;
  };
  const begin = (kind: "wait" | "verify", ts: number, title: string, bad = false): Mark => {
    const m: Mark = { kind, t0: at(ts), t1: at(ts), n: 0, title, bad, live: true };
    onFix(ts).marks.push(m);
    return m;
  };
  const end = (m: Mark | null, ts: number) => { if (m?.live) { m.t1 = at(ts); m.live = false; } };
  const read = (l: Lane, ts: number, title: string) => {
    const prev = l.marks.at(-1);
    if (prev && prev.kind === "reads" && ts - prev.t1 <= MERGE_S) {
      prev.t1 = at(ts); prev.n += 1; prev.title = `${prev.title}\n${title}`;
    } else {
      l.marks.push({ kind: "reads", t0: at(ts), t1: at(ts), n: 1, title, bad: false, live: false });
    }
    l.reads += 1;
    touch(l, ts);
  };

  for (const ev of events) {
    const p = ev.payload;
    const ts = ev.ts;
    const taskId = text(p.task_id);
    const args = (p.args && typeof p.args === "object" ? p.args : {}) as Record<string, unknown>;
    switch (ev.type) {
      case "rule_matched":
        runFrom = ts;
        break;
      case "tool_called":
        if (!taskId) runFrom ??= ts;
        read(taskId ? task(taskId, ts) : main, ts, readTitle(text(p.tool) ?? "?", args));
        break;
      case "llm_called": {
        // audit logs from before tool_called carry reads as llm_called with a tool name
        if (text(p.tool)) { read(main, ts, readTitle(text(p.tool)!, args)); break; }
        // a summary repeats what the per-call events already said; a cache hit asked no model
        if (p.kind === "summary" || p.cached === true) break;
        const usage = (p.usage ?? {}) as Record<string, unknown>;
        const used = count(usage.total_tokens) ?? (count(usage.prompt_tokens) ?? 0) + (count(usage.completion_tokens) ?? 0);
        const bad = text(p.error) != null;
        const l = taskId ? task(taskId, ts) : main;
        if (p.kind === "call") {
          const ms = count(p.ms) ?? 0;
          l.marks.push({ kind: "request", t0: at(ts - ms / 1000), t1: at(ts), n: 1, bad, live: false,
            title: [bad ? "Model request failed" : "Model request", used ? `${used} tokens` : null, ms ? `${Math.round(ms)} ms` : null]
              .filter(Boolean).join(" · ") });
          l.requests += 1;
          if (taskId) specialist += 1; else commander += 1;
        } else {
          // the single-agent path reports a whole run once, at its end: one span holding N, never N made-up marks
          const n = (count(usage.requests) ?? 0) > 0 ? count(usage.requests)! : 1;
          main.marks.push({ kind: "run", t0: at(runFrom ?? ts), t1: at(ts), n, bad, live: false,
            title: [bad ? "Model call failed" : plural(n, "model request"), used ? `${used} tokens` : null].filter(Boolean).join(" · ") });
          main.requests += n;
          commander += n;
          tokens += used;
          runFrom = null;
        }
        touch(l, ts);
        break;
      }
      case "diagnosis_ready":
        touch(main, ts);
        break;
      case "delegation_decided": {
        const title = text(p.explanation) ?? "Delegation decided";
        touch(main, ts);
        if (p.status === "admitted" && taskId) {
          task(taskId, ts);
          notes.push({ t: at(ts), kind: "ask", from: "main", to: taskId, tone: "accent", title, detail: null });
        } else if (notes.findLast((n) => n.kind === "decision" && n.from === "main")?.title !== title) {
          notes.push({ t: at(ts), kind: "decision", from: "main", to: null, tone: p.status === "denied" ? "warn" : "idle",
            title, detail: text(p.reason) ? words(text(p.reason)!) : null });
        }
        break;
      }
      case "investigation_task_changed":
        if (taskId) touch(task(taskId, ts), ts);
        break;
      case "finding_recorded": {
        const verdict = text(p.verdict) ?? "inconclusive";
        if (taskId) { touch(task(taskId, ts), ts); verdicts.set(taskId, verdict); }
        touch(main, ts);
        notes.push({ t: at(ts), kind: "finding", from: taskId ?? "main", to: taskId ? "main" : null,
          tone: VERDICT_TONE[verdict] ?? "idle", title: `Finding ${words(verdict)}`, detail: text(p.summary) });
        break;
      }
      case "approval_requested":
        end(wait, ts);
        wait = begin("wait", ts, "Waiting for a human to approve");
        break;
      case "approval_decided":
        if (wait) wait.title = `Approval ${text(p.decision) ?? "decided"}`;
        end(wait, ts);
        onFix(ts);
        break;
      case "action_executed":
        end(wait, ts);
        end(verify, ts);
        verify = begin("verify", ts, `${text(p.tool) ?? "fix"} on ${text(p.target) ?? "?"} applied, health watched`);
        break;
      case "early_abort":
      case "action_undone":
        if (verify) { verify.bad = true; verify.title = `${verify.title} · undone`; }
        end(verify, ts);
        onFix(ts);
        break;
      case "retry_started":
        end(verify, ts);
        runFrom = ts;
        break;
      case "action_intent_changed": {
        const status = text(p.status) ?? "?";
        onFix(ts);
        if (status === "queued") { if (!queue?.live) queue = begin("wait", ts, "Queued behind another fix"); }
        else end(queue, ts);
        if (status === "execution_unknown") {
          end(wait, ts);
          end(verify, ts);
          wait = begin("wait", ts, "Write got no answer: a human must check the cluster", true);
        } else if (status === "terminal" || status === "superseded" || status === "refused") {
          end(wait, ts);
          end(verify, ts);
        }
        if (status === "execution_unknown" || status === "superseded" || status === "refused") {
          notes.push({ t: at(ts), kind: "decision", from: "fix", to: null, tone: FIX_TONE[status] ?? "warn",
            title: `Fix ${words(status)}`, detail: text(p.reason) });
        }
        break;
      }
      default:
        if (CLOSERS.has(ev.type)) { end(queue, ts); end(wait, ts); end(verify, ts); if (fix) touch(fix, ts); }
    }
  }

  // a single agent still thinking has sent nothing about its requests yet: show the run as open
  if (open && !inc.orch && runFrom != null && inc.stages.diagnose === "active") {
    main.marks.push({ kind: "run", t0: at(runFrom), t1, n: 0, bad: false, live: true, title: "Working on a diagnosis" });
  }
  const held = fix as Lane | null;
  for (const m of held?.marks ?? []) if (m.live) { m.t1 = open ? t1 : at(inc.closedAt ?? last); m.live = open; }
  if (held && open) held.t1 = t1;
  if (open && !held) main.t1 = t1;

  const counts = (l: Lane) => `${plural(l.requests, "request")} · ${plural(l.reads, "read")}`;
  main.sub = counts(main);
  const specialists = [...tasks.values()];
  specialists.forEach((l, i) => {
    const known = inc.orch?.tasks[l.id];
    const state = known?.state ?? "pending";
    const verdict = verdicts.get(l.id);
    if (open && !TASK_OVER.has(state)) l.t1 = t1;
    if (specialists.length > 1) l.title = `Specialist ${i + 1}`;
    l.sub = `${counts(l)}${known && known.attempt > 1 ? ` · attempt ${known.attempt}` : ""}`;
    l.state = verdict ? { label: words(verdict), tone: VERDICT_TONE[verdict] ?? "idle" } : { label: words(state), tone: TASK_TONE[state] ?? "idle" };
  });
  if (held) {
    const what = inc.action ?? inc.choice?.chosen ?? null;
    held.sub = what ? `${what.tool} → ${what.target}` : null;
    held.state = fixState(inc);
  }

  const lanes = [main, ...specialists, ...(held ? [held] : [])];
  for (const l of lanes) {
    const span = `${since(l.t0, t0)} to ${since(l.t1, t0)}`;
    l.summary = l.kind === "fix"
      ? `Fix${l.sub ? ` ${l.sub}` : ""}: ${l.marks.map((m) => `${m.title} (${duration(m.t1 - m.t0)})`).join("; ") || "nothing sent yet"}${l.state ? `; ${l.state.label}` : ""}.`
      : `${l.title}${l.kind === "specialist" ? ` ${l.id}` : ""}: ${plural(l.requests, "model request")}, ${plural(l.reads, "read")}, ${span}${l.state ? `, ${l.state.label}` : ""}.`;
  }

  const o = inc.orch;
  const used = o ? Math.max(commander + specialist, o.modelCalls) : inc.llmCalls;
  const max = o && maxRequests != null && maxRequests > 0 ? maxRequests : null;
  return {
    t0, t1, lanes, notes, truncated, now: nowLine(inc),
    budget: {
      used, specialist, commander: Math.max(0, used - specialist), max, left: max == null ? null : Math.max(0, max - used),
      tokens: o ? o.tokensIn + o.tokensOut : tokens,
      reads: lanes.reduce((n, l) => n + l.reads, 0), reused: o?.reusedReads ?? 0,
    },
  };
}

