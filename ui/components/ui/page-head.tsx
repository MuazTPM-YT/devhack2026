import type { ReactNode } from "react";

import styles from "./page-head.module.css";

// title, one quiet line of facts under it, right-hand slot, heavy rule underneath: every page starts the same way
export function PageHead({ title, meta, aside }: { title: ReactNode; meta?: ReactNode; aside?: ReactNode }) {
  return (
    <header className={styles.head}>
      <div className={styles.text}>
        <h1 className={styles.title}>{title}</h1>
        {meta && <p className={styles.meta}>{meta}</p>}
      </div>
      {aside && <div className={styles.aside}>{aside}</div>}
    </header>
  );
}
