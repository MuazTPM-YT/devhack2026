import { stageTimes } from "@/lib/flow";
import { duration, since } from "@/lib/format";
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

// six stages as one stepper; each shows when it started and how long it ran
export function StageStrip({ incident, now }: { incident: Incident | null; now: number }) {
  const times = stageTimes(incident?.events ?? [], incident?.closedAt ?? now);
  return (
    <ol className={styles.strip} aria-label="Pipeline stages">
      {STAGES.map((stage, i) => {
        const state = incident?.stages[stage] ?? "idle";
        const t = times[stage];
        return (
          <li key={stage} className={`${styles.step} ${styles[state] ?? ""}`} title={COPY[stage].hint}>
            <div className={styles.top}>
              <span className={styles.num}>{String(i + 1).padStart(2, "0")}</span>
              <span className={styles.title}>{COPY[stage].title}</span>
            </div>
            <span className={styles.state}>{STATE_LABEL[state]}</span>
            <div className={styles.time}>
              {t && incident ? `${since(t.start, incident.openedAt)} · ${duration(t.took)}` : COPY[stage].hint}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
