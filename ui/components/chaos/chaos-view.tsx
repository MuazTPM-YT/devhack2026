import { CliGuide } from "./cli-guide";
import { Health } from "./health";
import { TruthLog } from "./truth-log";
import styles from "./chaos-view.module.css";

// watch-only: faults are injected with chaos/cli.py, this page shows health and ground truth
export function ChaosView() {
  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <p className="label">Admin kubeconfig · the agent never calls the chaos panel</p>
        <h1 className={styles.title}>Chaos monitor</h1>
      </div>
      <div className={styles.grid}>
        <CliGuide className={styles.span8} />
        <div className={styles.col4}>
          <Health />
          <TruthLog />
        </div>
      </div>
    </div>
  );
}
