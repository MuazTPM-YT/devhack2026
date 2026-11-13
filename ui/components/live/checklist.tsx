import { plural, since, words } from "@/lib/format";
import type { Incident } from "@/lib/live";

import { SheetSection } from "./sheet-section";
import s from "./sheet.module.css";

// gates that hand the fix to a human are not failures: amber, not red
const ASKS = new Set(["trust_gate", "approval"]);

function Mark({ kind }: { kind: "pass" | "fail" | "ask" }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" className={s[kind]} aria-label={kind === "pass" ? "passed" : kind === "ask" ? "asked a human" : "failed"}>
      <circle cx="8" cy="8" r="7" fill="currentColor" />
      {kind === "pass"
        ? <path d="M4.8 8.2l2.1 2.1 4.3-4.5" fill="none" stroke="var(--frame)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        : kind === "ask" ? <path d="M8 4.5v4M8 11v.5" stroke="var(--frame)" strokeWidth="1.6" strokeLinecap="round" />
        : <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="var(--frame)" strokeWidth="1.5" strokeLinecap="round" />}
    </svg>
  );
}

export function Checklist({ incident }: { incident: Incident }) {
  const steps = incident.checklist;
  const passed = steps.filter((x) => x.passed).length;
  return (
    <SheetSection id="sec-checklist" title="Checklist" open={steps.some((x) => !x.passed && !ASKS.has(x.name))}
      aside={steps.length > 0 && <span className="label">{passed} of {plural(steps.length, "gate")} passed</span>}>
      {steps.length === 0 ? (
        <p className={s.empty}>Gates run once a fix is proposed.</p>
      ) : (
        <ol className={s.steps}>
          {steps.map((step, i) => (
            <li key={`${step.name}-${i}`} className={s.step} title={step.reason ?? undefined}>
              <Mark kind={step.passed ? "pass" : ASKS.has(step.name) ? "ask" : "fail"} />
              <span>
                <span className={s.stepName}>{words(step.name)}</span>
                {step.reason && !step.passed && <span className={s.reason}>{step.reason}</span>}
              </span>
              <span className={s.at}>{since(step.ts, incident.openedAt)}</span>
            </li>
          ))}
        </ol>
      )}
    </SheetSection>
  );
}
