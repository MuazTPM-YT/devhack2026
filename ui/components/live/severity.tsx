import type { Incident } from "@/lib/live";
import type { ReceiptView } from "@/lib/use-receipt";

import { SheetSection } from "./sheet-section";
import s from "./sheet.module.css";

const W = 320;
const H = 140;
const PAD = { l: 22, r: 6, t: 8, b: 18 };

interface Point { t: number; v: number }

// severity since the incident opened, with the fix, the predicted and the actual recovery marked
export function Severity({ incident, receipt }: { incident: Incident; receipt: ReceiptView | null }) {
  const base = incident.openedAt;
  const points: Point[] = [];
  if (incident.severityAtOpen != null) points.push({ t: 0, v: incident.severityAtOpen });
  incident.ticks.forEach((k) => { if (k.severity != null) points.push({ t: k.ts - base, v: k.severity }); });

  const actionT = incident.action ? incident.action.ts - base : null;
  const predictedT = actionT != null && receipt?.forecast_s != null ? actionT + receipt.forecast_s : null;
  const firstOk = incident.ticks.find((k) => k.recovered);
  const actualT = firstOk ? firstOk.ts - base : null;

  const now = points.at(-1)?.v ?? null;
  const tMax = Math.max(30, ...points.map((p) => p.t), predictedT ?? 0, actualT ?? 0) * 1.04;
  const vMax = Math.max(4, ...points.map((p) => p.v));
  const x = (t: number) => PAD.l + (t / tMax) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - v / vMax) * (H - PAD.t - PAD.b);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const area = points.length > 1 ? `${line} L${x(points.at(-1)!.t).toFixed(1)},${y(0)} L${x(points[0].t).toFixed(1)},${y(0)} Z` : "";
  const held = receipt?.prediction_held;

  return (
    <SheetSection id="sec-severity" title="Severity"
      aside={held != null && <span className={`label ${held ? "ok" : "bad"}`}>prediction {held ? "held" : "missed"}</span>}>
      <div className={s.counts}>
        <div><span className={s.big}>{now ?? "–"}</span><span className={s.small}>now</span></div>
        <div><span className={s.big}>{incident.severityAtOpen ?? "–"}</span><span className={s.small}>at open</span></div>
        {receipt?.elapsed_s != null && <div><span className={s.big}>{Math.round(receipt.elapsed_s)} s</span><span className={s.small}>to recover</span></div>}
      </div>
      {points.length === 0 ? (
        <p className={s.empty}>Severity is 0 while every service is inside its baseline.</p>
      ) : (
        <>
          <svg viewBox={`0 0 ${W} ${H}`} className={s.chart} role="img" aria-label={`Severity went from ${points[0].v} to ${now}`}>
            {[0, 0.5, 1].map((f) => (
              <g key={f}>
                <line x1={PAD.l} x2={W - PAD.r} y1={y(vMax * f)} y2={y(vMax * f)} className={s.grid} />
                <text x={PAD.l - 5} y={y(vMax * f) + 3} className={s.tick} textAnchor="end">{Math.round(vMax * f)}</text>
              </g>
            ))}
            <text x={PAD.l} y={H - 4} className={s.tick}>open</text>
            <text x={W - PAD.r} y={H - 4} className={s.tick} textAnchor="end">{Math.round(tMax)} s</text>
            {area && <path d={area} className={s.area} />}
            <path d={line} className={s.line} />
            {actionT != null && <line x1={x(actionT)} x2={x(actionT)} y1={PAD.t} y2={y(0)} className={s.markAction} />}
            {predictedT != null && <line x1={x(predictedT)} x2={x(predictedT)} y1={PAD.t} y2={y(0)} className={s.markPred} />}
            {actualT != null && <line x1={x(actualT)} x2={x(actualT)} y1={PAD.t} y2={y(0)} className={s.markActual} />}
            {points.map((p, i) => <circle key={i} cx={x(p.t)} cy={y(p.v)} r="2" className={s.point} />)}
          </svg>
          <div className={s.legend}>
            <span><i className={s.kLine} />observed</span>
            {actionT != null && <span><i className={s.kAction} />fix applied</span>}
            {predictedT != null && <span><i className={s.kPred} />predicted · {receipt?.forecast_s} s</span>}
            {actualT != null && <span><i className={s.kActual} />recovered</span>}
          </div>
        </>
      )}
    </SheetSection>
  );
}
