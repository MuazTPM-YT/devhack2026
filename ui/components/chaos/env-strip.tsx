import { type ReactNode, useEffect, useRef, useState } from "react";

import type { Baseline, Experiment, Registry } from "@/lib/lab";
import type { Telemetry } from "@/lib/lab";

import styles from "./lab.module.css";

const HOLD_MS = 1500;

// destructive, so press and hold to confirm: the fill shows progress, letting go early cancels
function HoldButton({ busy, onDone, title, children }: { busy: boolean; onDone: () => void; title: string; children: ReactNode }) {
  const [holding, setHolding] = useState(false);
  const timer = useRef<number | null>(null);
  const stop = () => {
    if (timer.current != null) window.clearTimeout(timer.current);
    timer.current = null;
    setHolding(false);
  };
  const start = () => {
    if (busy || timer.current != null) return;
    setHolding(true);
    timer.current = window.setTimeout(() => { timer.current = null; setHolding(false); onDone(); }, HOLD_MS);
  };
  useEffect(() => () => { if (timer.current != null) window.clearTimeout(timer.current); }, []);
  const isKey = (k: string) => k === "Enter" || k === " ";
  return (
    <button type="button" className={`btn ${styles.danger} ${styles.hold}`} data-holding={holding} disabled={busy} title={title}
      onPointerDown={(e) => { if (e.button === 0) start(); }} onPointerUp={stop} onPointerLeave={stop} onPointerCancel={stop}
      onKeyDown={(e) => { if (isKey(e.key)) { e.preventDefault(); if (!e.repeat) start(); } }}
      onKeyUp={(e) => { if (isKey(e.key)) stop(); }} onBlur={stop} onContextMenu={(e) => e.preventDefault()}>
      <span className={styles.holdFill} aria-hidden="true" />
      <span aria-live="polite">{children}</span>
    </button>
  );
}

const DOT = { fresh: "dot-ok", stale: "dot-warn", blind: "dot-bad", offline: "dot-bad", waiting: "dot-warn" } as const;

function baselineText(b: Baseline | undefined): { dot: string; text: string } {
  if (!b) return { dot: "dot-warn", text: "Unknown, lab not loaded" };
  if (b.ok) return { dot: "dot-ok", text: "Healthy and fresh: ready" };
  return { dot: b.ok === false ? "dot-bad" : "dot-warn", text: `Not ready: ${b.reason}` };
}

// is the world in a state where an experiment means something? unknown is shown as unknown
export function EnvStrip({ telemetry, registry, run, error, busy, onReset }: {
  telemetry: Telemetry; registry: Registry | null; run: Experiment | null; error: string | null; busy: boolean; onReset: () => void;
}) {
  const base = baselineText(registry?.baseline);
  return (
    <section className={styles.strip} aria-label="Environment">
      <div className={`${styles.cell} ${telemetry.ok || telemetry.state === "waiting" ? "" : styles.blind}`}>
        <span className={styles.cellLabel}>Monitoring</span>
        <span className={styles.cellValue}><span className={`dot ${DOT[telemetry.state]}`} />{telemetry.text}</span>
      </div>
      <div className={styles.cell}>
        <span className={styles.cellLabel}>Baseline</span>
        <span className={styles.cellValue}><span className={`dot ${base.dot}`} />{base.text}</span>
      </div>
      <div className={styles.cell}>
        <span className={styles.cellLabel}>Experiment</span>
        <span className={styles.cellValue}>
          {run ? <><span className="dot dot-warn" />{run.id} is {run.status.replace("_", " ")}</> : registry ? "None running" : "Unknown"}
        </span>
      </div>
      <div className={styles.cell}>
        <span className={styles.cellLabel}>Lab</span>
        <span className={styles.cellValue}>
          {error ? <span className="bad">{error}</span>
            : registry ? `k3d-oncall / shop · rules v${registry.version} · ${registry.limits.max_active} at a time` : "Loading…"}
        </span>
      </div>
      <div className={styles.cell}>
        <HoldButton busy={busy} onDone={onReset} title="Restore the whole shop from its healthy snapshot. Ends every experiment; can take a few minutes.">
          {busy ? "Recovering…" : "Hold to recover everything"}
        </HoldButton>
      </div>
    </section>
  );
}
