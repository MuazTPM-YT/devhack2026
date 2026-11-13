"use client";

import { useEffect, useState } from "react";

import { pct, type TrustTable } from "@/lib/pages";

import styles from "./pages.module.css";

// ledger per (pattern, tool, target): what the gate would decide right now
export function TrustView() {
  const [table, setTable] = useState<TrustTable | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/gateway/trust")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${r.statusText}`))))
      .then(setTable)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          <p className="label">Autonomy is earned from measured outcomes, never from confidence</p>
          <h1 className={styles.title}>Trust</h1>
        </div>
        {table && <span className="pill">bar {pct(table.bar)} at {pct(table.confidence)} confidence</span>}
      </div>
      <section className="card">
        {error && <p className="empty">Gateway unreachable: {error}</p>}
        {table && table.rows.length === 0 && <p className="empty">No runs recorded yet. Every action asks a human.</p>}
        {table && table.rows.length > 0 && (
          <div className={styles.wrap}>
            <table className={styles.table}>
              <thead>
                <tr><th>Pattern</th><th>Tool</th><th>Target</th><th>Rehearsal ok / fail</th>
                  <th>Real ok / fail</th><th>Proven at least</th><th>Gate</th></tr>
              </thead>
              <tbody>
                {table.rows.map((r) => (
                  <tr key={`${r.pattern}/${r.action}/${r.target}`}>
                    <td>{r.pattern}</td><td className="mono">{r.action}</td><td>{r.target}</td>
                    <td>{r.rehearsal[0]} / {r.rehearsal[1]}</td><td>{r.real[0]} / {r.real[1]}</td>
                    <td>{pct(r.lower_bound)}</td>
                    <td><span className={r.open ? "ok" : "bad"}>{r.open ? "open: automatic" : "closed: asks"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className={styles.note}>
          One failure closes a gate. With zero failures: 10 runs prove 74%, 29 prove 90%, 59 prove 95%.
        </p>
      </section>
    </div>
  );
}
