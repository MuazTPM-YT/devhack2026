import { since } from "@/lib/format";
import { type Incident, STAGES, type Stage, type StageState } from "@/lib/live";

import styles from "./stage-strip.module.css";

const COPY: Record<Stage, { title: string; hint: string }> = {
  detect: { title: "Detect", hint: "error or latency breach held" },
  group: { title: "Group", hint: "alerts folded into one incident" },
  diagnose: { title: "Diagnose", hint: "culprit, evidence, pattern" },
  check: { title: "Check", hint: "every gate before acting" },
  act: { title: "Act", hint: "auto or human approval" },
  verify: { title: "Verify", hint: "health watched, undo if worse" },
};

const STATE_LABEL: Record<StageState, string> = {
  idle: "waiting", active: "working", done: "done", failed: "stopped",
};

// 5x4 dot field; lit dots grow as the stage moves on
function Dots({ state }: { state: StageState }) {
  const lit = { idle: 0, active: 9, done: 20, failed: 20 }[state];
  return (
    <div className={styles.dots} aria-hidden="true">
      {Array.from({ length: 20 }, (_, i) => (
        <span key={i} className={i < lit ? styles[`dot_${state}`] : styles.dot} />
      ))}
    </div>
  );
}

export function StageStrip({ incident }: { incident: Incident | null }) {
  return (
    <section className={styles.strip} aria-label="Pipeline stages">
      {STAGES.map((stage, i) => {
        const state = incident?.stages[stage] ?? "idle";
        return (
          <article key={stage} className={`card ${styles.tile} ${styles[state]}`}>
            <div className={styles.top}>
              <span className="label">{String(i + 1).padStart(2, "0")}</span>
              <span className={styles.state}>{STATE_LABEL[state]}</span>
            </div>
            <h3 className={styles.title}>{COPY[stage].title}</h3>
            <div className={styles.bottom}>
              <p className={styles.hint}>{COPY[stage].hint}</p>
              <Dots state={state} />
            </div>
            {stage === "detect" && incident?.onsetAt != null && (
              <span className={styles.stamp}>{since(incident.openedAt, incident.onsetAt)} after onset</span>
            )}
          </article>
        );
      })}
    </section>
  );
}
