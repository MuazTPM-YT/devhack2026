import { clock, words } from "@/lib/format";
import type { LiveState } from "@/lib/live";

import styles from "./feed.module.css";

const LOUD = new Set(["escalated", "handed_off", "early_abort", "action_undone", "blocked", "injection_quarantined"]);

export function Feed({ feed, className }: { feed: LiveState["feed"]; className?: string }) {
  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Event log</h2>
        <span className="label">{feed.length ? `last ${feed.length}` : ""}</span>
      </div>
      {feed.length === 0 ? (
        <p className="empty">Nothing on the bus yet.</p>
      ) : (
        <ol className={styles.list}>
          {feed.map((e) => (
            <li key={e.seq} className={LOUD.has(e.type) ? styles.loud : undefined}>
              <span className={styles.time}>{clock(e.ts)}</span>
              <span>{words(e.type)}</span>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
