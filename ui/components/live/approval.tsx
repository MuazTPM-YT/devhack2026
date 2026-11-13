import { Tag } from "@/components/ui/tag";
import { clock, duration } from "@/lib/format";
import type { Incident } from "@/lib/live";

import s from "./sheet.module.css";

// read-only: approvers decide in Discord; this shows what they are deciding and how long is left
export function Approval({ incident, now }: { incident: Incident; now: number }) {
  const a = incident.approval;
  if (!a) return null;
  const left = a.expiresAt - now;
  const tag = a.decision === "approved" ? <Tag tone="ok">Approved</Tag>
    : a.decision ? <Tag tone="bad">{a.decision}</Tag>
    : left > 0 ? <Tag tone="warn">Waiting · {duration(left)}</Tag>
    : <Tag tone="bad">Expired</Tag>;
  return (
    <section className={s.sec} aria-labelledby="sec-approval">
      <div className={s.head}>
        <h2 id="sec-approval" className={s.title}>Approval</h2>
        {tag}
      </div>
      {a.diff && <p className={`${s.note} mono`}>{a.diff}</p>}
      {a.forecast && <p className={s.note}>{a.forecast}</p>}
      <p className={s.empty}>
        {a.decision ? `Decided: ${a.decision}.` : `Approve or reject in Discord (#wake) before ${clock(a.expiresAt)}.`}
      </p>
    </section>
  );
}
