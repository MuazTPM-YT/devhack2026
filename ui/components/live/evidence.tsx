import { words } from "@/lib/format";
import type { Incident } from "@/lib/live";

import styles from "./evidence.module.css";

const KINDS = ["changes", "metrics", "traces", "events", "logs"] as const;
const MAX_DOTS = 8;

// shop's Jaeger behind frontend-proxy (plan §3.3)
const JAEGER = process.env.NEXT_PUBLIC_JAEGER_URL ?? "http://localhost:8080/jaeger/ui";

export function Evidence({ incident, className }: { incident: Incident | null; className?: string }) {
  const bundle = incident?.bundle ?? {};
  const total = KINDS.reduce((n, k) => n + (bundle[k] ?? 0), 0);
  const culprit = incident?.culprit;
  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Evidence sent</h2>
        {culprit && (
          <a className="pill" href={`${JAEGER}/search?service=${encodeURIComponent(culprit)}`} target="_blank" rel="noreferrer">
            traces in Jaeger ↗
          </a>
        )}
      </div>

      <div className={styles.top}>
        <div>
          <div className="figure">{String(total).padStart(2, "0")}</div>
          <div className="label">items in the bundle, redacted</div>
        </div>
        <div className={styles.facts}>
          <span><b>{incident?.pattern ? words(incident.pattern) : "–"}</b> pattern</span>
          <span><b>{incident?.llmCalls ?? 0}</b> model calls</span>
          {(incident?.quarantined ?? 0) > 0 && <span className="bad"><b>{incident?.quarantined}</b> lines quarantined</span>}
        </div>
      </div>

      <div className={styles.columns} role="img" aria-label={KINDS.map((k) => `${bundle[k] ?? 0} ${k}`).join(", ")}>
        {KINDS.map((kind) => {
          const n = bundle[kind] ?? 0;
          return (
            <div key={kind} className={styles.col}>
              <div className={styles.stack}>
                {Array.from({ length: MAX_DOTS }, (_, i) => (
                  <span key={i} className={i < Math.min(n, MAX_DOTS) ? styles.on : styles.off} />
                ))}
              </div>
              <span className={styles.n}>{n}</span>
              <span className="label">{kind}</span>
            </div>
          );
        })}
      </div>

      {incident?.tools.length ? (
        <p className={styles.tools}>Rule proposes <span className="mono">{incident.tools.join(", ")}</span></p>
      ) : null}
    </article>
  );
}
