"use client";

import Link from "next/link";

import { STATUS_TAG, who } from "@/components/live/incident-list";
import { Tag } from "@/components/ui/tag";
import type { HealthNow } from "@/lib/chaos-api";
import { duration } from "@/lib/format";
import { type Experiment, incidentFor, milestones, OPEN, revealRows, runState, symptomAt } from "@/lib/lab";
import type { LiveState } from "@/lib/live";
import { incidentStatus, type Policy } from "@/lib/overview";
import { useNow } from "@/lib/use-now";

import styles from "./lab.module.css";

// one run next to Akira's response to it: what the lab did, what was measured, what Akira did
export function ActiveRun({ run, live, health, policy, busy, onStop, onReveal }: {
  run: Experiment; live: LiveState; health: HealthNow | null; policy: Policy; busy: boolean;
  onStop: () => void; onReveal: () => void;
}) {
  const open = OPEN.includes(run.status);
  const now = useNow(open);
  const incident = incidentFor(run, live.incidents, live.order);
  const symptom = symptomAt(run, health, incident);
  const state = runState(run, incident, symptom);
  const base = run.applied_at ?? run.start_at;
  const steps = milestones(run, incident, symptom);
  const status = incident ? incidentStatus(incident, now, policy.maxAgeS) : null;
  const waiting = incident?.approval && incident.approval.decision == null && incident.outcome == null;
  return (
    <article className="card" aria-live="polite">
      <div className="card-head">
        <h2 className="card-title">{open ? "Running experiment" : "Last experiment"}</h2>
        <Tag tone={state.tone}>{state.label}</Tag>
      </div>

      <dl className={styles.facts}>
        <dt>Run</dt>
        <dd className="mono">{run.id}{run.legacy ? " · from the CLI" : ""}</dd>
        <dt>Target</dt>
        <dd>{run.hidden ? "hidden until you reveal it" : `${run.target} · ${run.spec?.capability} · ${run.spec?.choice}`}</dd>
        <dt>{run.status === "scheduled" ? "Starts in" : open ? "Running for" : "Ran for"}</dt>
        <dd className="num">
          {run.status === "scheduled" ? duration(run.start_at - now)
            : run.applied_at ? duration((run.ended_at ?? now) - run.applied_at) : "never applied"}
        </dd>
        {open && run.expires_at != null && run.status === "active" && (
          <><dt>Lab removes it in</dt><dd className="num">{duration(run.expires_at - now)}</dd></>
        )}
      </dl>
      {run.error && <p className={styles.error} role="alert" style={{ marginTop: 10 }}>{run.error}</p>}

      <div className={styles.actions} style={{ marginTop: 12 }}>
        {(run.status === "active" || run.status === "scheduled") && (
          <button type="button" className={`btn ${styles.danger}`} onClick={onStop} disabled={busy}>
            {busy ? "Stopping…" : "Stop and restore"}
          </button>
        )}
        {run.hidden && <button type="button" className="btn" onClick={onReveal} disabled={busy}>Reveal the answer</button>}
        {run.status === "needs_operator" && (
          <span className={styles.hint}>The lab will not overwrite it. Fix the field by hand, or use Recover everything.</span>
        )}
      </div>

      {run.applied_at != null && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>What happened, in order</h3>
          <ol className={styles.miles}>
            {steps.map((m) => (
              <li key={m.key} className={styles.mile} data-state={m.state}>
                <span className={styles.mark} aria-hidden />
                <span className={styles.mileLabel}>
                  {m.label}<span className="sr-only">: {m.state === "done" ? "done" : m.state === "now" ? "waiting for this" : m.state === "skip" ? "did not happen" : "not yet"}</span>
                </span>
                <span className={styles.mileTime}>{m.at != null ? `+${duration(m.at - base)}` : m.state === "now" ? "waiting" : "–"}</span>
                {m.note && <span className={styles.mileNote}>{m.note}</span>}
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Akira</h3>
        {incident ? (
          <dl className={styles.facts}>
            <dt>Incident</dt>
            <dd>
              {status && <Tag tone={STATUS_TAG[status].tone}>{STATUS_TAG[status].label}</Tag>}{" "}
              <Link href={`/live?incident=${encodeURIComponent(incident.id)}`}>Open {incident.id} →</Link>
            </dd>
            <dt>Suspect</dt>
            <dd>{run.hidden && incident.outcome == null ? who(incident) : `${who(incident)}${incident.pattern ? ` · ${incident.pattern.replace("_", " ")}` : ""}`}</dd>
            {waiting && <><dt>Needs you</dt><dd>Approve or reject in Discord (#wake). The fault stays until then.</dd></>}
            {incident.card && <><dt>Verdict</dt><dd>{incident.card.status}</dd></>}
          </dl>
        ) : (
          <p className="empty">
            {run.applied_at == null ? "Nothing applied yet."
              : open ? "No incident yet. Akira opens one after a breach holds for 30 s; no symptom is also a valid result."
                : "Akira opened no incident for this run."}
          </p>
        )}
      </div>

      {!run.hidden && run.applied_at != null && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>{open ? "Injected (the answer)" : "Reveal: injected against concluded"}</h3>
          <dl className={styles.facts}>
            {revealRows(run, incident).map((r) => (
              <div key={`${r.label}${r.value}`} style={{ display: "contents" }}>
                <dt>{r.label}</dt><dd>{r.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </article>
  );
}
