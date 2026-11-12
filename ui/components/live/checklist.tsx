import { since, words } from "@/lib/format";
import type { Incident } from "@/lib/live";

import styles from "./checklist.module.css";

function Mark({ passed }: { passed: boolean }) {
  return passed ? (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-label="passed" className={styles.pass}>
      <circle cx="9" cy="9" r="8" fill="currentColor" />
      <path d="M5.5 9.2l2.3 2.3 4.7-4.9" fill="none" stroke="var(--frame)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-label="failed" className={styles.fail}>
      <circle cx="9" cy="9" r="8" fill="currentColor" />
      <path d="M6.2 6.2l5.6 5.6M11.8 6.2l-5.6 5.6" stroke="var(--frame)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function Checklist({ incident, className }: { incident: Incident | null; className?: string }) {
  const steps = incident?.checklist ?? [];
  const approval = incident?.approval;
  const passed = steps.filter((s) => s.passed).length;
  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Checklist</h2>
        {steps.length > 0 && <span className="pill">{passed} / {steps.length} passed</span>}
      </div>

      {steps.length === 0 ? (
        <p className="empty">Gates run here once a fix is proposed: schema, hands-off, policy, dry run, net benefit, freshness, trust gate.</p>
      ) : (
        <ol className={styles.list}>
          {steps.map((step, i) => (
            <li key={`${step.name}-${i}`} className={styles.step}>
              <Mark passed={step.passed} />
              <div className={styles.body}>
                <span className={styles.name}>{words(step.name)}</span>
                {step.reason && <span className={styles.reason}>{step.reason}</span>}
              </div>
              <span className={styles.at}>{incident ? since(step.ts, incident.openedAt) : ""}</span>
            </li>
          ))}
        </ol>
      )}

      {approval && (
        <div className={styles.approval}>
          <span className="label">Approval {approval.decision ? words(approval.decision) : "waiting on a human"}</span>
          {approval.forecast && <p className={styles.forecast}>{approval.forecast}</p>}
        </div>
      )}
    </article>
  );
}
