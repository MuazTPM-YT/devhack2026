"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Tag, type Tone } from "@/components/ui/tag";
import { clock, duration } from "@/lib/format";
import type { Incident, LiveState } from "@/lib/live";
import { orchSummary } from "@/lib/orchestration";
import { type IncidentStatus, incidentStatus, VERDICT, verdict } from "@/lib/overview";

import styles from "./incident-list.module.css";

export const STATUS_TAG: Record<IncidentStatus, { tone: Tone; label: string }> = {
  open: { tone: "accent", label: "Open" },
  resolved: { tone: "ok", label: "Fixed" },
  escalated: { tone: "bad", label: "Escalated" },
  handed_off: { tone: "warn", label: "Handed off" },
  lost: { tone: "idle", label: "No outcome" },
};

// resolved splits into what was actually proven (lib/overview.ts verdict)
export function statusTag(inc: Incident | null, status: IncidentStatus, short = false): { tone: Tone; label: string } {
  const proved = inc ? verdict(inc) : null;
  if (!proved) return STATUS_TAG[status];
  return { tone: VERDICT[proved].tone, label: short ? VERDICT[proved].short : VERDICT[proved].label };
}

const MAX = 60;

export const who = (inc: Incident) => inc.culprit ?? inc.unhealthy[0] ?? "detecting…";

// every incident the bus replayed, newest first; links keep the choice in the URL
export function IncidentList({ state, picked, now, maxAgeS }: {
  state: LiveState; picked: string | null; now: number; maxAgeS: number | null;
}) {
  const ids = state.order.slice(0, MAX);
  return (
    <nav className={styles.pane} aria-label="Incidents">
      <h2 className={styles.title}>Incidents <span className="num">{state.order.length}</span></h2>
      {ids.length === 0 ? <p className={styles.none}>None yet.</p> : (
        <ul className={styles.list}>
          {ids.map((id) => {
            const inc = state.incidents[id];
            const status = incidentStatus(inc, now, maxAgeS);
            const st = statusTag(inc, status, true);
            const took = (inc.closedAt ?? now) - inc.openedAt;
            return (
              <li key={id}>
                <Link href={`/live?incident=${encodeURIComponent(id)}`} title={`${who(inc)} · ${id}`}
                  className={id === picked ? `${styles.row} ${styles.on}` : styles.row} aria-current={id === picked ? "true" : undefined}>
                  <span className={styles.rowTop}>
                    <span className={styles.who}>{who(inc)}</span>
                    <Tag tone={st.tone}>{st.label}</Tag>
                  </span>
                  <span className={styles.meta}>{clock(inc.openedAt)} · {status === "lost" ? "–" : duration(took)}</span>
                  {orchSummary(inc) && <span className={styles.meta}>{orchSummary(inc)}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </nav>
  );
}

// narrow screens: the same choice as a select
export function IncidentSelect({ state, picked }: { state: LiveState; picked: string | null }) {
  const router = useRouter();
  if (state.order.length < 2) return null;
  return (
    <label className={styles.select}>
      <span className="sr-only">Incident</span>
      <select value={picked ?? ""} onChange={(e) => router.push(`/live?incident=${encodeURIComponent(e.target.value)}`)}>
        {state.order.slice(0, MAX).map((id) => (
          <option key={id} value={id}>{who(state.incidents[id])} · {clock(state.incidents[id].openedAt)}</option>
        ))}
      </select>
    </label>
  );
}
