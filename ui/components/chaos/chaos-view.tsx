"use client";

import { useState } from "react";

import { FaultBoard } from "./fault-board";
import { Health } from "./health";
import { KubectlBox } from "./kubectl-box";
import { TruthLog } from "./truth-log";
import styles from "./chaos-view.module.css";

export function ChaosView() {
  // bumped after any write so the panels below refetch
  const [version, setVersion] = useState(0);
  const changed = () => setVersion((v) => v + 1);

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <p className="label">Admin kubeconfig · the agent never calls this panel</p>
        <h1 className={styles.title}>Chaos</h1>
      </div>
      <FaultBoard onChange={changed} />
      <div className={styles.grid}>
        <Health className={styles.span4} />
        <KubectlBox onChange={changed} className={styles.span8} />
        <TruthLog version={version} className={styles.span12} />
      </div>
    </div>
  );
}
