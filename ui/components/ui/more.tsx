import type { ReactNode } from "react";

import styles from "./more.module.css";

// the short version stays on screen; the rest is one click away
export function More({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details className={styles.more}>
      <summary className={styles.summary}>{label}</summary>
      <div className={styles.body}>{children}</div>
    </details>
  );
}
