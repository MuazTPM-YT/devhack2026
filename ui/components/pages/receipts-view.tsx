"use client";

import { useEffect, useState } from "react";

import { type ReceiptItem, secs } from "@/lib/pages";

import styles from "./pages.module.css";

type Audit = { ok: boolean; records?: number; error?: string } | null;

// every executed action, its card, and the hash-chain check (plan §6.7)
export function ReceiptsView() {
  const [items, setItems] = useState<ReceiptItem[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [audit, setAudit] = useState<Audit>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/gateway/receipts")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${r.statusText}`))))
      .then((list: ReceiptItem[]) => { setItems(list); setOpen(list[0]?.id ?? null); })
      .catch((e: Error) => setError(e.message));
  }, []);

  async function verify() {
    setAudit(null);
    try {
      setAudit(await (await fetch("/api/gateway/audit/verify")).json());
    } catch (e) {
      setAudit({ ok: false, error: e instanceof Error ? e.message : String(e) });
    }
  }

  const chosen = items?.find((i) => i.id === open);
  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          <p className="label">What the agent did, how to undo it, and proof nobody edited the log</p>
          <h1 className={styles.title}>Receipts</h1>
        </div>
        <div>
          <button type="button" className={`pill ${styles.button}`} onClick={verify}>Verify audit log</button>{" "}
          {audit && (
            <span className="pill">
              <span className={`dot ${audit.ok ? "dot-ok" : "dot-bad"}`} />
              {audit.ok ? `${audit.records} records, chain intact` : audit.error}
            </span>
          )}
        </div>
      </div>
      <section className="card">
        {error && <p className="empty">Gateway unreachable: {error}</p>}
        {items && items.length === 0 && <p className="empty">No actions yet.</p>}
        {items && items.length > 0 && (
          <div className={styles.wrap}>
            <table className={styles.table}>
              <thead>
                <tr><th>#</th><th>Incident</th><th>Tool</th><th>Target</th><th>Outcome</th>
                  <th>Prediction</th><th>Harm check</th><th>Verified in</th></tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.id} className={`${styles.row} ${i.id === open ? styles.on : ""}`}
                    onClick={() => setOpen(i.id)} tabIndex={0}
                    onKeyDown={(e) => { if (e.key === "Enter") setOpen(i.id); }}>
                    <td>{i.id}</td><td className="mono">{i.receipt.incident_id}</td>
                    <td className="mono">{i.receipt.tool}</td><td>{i.receipt.target}</td><td>{i.receipt.outcome}</td>
                    <td>{i.receipt.prediction_held == null ? "–" : i.receipt.prediction_held ? "held" : "missed"}</td>
                    <td>{i.receipt.harm_clean == null ? "–" : i.receipt.harm_clean ? "clean" : "harm"}</td>
                    <td>{secs(i.receipt.elapsed_s)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {chosen && (
        <section className="card">
          <div className="card-head">
            <h2 className="card-title">Receipt #{chosen.id}</h2>
            <a className="pill" href={`/api/gateway/receipts/${chosen.id}`} target="_blank" rel="noreferrer">raw JSON ↗</a>
          </div>
          <pre className={styles.card}>{chosen.card.text}</pre>
        </section>
      )}
    </div>
  );
}
