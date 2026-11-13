import { plural, words } from "@/lib/format";
import type { Incident } from "@/lib/live";
import { readTitle } from "@/lib/request-flow";

import s from "./sheet.module.css";

const KINDS = ["changes", "metrics", "traces", "events", "logs"] as const;

// shop's Jaeger behind frontend-proxy (plan §3.3)
const JAEGER = process.env.NEXT_PUBLIC_JAEGER_URL ?? "http://localhost:8080/jaeger/ui";

export function Evidence({ incident }: { incident: Incident }) {
  const bundle = incident.bundle;
  const total = KINDS.reduce((n, k) => n + (bundle[k] ?? 0), 0);
  const max = Math.max(8, ...KINDS.map((k) => bundle[k] ?? 0));
  return (
    <section className={s.sec} aria-labelledby="sec-evidence">
      <div className={s.head}>
        <h2 id="sec-evidence" className={s.title}>Evidence</h2>
        {incident.culprit && (
          <a className="pill" href={`${JAEGER}/search?service=${encodeURIComponent(incident.culprit)}`} target="_blank" rel="noreferrer">
            Traces in Jaeger ↗
          </a>
        )}
      </div>
      <p className={s.note}>
        {plural(total, "item")}, redacted · {incident.pattern ? words(incident.pattern) : "no"} pattern
        {incident.quarantined > 0 && <span className="bad"> · {plural(incident.quarantined, "line")} quarantined</span>}
      </p>
      <div className={s.bars}>
        {KINDS.map((kind) => {
          const n = bundle[kind] ?? 0;
          return (
            <div key={kind} className={s.barRow}>
              <span className={s.barLabel}>{kind}</span>
              <span className={s.track} aria-hidden="true"><span className={s.fill} style={{ width: `${(n / max) * 100}%` }} /></span>
              <span className={s.barN}>{n}</span>
            </div>
          );
        })}
      </div>
      {incident.reads.length > 0 && (
        <>
          <p className={`${s.note} ${s.noteTop}`}>What the agent read itself</p>
          <ol className={s.steps}>
            {incident.reads.map((r, i) => (
              <li key={`${r.ts}-${i}`} className={`${s.step} ${s.read}`}>
                <span>{readTitle(r.tool, r.args)}</span>
                <span className="num muted">{r.evidence} found</span>
              </li>
            ))}
          </ol>
        </>
      )}
      {incident.tools.length > 0 && (
        <p className={`${s.note} ${s.noteTop}`}>Rule proposes <span className="mono">{incident.tools.join(", ")}</span></p>
      )}
    </section>
  );
}
