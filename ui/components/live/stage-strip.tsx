import { stageTimes } from "@/lib/request-flow";
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
      {STAGES.map((stage) => {
        const state = incident?.stages[stage] ?? "idle";
        const t = times[stage];
        return (
          <li key={stage} className={`${styles.step} ${styles[state] ?? ""}`}
            title={`${COPY[stage].hint}${t && incident ? ` · started ${since(t.start, incident.openedAt)}` : ""}`}>
            <span className={styles.title}>{COPY[stage].title}</span>
            <span className={styles.state}>
              {t && incident && state === "done" ? duration(t.took)
                : t && incident ? `${STATE_LABEL[state]} · ${duration(t.took)}` : STATE_LABEL[state]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
