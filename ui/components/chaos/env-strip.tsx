import type { Baseline, Experiment, Registry } from "@/lib/lab";
import type { Telemetry } from "@/lib/lab";

import styles from "./lab.module.css";

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
      <div className={`${styles.cell} ${telemetry.ok ? "" : styles.blind}`}>
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
        <button type="button" className={`btn ${styles.danger}`} onClick={onReset} disabled={busy}
                title="Restore the whole shop from its healthy snapshot. Ends every experiment.">
          {busy ? "Recovering…" : "Recover everything"}
        </button>
      </div>
    </section>
  );
}
