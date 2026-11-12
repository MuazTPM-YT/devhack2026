import { words } from "@/lib/format";
import type { Incident } from "@/lib/live";
import type { ReceiptView } from "@/lib/use-receipt";

import styles from "./outcome.module.css";

function Yes({ value, yes, no }: { value: boolean | null | undefined; yes: string; no: string }) {
  if (value == null) return <span className="muted">–</span>;
  return <span className={value ? "ok" : "bad"}>{value ? yes : no}</span>;
}

// the final card the notifier also posts, plus the receipt numbers behind it
export function Outcome({ incident, receipt, className }: {
  incident: Incident | null; receipt: ReceiptView | null; className?: string;
}) {
  const action = incident?.action;
  const bound = receipt?.trust?.lower_bound;
  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Outcome</h2>
        {incident?.outcome && <span className="pill pill-dark">{words(incident.outcome)}</span>}
      </div>

      {incident?.card ? (
        <blockquote className={styles.card}>{incident.card.text}</blockquote>
      ) : (
        <p className="empty">{action ? "Watching health after the fix." : "No action taken yet."}</p>
      )}
      {incident?.briefing && <p className={styles.briefing}>{incident.briefing}</p>}

      <dl className={styles.facts}>
        <div><dt>Action</dt><dd>{action ? <span className="mono">{action.tool} → {action.target}</span> : "–"}</dd></div>
        <div><dt>Harm check</dt><dd><Yes value={incident?.harmClean} yes="clean" no="side effects" /></dd></div>
        <div><dt>Prediction</dt><dd><Yes value={receipt?.prediction_held} yes="held" no="missed" /></dd></div>
        <div><dt>Trust bound</dt><dd>{typeof bound === "number" ? `${(bound * 100).toFixed(1)}%` : "–"}</dd></div>
      </dl>

      {action && action.receiptId > 0 && (
        <a className={styles.receipt} href={`/api/gateway/receipts/${action.receiptId}`} target="_blank" rel="noreferrer">
          Receipt #{action.receiptId} ↗
        </a>
      )}
    </article>
  );
}
