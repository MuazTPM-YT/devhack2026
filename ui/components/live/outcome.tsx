import { More } from "@/components/ui/more";
import { Tag, type Tone } from "@/components/ui/tag";
import { lead, words } from "@/lib/format";
import type { Choice, Incident, Outcome as OutcomeKind } from "@/lib/live";
import type { ReceiptView } from "@/lib/use-receipt";

import { SheetSection } from "./sheet-section";
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

function ownPick(choice: Choice): string {
  const mine = choice.chosen, rule = choice.ruleChoice;
  if (!mine) return "Agent chose its own fix";
  if (!rule) return `Agent chose ${words(mine.tool)}; no rule matched`;
  return rule.tool === mine.tool && rule.target === mine.target
    ? `Agent chose to undo an older change than the rule's first pick (${words(mine.tool)})`
    : `Agent chose ${words(mine.tool)}, not the rule's ${words(rule.tool)}`;
}

// the card the notifier posts, and the receipt numbers behind it
export function Outcome({ incident, receipt }: { incident: Incident; receipt: ReceiptView | null }) {
  const action = incident.action;
  const bound = receipt?.trust?.lower_bound;
  const tag = OUTCOME_TAG[incident.outcome ?? "open"];
  const briefing = incident.briefing && !incident.card?.text.includes(incident.briefing) ? incident.briefing : null;
  const choice = incident.choice;
  const rule = choice?.ruleChoice ?? null;
  // the card often quotes the agent's reason already; say it once
  const reason = choice?.reason && !incident.card?.text.includes(choice.reason) ? choice.reason : null;
  const card = incident.card ? lead(incident.card.text) : null;
  return (
    <SheetSection id="sec-outcome" title="Outcome" aside={<Tag tone={tag.tone}>{tag.label}</Tag>}>
      {card ? (
        <>
          <blockquote className={s.quote}>{card.head}</blockquote>
          {card.rest && <More label="Full card"><p className={s.pre}>{card.rest}</p></More>}
        </>
      ) : (
        <p className={s.note}>{action ? "Watching health after the fix." : "No action taken yet."}</p>
      )}
      {briefing && <p className={s.note}>{briefing}</p>}
      {choice && (
        <p className={s.note}>
          <strong>
            {choice.decision === "decline" ? "Agent declined to act."
              : choice.origin === "model" ? `${ownPick(choice)}; a human approves it.`
                : "Agent agreed with the rule's pick."}
          </strong>
          {choice.decision === "decline" && rule && <> Rule suggested <span className="mono">{rule.tool} → {rule.target}</span>.</>}
        </p>
      )}
      {choice && (reason || choice.alternative) && (
        <More label="Why">
          {reason && <p>{reason}</p>}
          {choice.alternative && <p className="muted">Also weighed: {choice.alternative}</p>}
        </More>
      )}
      <dl className={s.facts}>
        <div><dt>Action</dt><dd className="mono">{action ? `${action.tool} → ${action.target}` : "–"}</dd></div>
        <div><dt>Harm check</dt><dd><Yes value={incident.harmClean} yes="clean" no="side effects" /></dd></div>
        <div><dt>Prediction</dt><dd><Yes value={receipt?.prediction_held} yes="held" no="missed" /></dd></div>
        <div><dt>Trust bound</dt><dd className="num">{typeof bound === "number" ? `${(bound * 100).toFixed(1)}%` : "–"}</dd></div>
      </dl>
      {action && action.receiptId > 0 && (
        <a className={s.link} href={`/receipts?receipt=${action.receiptId}`}>Receipt #{action.receiptId} →</a>
      )}
    </SheetSection>
  );
}
