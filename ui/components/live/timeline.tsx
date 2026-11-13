"use client";

import { useEffect, useRef } from "react";

import { duration, plural, since } from "@/lib/format";
import { describe, type Line, NODES, pathOf, type Phase, phaseOf, type Row, rows, stageTimes } from "@/lib/request-flow";
import type { Incident, IncidentEvent } from "@/lib/live";

import styles from "./timeline.module.css";

const PHASE_TITLE: Record<Phase, string> = {
  detect: "Detect", group: "Group", diagnose: "Diagnose", check: "Check", act: "Act", verify: "Verify", outcome: "Outcome",
};

function rowLine(row: Row, events: IncidentEvent[]): Line {
  if (row.kind === "event") return describe(row.ev, events[row.index + 1] ?? null);
  const a = row.first.payload.severity;
  const b = row.last.payload.severity;
  const ok = row.last.payload.recovered === true;
  return {
    title: `Health checks ×${row.count}`,
    detail: `severity ${a ?? "?"} → ${b ?? "?"}${ok ? " · recovered" : ""}`,
    tone: ok ? "ok" : "info",
  };
}

// every bus event for one incident, grouped by stage; click a row to see it on the flow map
export function Timeline({ incident, selected, onSelect, now, className }: {
  incident: Incident | null; selected: number | null; onSelect: (i: number | null) => void; now: number; className?: string;
}) {
  const events = incident?.events ?? [];
  const list = rows(events);
  const times = stageTimes(events, incident?.closedAt ?? now);
  const box = useRef<HTMLOListElement>(null);

  // follow the newest event unless someone is inspecting an older one
  useEffect(() => {
    if (selected == null && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [events.length, selected]);

  const seen = new Set<Phase>();
  let lastPhase: Phase | null = null;
  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Timeline</h2>
        <div className={styles.headRight}>
          {events.length > 0 && <span className="label">{plural(events.length, "event")}</span>}
          {selected != null && (
            <button type="button" className="btn" onClick={() => onSelect(null)}>Follow live</button>
          )}
        </div>
      </div>

      {!incident ? (
        <p className="empty">Each step the agent takes shows here as it happens, with what it saw and decided.</p>
      ) : (
        <ol ref={box} className={styles.list}>
          {list.map((row) => {
            const ev = row.kind === "event" ? row.ev : row.last;
            const phase = phaseOf(ev.type);
            const header = phase !== lastPhase;
            const first = header && !seen.has(phase);
            lastPhase = phase;
            seen.add(phase);
            const t = times[phase];
            const line = rowLine(row, events);
            const from = row.kind === "event" ? row.index : row.index - row.count + 1;
            const on = selected != null && selected >= from && selected <= row.index;
            const path = pathOf(ev, events[row.index - 1] ?? null);
            return (
              <li key={ev.seq} className={styles.item}>
                {header && (
                  <div className={styles.phase}>
                    <span>{PHASE_TITLE[phase]}</span>
                    {first && t && phase !== "outcome" && (
                      <span className={styles.phaseTime}>{since(t.start, incident.openedAt)} · took {duration(t.took)}</span>
                    )}
                  </div>
                )}
                <button type="button" className={on ? `${styles.row} ${styles.on}` : styles.row}
                  title={!on && line.detail ? line.detail : undefined} aria-pressed={on} onClick={() => onSelect(on ? null : row.index)}>
                  <span className={styles.time}>{since(ev.ts, incident.openedAt)}</span>
                  <span className={`${styles.marker} ${styles[line.tone] ?? ""}`} aria-hidden="true" />
                  <span className={styles.body}>
                    <span className={`${styles.title} ${styles[`t_${line.tone}`] ?? ""}`}>{line.title}</span>
                    {line.detail && (on || line.tone === "warn" || line.tone === "bad") && <span className={styles.detail}>{line.detail}</span>}
                  </span>
                  <span className={styles.route}>{path.map((id) => NODES[id].title).join(" → ")}</span>
                </button>
                {on && (
                  <pre className={styles.payload} aria-label="Event payload">
                    {JSON.stringify({ type: ev.type, seq: ev.seq, ...ev.payload }, null, 2)}
                  </pre>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </article>
  );
}
