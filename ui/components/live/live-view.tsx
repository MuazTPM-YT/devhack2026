"use client";

import { useSearchParams } from "next/navigation";
import { type ReactNode, useState } from "react";

import { Kpis } from "@/components/ui/kpis";
import { PageHead } from "@/components/ui/page-head";
import { Tag } from "@/components/ui/tag";
import { clock, duration, words } from "@/lib/format";
import type { Incident } from "@/lib/live";
import { useLiveContext } from "@/lib/live-context";
import { incidentStatus, verdict } from "@/lib/overview";
import { useNow } from "@/lib/use-now";
import { useReceipt } from "@/lib/use-receipt";

import { Approval } from "./approval";
import { Blast } from "./blast";
import { Checklist } from "./checklist";
import { Evidence } from "./evidence";
import { FlowMap } from "./flow-map";
import { IncidentList, IncidentSelect, statusTag, who } from "./incident-list";
import { Investigation } from "./investigation";
import { Outcome } from "./outcome";
import { Severity } from "./severity";
import sheet from "./sheet.module.css";
import { StageStrip } from "./stage-strip";
import { Timeline } from "./timeline";
import styles from "./live-view.module.css";

function headline(inc: Incident | null, elapsed: number | null): string {
  if (!inc) return "Waiting for an incident";
  const name = who(inc);
  // recovered is not fixed: only a recovery that matched the prediction is called a fix
  const proved = verdict(inc);
  const took = duration(elapsed ?? 0);
  if (proved === "verified") return `${name} fixed in ${took}`;
  if (proved === "mitigated") return `${name} mitigated in ${took}, permanent fix needed`;
  if (proved === "unproven") return `${name} recovered in ${took}, fix not proven`;
  if (inc.outcome === "escalated") return `${name}: woke a human`;
  if (inc.outcome === "handed_off") return `${name}: handed off`;
  return `Working on ${name}`;
}

// one incident: figures, stages, flow and timeline in the middle, the decision sheet on the right
function IncidentBody({ incident, demo, list, picker }: {
  incident: Incident | null; demo: boolean; list: ReactNode; picker: ReactNode;
}) {
  const { policy, link, replay } = useLiveContext();
  const [selected, setSelected] = useState<number | null>(null);
  const open = incident != null && incident.outcome == null;
  const now = useNow(open);
  const receipt = useReceipt(incident?.action?.receiptId ?? null, incident?.outcome != null, demo);
  const elapsed = incident ? (incident.closedAt ?? now) - incident.openedAt : null;
  const status = incident ? incidentStatus(incident, now, policy.maxAgeS) : null;
  const gates = incident?.checklist ?? [];
  const sev = incident?.ticks.findLast((t) => t.severity != null)?.severity ?? incident?.severityAtOpen ?? null;

  return (
    <>
      <PageHead
        eyebrow={incident ? <>Live incident · <span className="mono">{incident.id}</span> · opened {clock(incident.openedAt)}</> : "Live incident"}
        title={headline(incident, elapsed)}
        aside={<>
          <span className={styles.picker}>{picker}</span>
          {status && <Tag tone={statusTag(incident, status).tone}>{statusTag(incident, status).label}</Tag>}
          {link === "demo" && <button type="button" className="btn" onClick={replay}>Replay demo</button>}
        </>}
      />

      {incident && (
        <Kpis label="Incident figures" items={[
          { label: "Severity", value: sev ?? "–", sub: incident.severityAtOpen != null ? `${incident.severityAtOpen} at open` : undefined, tone: sev ? "warn" : "ok" },
          { label: "Unhealthy", value: incident.unhealthy.length, sub: incident.groupings ? `${incident.groupings} folded in` : undefined },
          { label: "Culprit", value: incident.culprit ?? "–", sub: incident.victims.length ? `victims ${incident.victims.join(", ")}` : undefined },
          { label: "Pattern", value: incident.pattern ? words(incident.pattern) : "–", sub: incident.tools.length ? incident.tools.join(", ") : undefined },
          { label: "Gates", value: gates.length ? `${gates.filter((g) => g.passed).length}/${gates.length}` : "–", sub: "passed" },
          { label: open ? "Open for" : "Took", value: elapsed == null ? "–" : duration(elapsed), sub: incident.onsetAt != null ? `detected ${duration(incident.openedAt - incident.onsetAt)} after onset` : undefined },
        ]} />
      )}

      <div className={styles.layout}>
        <div className={styles.list}>{list}</div>
        <div className={styles.center}>
          <StageStrip incident={incident} now={now} />
          <FlowMap incident={incident} upto={selected} />
          <Timeline incident={incident} selected={selected} onSelect={setSelected} now={now} />
        </div>
        {incident && (
          <aside className={`${sheet.sheet} ${styles.sheet}`} aria-label="Incident details">
            <Outcome incident={incident} receipt={receipt} />
            <Approval incident={incident} now={now} />
            <Investigation incident={incident} />
            <Severity incident={incident} receipt={receipt} />
            <Checklist incident={incident} />
            <Blast incident={incident} />
            <Evidence incident={incident} />
          </aside>
        )}
      </div>
    </>
  );
}

export function LiveView() {
  const { state, link, policy } = useLiveContext();
  const asked = useSearchParams().get("incident");
  const now = useNow(true, 5000);
  const id = asked && state.incidents[asked] ? asked : state.current;
  const incident = id ? state.incidents[id] : null;

  return (
    <div className={styles.page}>
      {asked && !state.incidents[asked] && state.order.length > 0 && (
        <p className={styles.note}>Incident <span className="mono">{asked}</span> is not on the bus; showing the latest one.</p>
      )}
      <IncidentBody key={incident?.id ?? "none"} incident={incident} demo={link === "demo"}
        list={<IncidentList state={state} picked={id} now={now} maxAgeS={policy.maxAgeS} />}
        picker={<IncidentSelect state={state} picked={id} />} />
    </div>
  );
}
