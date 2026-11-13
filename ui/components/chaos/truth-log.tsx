"use client";

import { useEffect, useState } from "react";

import { groundTruth, type TruthEntry } from "@/lib/chaos-api";
import { clock, words } from "@/lib/format";

import styles from "./truth-log.module.css";

function detail(e: TruthEntry): string {
  if (e.type === "reset") return Array.isArray(e.restored) && e.restored.length ? `restored ${e.restored.join(", ")}` : "nothing to restore";
  if (e.type === "judge_kubectl") return Array.isArray(e.args) ? `kubectl ${e.args.join(" ")}` : "";
  return [e.target, typeof e.key === "string" ? e.key : null].filter(Boolean).join(" · ");
}

const POLL_MS = 5000;

// what was really broken and when; faults come from the CLI, so poll. The agent never sees this.
export function TruthLog({ className }: { className?: string }) {
  const [entries, setEntries] = useState<TruthEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const tick = () => groundTruth()
      .then((all) => { if (live) { setEntries(all.slice(-15).reverse()); setError(null); } })
      .catch((e: Error) => { if (live) setError(e.message); });
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { live = false; clearInterval(id); };
  }, []);

  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Ground truth</h2>
        <span className="label">bench only</span>
      </div>
      {error && !entries ? (
        <p className="empty bad">Chaos panel unreachable: {error}</p>
      ) : !entries?.length ? (
        <p className="empty">Nothing injected yet.</p>
      ) : (
        <ol className={styles.list}>
          {entries.map((e) => (
            <li key={`${e.ts}-${e.type}`} className={e.type === "reset" ? styles.reset : undefined}>
              <span className={styles.time}>{clock(e.ts)}</span>
              <span className={styles.type}>{words(e.type)}</span>
              <span className={styles.detail}>{detail(e)}</span>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
