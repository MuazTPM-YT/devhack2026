import type { CSSProperties } from "react";

import { Tag } from "@/components/ui/tag";
import { duration, plural, since } from "@/lib/format";
import type { Incident } from "@/lib/live";
import { agentLanes, type LaneView, type Mark, type MarkKind } from "@/lib/orchestration";

import s from "./agent-lanes.module.css";

const LEGEND: Record<MarkKind, string> = {
  request: "model request", run: "agent run", reads: "telemetry read", wait: "waiting", verify: "health watched",
};
const KINDS: MarkKind[] = ["request", "run", "reads", "wait", "verify"];
// past this many the budget reads better as a number than as cells
const MAX_CELLS = 20;

function markClass(m: Mark): string {
  return [s.mark, s[m.kind], m.bad ? s.bad : "", m.live ? s.live : "", m.kind === "reads" && m.n > 1 ? s.many : ""].filter(Boolean).join(" ");
}

// one cell per allowed request: solid = commander, ring = specialist, sunk = still left
function Meter({ budget }: { budget: LaneView["budget"] }) {
  const max = budget.max ?? 0;
  if (max < 1 || max > MAX_CELLS) return null;
  return (
    <span className={s.meter} aria-hidden="true">
      {Array.from({ length: max }, (_, i) => (
        <i key={i} className={i < budget.commander ? s.cellMain : i < budget.used ? s.cellSpec : s.cell} />
      ))}
    </span>
  );
}

// who is working on the incident: one lane per agent on one time axis, hand-offs between them, what it cost.
// live false = an open incident that went quiet: the axis stops at its last event
export function AgentLanes({ incident, now, live, maxRequests }: {
  incident: Incident; now: number; live: boolean; maxRequests: number | null;
}) {
  const view = agentLanes(incident, now, maxRequests);
  const span = view.t1 - view.t0;
  const pct = (t: number) => ((t - view.t0) / span) * 100;
  const row = (id: string) => view.lanes.findIndex((l) => l.id === id);
  const name = (id: string) => view.lanes.find((l) => l.id === id)?.title ?? id;
  const b = view.budget;
  const agents = view.lanes.filter((l) => l.kind !== "fix").length;
  const kinds = KINDS.filter((k) => view.lanes.some((l) => l.marks.some((m) => m.kind === k)));

  return (
    <article className={`card ${s.band}`} aria-labelledby="agents-title">
      <div className="card-head">
        <h2 id="agents-title" className="card-title">Agents</h2>
        <span aria-live="polite">
          {view.now && live
            ? <Tag tone={view.now.tone}>{view.now.text}</Tag>
            : <span className="label">{plural(agents, "agent")} · {duration(span)}{incident.outcome == null ? " · gone quiet" : ""}</span>}
        </span>
      </div>

      <ol className={s.lanes}>
        {view.lanes.map((l, i) => (
          <li key={l.id} className={s.lane}>
            <div className={s.who} title={l.kind === "specialist" ? l.id : undefined}>
              <span className={s.name}>{l.title}</span>
              {l.sub && <span className={s.sub}>{l.sub}</span>}
            </div>
            <div className={s.track} aria-hidden="true">
              <span className={s.extent} style={{ left: `${pct(l.t0)}%`, width: `${pct(l.t1) - pct(l.t0)}%` }} />
              {l.marks.map((m, k) => (
                <span key={`${m.kind}-${m.t0}-${k}`} className={markClass(m)} title={m.title}
                  style={{ left: `${pct(m.t0)}%`, width: `${pct(m.t1) - pct(m.t0)}%` }} />
              ))}
              {/* a hand-off is drawn from the upper lane down to the lower one; the foot sits on who receives */}
              {view.notes.filter((n) => n.to != null && Math.min(row(n.from), row(n.to)) === i).map((n) => (
                <span key={`${n.kind}-${n.t}`} className={`${s.link} ${row(n.to!) > row(n.from) ? s.down : s.up}`} title={n.title}
                  style={{ left: `${pct(n.t)}%`, "--rows": Math.abs(row(n.to!) - row(n.from)) } as CSSProperties} />
              ))}
            </div>
            <span className="sr-only">{l.summary}</span>
            <span className={s.state}>{l.state && <Tag tone={l.state.tone}>{l.state.label}</Tag>}</span>
          </li>
        ))}
        <li className={s.axis} aria-hidden="true">
          <span className={s.ticks}>
            <span>{view.truncated ? "earlier events not kept" : "+0 s"}</span>
            <span>{view.now && live ? "now" : `+${duration(span)}`}</span>
          </span>
        </li>
      </ol>

      {view.notes.length > 0 && (
        <ul className={s.notes} aria-label="Hand-offs and decisions">
          {view.notes.map((n) => (
            <li key={`${n.kind}-${n.t}-${n.from}`}>
              <span className={s.at}>{since(n.t, view.t0)}</span>
              <span className={s.route}>{name(n.from)}{n.to ? ` → ${name(n.to)}` : ""}</span>
              <span className={s.said}>
                {n.title}
                {n.detail && <span className={s.detail}>{n.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className={s.totals}>
        <p className={s.spend}>
          <Meter budget={b} />
          <span>
            <strong>{b.max != null ? `${b.used} of ${b.max}` : b.used}</strong> {b.max != null || b.used !== 1 ? "model requests" : "model request"}
            {b.max != null && <> · {b.left} left</>}
            {b.specialist > 0 && <> · commander {b.commander}, specialist {b.specialist}</>}
          </span>
        </p>
        {(b.tokens > 0 || b.reads > 0) && (
          <p className={s.spend}>
            {b.tokens > 0 && <>{b.tokens.toLocaleString("en")} tokens · </>}{plural(b.reads, "read")}
            {b.reused > 0 && <> · {b.reused} reused</>}
          </p>
        )}
        {kinds.length > 0 && (
          <p className={s.legend} aria-hidden="true">
            {kinds.map((k) => <span key={k}><i className={`${s.key} ${s[k]}`} />{LEGEND[k]}</span>)}
          </p>
        )}
      </div>
    </article>
  );
}
