import { Tag } from "@/components/ui/tag";
import { clock, duration } from "@/lib/format";
import type { Incident } from "@/lib/live";

import { SheetSection } from "./sheet-section";
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
    <SheetSection id="sec-approval" title="Approval" aside={tag} open={!a.decision}>
      {a.diff && <p className={`${s.note} mono`}>{a.diff}</p>}
      {a.forecast && <p className={s.note}>{a.forecast}</p>}
      {!a.decision && <p className={s.empty}>Approve or reject in Discord (#wake) before {clock(a.expiresAt)}.</p>}
    </SheetSection>
  );
}
