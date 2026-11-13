import type { ReactNode } from "react";

import styles from "./page-head.module.css";

// eyebrow, title, right-hand slot, heavy rule underneath: every page starts the same way
export function PageHead({ eyebrow, title, aside }: { eyebrow: ReactNode; title: ReactNode; aside?: ReactNode }) {
  return (
    <header className={styles.head}>
      <div className={styles.text}>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h1 className={styles.title}>{title}</h1>
      </div>
      {aside && <div className={styles.aside}>{aside}</div>}
    </header>
  );
}
