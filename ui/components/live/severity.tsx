import type { Incident } from "@/lib/live";
import type { ReceiptView } from "@/lib/use-receipt";

import styles from "./severity.module.css";

const W = 600;
const H = 250;
const PAD = { l: 34, r: 12, t: 14, b: 26 };

interface Point { t: number; v: number }

// severity over time since the incident opened, with the predicted and actual recovery marked
export function Severity({ incident, receipt, className }: {
  incident: Incident | null; receipt: ReceiptView | null; className?: string;
}) {
  const base = incident?.openedAt ?? 0;
  const points: Point[] = [];
  if (incident?.severityAtOpen != null) points.push({ t: 0, v: incident.severityAtOpen });
  incident?.ticks.forEach((k) => { if (k.severity != null) points.push({ t: k.ts - base, v: k.severity }); });

  const actionT = incident?.action ? incident.action.ts - base : null;
  const predictedT = actionT != null && receipt?.forecast_s != null ? actionT + receipt.forecast_s : null;
  const firstOk = incident?.ticks.find((k) => k.recovered);
  const actualT = firstOk ? firstOk.ts - base : null;

  const now = points.at(-1)?.v ?? null;
  const tMax = Math.max(30, ...points.map((p) => p.t), predictedT ?? 0, actualT ?? 0) * 1.05;
  const vMax = Math.max(4, ...points.map((p) => p.v));
  const x = (t: number) => PAD.l + (t / tMax) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - v / vMax) * (H - PAD.t - PAD.b);

  const line = points.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const area = points.length > 1 ? `${line} L${x(points.at(-1)!.t).toFixed(1)},${y(0)} L${x(points[0].t).toFixed(1)},${y(0)} Z` : "";

  const held = receipt?.prediction_held;
  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Severity</h2>
        {held != null && (
          <span className="pill">
            <span className={`dot ${held ? "dot-ok" : "dot-bad"}`} />
            prediction {held ? "held" : "missed"}
          </span>
        )}
      </div>

      <div className={styles.summary}>
        <div>
          <div className="figure">{now == null ? "–" : now}</div>
          <div className="label">now{incident?.severityAtOpen != null ? ` · was ${incident.severityAtOpen} at open` : ""}</div>
        </div>
        <div className={styles.legend}>
          <span><i className={styles.keyLine} /> observed</span>
          <span><i className={styles.keyPred} /> predicted recovery{receipt?.forecast_s != null ? ` · ${receipt.forecast_s} s` : ""}</span>
          <span><i className={styles.keyActual} /> recovered{receipt?.elapsed_s != null ? ` · ${receipt.elapsed_s} s` : ""}</span>
        </div>
      </div>

      {points.length === 0 ? (
        <p className="empty">Severity is 0 while every service is inside its baseline.</p>
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} className={styles.chart} role="img"
          aria-label={`Severity went from ${points[0].v} to ${now}`}>
          {[0, 0.5, 1].map((f) => (
            <g key={f}>
              <line x1={PAD.l} x2={W - PAD.r} y1={y(vMax * f)} y2={y(vMax * f)} className={styles.grid} />
              <text x={PAD.l - 8} y={y(vMax * f) + 4} className={styles.tick} textAnchor="end">{Math.round(vMax * f)}</text>
            </g>
          ))}
          <text x={W - PAD.r} y={H - 6} className={styles.tick} textAnchor="end">{Math.round(tMax)} s</text>
          <text x={PAD.l} y={H - 6} className={styles.tick}>open</text>
          {area && <path d={area} className={styles.area} />}
          <path d={line} className={styles.line} />
          {actionT != null && (
            <g>
              <line x1={x(actionT)} x2={x(actionT)} y1={PAD.t} y2={y(0)} className={styles.action} />
              <text x={x(actionT) + 5} y={y(0) - 6} className={styles.tick}>fix applied</text>
            </g>
          )}
          {predictedT != null && (
            <line x1={x(predictedT)} x2={x(predictedT)} y1={PAD.t} y2={y(0)} className={styles.pred} />
          )}
          {actualT != null && (
            <line x1={x(actualT)} x2={x(actualT)} y1={PAD.t} y2={y(0)} className={styles.actual} />
          )}
          {points.map((p, i) => (
            <circle key={i} cx={x(p.t)} cy={y(p.v)} r="2.6" className={styles.point} />
          ))}
        </svg>
      )}
    </article>
  );
}
