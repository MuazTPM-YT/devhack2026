import { Tag, type Tone } from "@/components/ui/tag";
import { plural, words } from "@/lib/format";
import type { Incident } from "@/lib/live";

import s from "./sheet.module.css";

const TASK_TONE: Record<string, Tone> = { succeeded: "ok", running: "accent", failed: "bad", timed_out: "bad" };
const FIX_TONE: Record<string, Tone> = { execution_unknown: "bad", superseded: "warn", queued: "warn", verifying: "accent" };

// coordinated mode only: why these services share one investigation, whether a specialist ran and why,
// what the investigation cost, where each fix stands. Nothing here for single-agent incidents
export function Investigation({ incident }: { incident: Incident }) {
  const o = incident.orch;
  if (!o) return null;
  const tasks = Object.entries(o.tasks);
  const fixes = Object.entries(o.intents);
  const decided = o.delegation.at(-1);
  return (
    <section className={s.sec} aria-labelledby="sec-investigation">
      <div className={s.head}>
        <h2 id="sec-investigation" className={s.title}>Investigation</h2>
        {o.scopeRevision > 0 && <span className="label">scope r{o.scopeRevision}</span>}
      </div>
      {o.services.length > 0 && (
        <p className={s.note}>
          {o.services.join(", ")}{o.reasons.length > 0 && <> · {o.reasons.map(words).join(" · ")}</>}
        </p>
      )}
      {decided && <p className={s.note}>{decided.explanation}</p>}
      {tasks.length > 0 && (
        <ul className={s.rows} aria-label="Specialists">
          {tasks.map(([id, t]) => (
            <li key={id}>
              <span className="mono">{id}</span>
              <Tag tone={TASK_TONE[t.state] ?? "idle"}>{words(t.state)}</Tag>
            </li>
          ))}
        </ul>
      )}
      {o.findings.map((f, i) => (
        <p key={i} className={s.note}><strong>{words(f.verdict)}:</strong> {f.summary}</p>
      ))}
      <div className={s.counts}>
        <div><span className={s.big}>{o.modelCalls}</span><span className={s.small}>model requests</span></div>
        <div><span className={s.big}>{o.tokensIn + o.tokensOut}</span><span className={s.small}>tokens</span></div>
        <div><span className={s.big}>{o.reusedReads}</span><span className={s.small}>reads reused</span></div>
      </div>
      {fixes.length > 0 ? (
        <ul className={s.rows} aria-label="Fixes">
          {fixes.map(([id, f]) => (
            <li key={id}>
              <span><span className="mono">{id}</span>{f.reason && <span className={s.reason}>{f.reason}</span>}</span>
              <Tag tone={FIX_TONE[f.status] ?? "idle"}>{words(f.status)}</Tag>
            </li>
          ))}
        </ul>
      ) : (
        <p className={s.empty}>{plural(tasks.length, "specialist")} so far; no fix sent yet.</p>
      )}
    </section>
  );
}
