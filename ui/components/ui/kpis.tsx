import type { ReactNode } from "react";

import styles from "./kpis.module.css";

export interface Kpi { label: string; value: ReactNode; sub?: ReactNode; tone?: "bad" | "warn" | "ok"; title?: string }

// one ruled row of figures under a page head
export function Kpis({ items, label }: { items: Kpi[]; label: string }) {
  return (
    <dl className={styles.row} aria-label={label}>
      {items.map((k) => (
        <div key={k.label} className={styles.cell} title={k.title}>
          <dt className={styles.label}>{k.label}</dt>
          <dd key={typeof k.value === "object" ? k.label : String(k.value)} className={`${styles.value} ${k.tone ? styles[k.tone] : ""}`}
            data-long={typeof k.value === "string" && k.value.length > 12}>{k.value}</dd>
          {k.sub != null && <dd className={styles.sub}>{k.sub}</dd>}
        </div>
      ))}
    </dl>
  );
}
