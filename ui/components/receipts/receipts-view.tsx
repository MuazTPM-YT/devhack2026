"use client";

import { useEffect, useState } from "react";

import outcome from "@/components/live/outcome.module.css";
import page from "@/components/page.module.css";
import { words } from "@/lib/format";
import { type AuditResult, listReceipts, type ReceiptItem, verifyAudit } from "@/lib/receipts";

import styles from "./receipts-view.module.css";

const secs = (v: number | null | undefined) => (v == null ? "–" : `${v.toFixed(1)} s`);

function Yes({ value, yes, no }: { value: boolean | null | undefined; yes: string; no: string }) {
  if (value == null) return <span className="muted">–</span>;
  return <span className={value ? "ok" : "bad"}>{value ? yes : no}</span>;
}

function outcomeDot(o: string) {
  if (o === "success") return "dot dot-ok";
  if (o === "pending") return "dot dot-warn";
  return o === "undone" ? "dot dot-bad" : "dot";
}

// hash chain over data/audit.jsonl: names the first broken record if anyone edited the log
function AuditCheck() {
  const [state, setState] = useState<"idle" | "busy" | "missing" | AuditResult | Error>("idle");
  const run = () => {
    setState("busy");
    verifyAudit().then((r) => setState(r ?? "missing")).catch((e: Error) => setState(e));
  };
  let text = null;
  if (state === "missing") text = <span className="muted">Gateway has no <span className="mono">/audit/verify</span> route yet.</span>;
  else if (state instanceof Error) text = <span className="bad">Gateway unreachable: {state.message}</span>;
  else if (typeof state === "object") text = state.ok
    ? <span className="ok">Chain intact · {state.records} records</span>
    : <span className="bad">{state.error}</span>;
  return (
    <div className={styles.audit}>
      <button type="button" className={styles.verify} onClick={run} disabled={state === "busy"}>
        {state === "busy" ? "Checking…" : "Verify audit log"}
      </button>
      <span aria-live="polite" className={styles.auditText}>{text}</span>
    </div>
  );
}

function Detail({ item }: { item: ReceiptItem }) {
  const r = item.receipt;
  return (
    <article className="card">
      <div className="card-head">
        <h2 className="card-title">Receipt #{item.id}</h2>
        <span className="pill pill-dark">{words(r.outcome)}</span>
      </div>
      <blockquote className={outcome.card}>{item.card.text}</blockquote>

      <dl className={styles.facts}>
        <div><dt>Action</dt><dd className="mono">{r.tool} → {r.target}</dd></div>
        <div><dt>Incident</dt><dd className="mono">{r.incident_id}</dd></div>
        <div><dt>Forecast</dt><dd>{secs(r.forecast_s)}</dd></div>
        <div><dt>Took</dt><dd>{secs(r.elapsed_s)}</dd></div>
        <div><dt>Prediction</dt><dd><Yes value={r.prediction_held} yes="held" no="missed" /></dd></div>
        <div><dt>Harm check</dt><dd><Yes value={r.harm_clean} yes="clean" no="side effects" /></dd></div>
        <div><dt>Trust bound</dt><dd>{typeof r.trust.lower_bound === "number" ? `${(r.trust.lower_bound * 100).toFixed(1)}%` : "–"}</dd></div>
        <div><dt>Gate</dt><dd>{r.trust.open == null ? "–" : r.trust.open ? "open · auto" : "closed · asked"}</dd></div>
      </dl>

      {r.checklist.length > 0 && (
        <>
          <h3 className={styles.sub}>Checklist</h3>
          <ol className={styles.steps}>
            {r.checklist.map((s, i) => (
              <li key={`${s.name}-${i}`}>
                <span className={s.passed ? "dot dot-ok" : "dot dot-bad"} />
                <span className={styles.stepName}>{words(s.name)}</span>
                {s.reason && s.name !== "approval" && <span className={styles.reason}>{s.reason}</span>}
              </li>
            ))}
          </ol>
        </>
      )}

      {r.pods_touched.length > 0 && (
        <>
          <h3 className={styles.sub}>Pods touched</h3>
          <p className={styles.pods}>{r.pods_touched.map((p) => <span key={p} className="mono">{p}</span>)}</p>
        </>
      )}

      <details className={styles.raw}>
        <summary>Diff and undo</summary>
        <h3 className={styles.sub}>Diff</h3>
        <pre>{JSON.stringify(r.diff, null, 2)}</pre>
        <h3 className={styles.sub}>Inverse (what undo applies)</h3>
        <pre>{JSON.stringify(r.inverse, null, 2)}</pre>
        <p className="label">Namespace hash before <span className="mono">{r.hash_before?.slice(0, 16) ?? "–"}</span> · after <span className="mono">{r.hash_after?.slice(0, 16) ?? "–"}</span></p>
      </details>
    </article>
  );
}

export function ReceiptsView() {
  const [data, setData] = useState<{ items: ReceiptItem[]; listed: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<number | null>(null);

  useEffect(() => {
    listReceipts()
      .then((d) => { setData(d); setPicked(d.items[0]?.id ?? null); })
      .catch((e: Error) => setError(e.message));
  }, []);

  const items = data?.items ?? [];
  const current = items.find((i) => i.id === picked) ?? null;

  return (
    <div className={page.page}>
      <div className={page.head}>
        <div>
          <p className="label">Every action the agent took, what it changed and how to undo it</p>
          <h1 className={page.title}>Receipts</h1>
        </div>
        <AuditCheck />
      </div>

      <div className={page.grid}>
        <article className={`card ${page.span4}`}>
          <div className="card-head">
            <h2 className="card-title">Actions</h2>
            {items.length > 0 && <span className="label">{items.length}</span>}
          </div>
          {error ? (
            <p className="empty bad">Gateway unreachable: {error}</p>
          ) : !data ? (
            <p className="empty">Loading…</p>
          ) : items.length === 0 ? (
            <p className="empty">No action taken yet. A receipt is written the moment one runs.</p>
          ) : (
            <ul className={styles.list}>
              {items.map((i) => (
                <li key={i.id}>
                  <button type="button" onClick={() => setPicked(i.id)}
                    className={i.id === picked ? `${styles.row} ${styles.on}` : styles.row}
                    aria-pressed={i.id === picked}>
                    <span className={styles.rowId}>#{i.id}</span>
                    <span className={styles.rowMain}>
                      <span className="mono">{i.receipt.tool} → {i.receipt.target}</span>
                      <span className={styles.rowSub}><span className={outcomeDot(i.receipt.outcome)} />{words(i.receipt.outcome)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {data && !data.listed && items.length > 0 && (
            <p className={styles.hint}>Found by id; the gateway has no list route yet.</p>
          )}
        </article>

        <div className={page.span8}>
          {current ? <Detail item={current} /> : (
            <article className="card"><p className="empty">Pick a receipt to see it.</p></article>
          )}
        </div>
      </div>
    </div>
  );
}
