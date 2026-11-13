import { Tag, type Tone } from "@/components/ui/tag";
import type { Incident, Outcome as OutcomeKind } from "@/lib/live";
import type { ReceiptView } from "@/lib/use-receipt";

import s from "./sheet.module.css";

export const OUTCOME_TAG: Record<OutcomeKind | "open", { tone: Tone; label: string }> = {
  open: { tone: "accent", label: "In progress" },
  resolved: { tone: "ok", label: "Resolved" },
  escalated: { tone: "bad", label: "Escalated" },
  handed_off: { tone: "warn", label: "Handed off" },
};

function Yes({ value, yes, no }: { value: boolean | null | undefined; yes: string; no: string }) {
  if (value == null) return <span className="muted">–</span>;
  return <span className={value ? "ok" : "bad"}>{value ? yes : no}</span>;
}

// the card the notifier posts, and the receipt numbers behind it
export function Outcome({ incident, receipt }: { incident: Incident; receipt: ReceiptView | null }) {
  const action = incident.action;
  const bound = receipt?.trust?.lower_bound;
  const tag = OUTCOME_TAG[incident.outcome ?? "open"];
  const briefing = incident.briefing && !incident.card?.text.includes(incident.briefing) ? incident.briefing : null;
  return (
    <section className={s.sec} aria-labelledby="sec-outcome">
      <div className={s.head}>
        <h2 id="sec-outcome" className={s.title}>Outcome</h2>
        <Tag tone={tag.tone}>{tag.label}</Tag>
      </div>
      {incident.card ? (
        <blockquote className={s.quote}>{incident.card.text}</blockquote>
      ) : (
        <p className={s.note}>{action ? "Watching health after the fix." : "No action taken yet."}</p>
      )}
      {briefing && <p className={s.note}>{briefing}</p>}
      <dl className={s.facts}>
        <div><dt>Action</dt><dd className="mono">{action ? `${action.tool} → ${action.target}` : "–"}</dd></div>
        <div><dt>Harm check</dt><dd><Yes value={incident.harmClean} yes="clean" no="side effects" /></dd></div>
        <div><dt>Prediction</dt><dd><Yes value={receipt?.prediction_held} yes="held" no="missed" /></dd></div>
        <div><dt>Trust bound</dt><dd className="num">{typeof bound === "number" ? `${(bound * 100).toFixed(1)}%` : "–"}</dd></div>
      </dl>
      {action && action.receiptId > 0 && (
        <a className={s.link} href={`/receipts?receipt=${action.receiptId}`}>Receipt #{action.receiptId} →</a>
      )}
    </section>
  );
}
