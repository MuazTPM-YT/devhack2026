import Link from "next/link";

import { plural, words } from "@/lib/format";
import type { Incident } from "@/lib/live";
import { reasonText } from "@/lib/orchestration";

import { SheetSection } from "./sheet-section";
import s from "./sheet.module.css";

// coordinated mode only: which services share this investigation and why, and what was kept apart.
// Who worked on it and what it cost is the Agents band's job
export function Investigation({ incident }: { incident: Incident }) {
  const o = incident.orch;
  if (!o || (o.services.length === 0 && o.related.length === 0)) return null;
  return (
    <SheetSection id="sec-scope" title="Scope" open={false}
      aside={<span className="label">{plural(o.services.length, "service")}{o.related.length > 0 ? ` · ${o.related.length} related` : ""}</span>}>
      {o.services.length > 0 && (
        <p className={s.note}>
          {o.services.join(", ")}{o.reasons.length > 0 && <> · {o.reasons.map(reasonText).join(" · ")}</>}
        </p>
      )}
      {o.related.length > 0 && (
        <p className={s.note}>
          Possibly related:{" "}
          {o.related.map((r, i) => (
            <span key={r.incidentId}>
              {i > 0 && ", "}
              <Link href={`/live?incident=${encodeURIComponent(r.incidentId)}`} className="mono">{r.incidentId}</Link>
              {" "}({words(r.reason)})
            </span>
          ))}. Kept apart: no shared cause is proven.
        </p>
      )}
    </SheetSection>
  );
}
