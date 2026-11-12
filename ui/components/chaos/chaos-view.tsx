"use client";

import { useState } from "react";

import { FaultBoard } from "./fault-board";
import styles from "./chaos-view.module.css";

export function ChaosView() {
  // bumped after any write so the panels below refetch
  const [, setVersion] = useState(0);
  const changed = () => setVersion((v) => v + 1);

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <p className="label">Admin kubeconfig · the agent never calls this panel</p>
        <h1 className={styles.title}>Chaos</h1>
      </div>
      <FaultBoard onChange={changed} />
    </div>
  );
}
