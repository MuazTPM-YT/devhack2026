"use client";

import { clock } from "@/lib/format";
import { useLiveContext } from "@/lib/live-context";

import styles from "./health.module.css";

// severity worth a full arc; higher still draws as full
const ARC_MAX = 12;

// half-circle gauge: 0 healthy on the left, full arc = very bad
function Gauge({ severity }: { severity: number }) {
  const f = Math.min(1, severity / ARC_MAX);
  const r = 90;
  const len = Math.PI * r;
  return (
    <svg viewBox="0 0 220 120" className={styles.gauge} aria-hidden="true">
      <path d="M20 110 A90 90 0 0 1 200 110" className={styles.track} />
      {/* a round cap on a zero-length dash still draws a dot, so 0 draws nothing */}
      {f > 0 && <path d="M20 110 A90 90 0 0 1 200 110" className={styles.fill}
        style={{ strokeDasharray: `${len * f} ${len}` }} />}
    </svg>
  );
}

export function Health({ className }: { className?: string }) {
  const { health, error } = useLiveContext().observer;

  const services = health ? Object.entries(health.services).sort(([, a], [, b]) => Number(b.unhealthy) - Number(a.unhealthy)) : [];
  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Health now</h2>
        <span className="pill">
          <span className={`dot ${error ? "dot-bad" : health ? "dot-ok" : "dot-warn"}`} />
          {error ? "observer offline" : health ? `read ${clock(health.ts)}` : "waiting"}
        </span>
      </div>

      {error && !health ? (
        <p className="empty">No reading from the observer ({error}). Start it on :7001 to see severity here.</p>
      ) : (
        <>
          <div className={styles.dial}>
            <Gauge severity={health?.severity ?? 0} />
            <div className={styles.center}>
              <div className="figure">{health ? health.severity : "–"}</div>
              <div className="label">severity, 0 is healthy</div>
            </div>
          </div>
          <ul className={styles.list}>
            {services.map(([name, s]) => (
              <li key={name} className={s.unhealthy ? styles.bad : undefined}>
                <span className={`dot ${s.unhealthy ? "dot-bad" : s.breaching ? "dot-warn" : "dot-ok"}`} />
                <span>{name}</span>
                <span className={styles.num}>{s.err_ratio == null ? "–" : `${(s.err_ratio * 100).toFixed(1)}%`}</span>
                <span className={styles.num}>{s.p95_ms == null ? "–" : `${Math.round(s.p95_ms)} ms`}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </article>
  );
}
