"use client";

import { useSearchParams } from "next/navigation";
import { type ReactNode, useState } from "react";

import { Kpis } from "@/components/ui/kpis";
import { PageHead } from "@/components/ui/page-head";
import { Tag } from "@/components/ui/tag";
import { DEMO_STATUS } from "@/lib/demo";
import { clock, duration, words } from "@/lib/format";
import type { Incident } from "@/lib/live";
import { useLiveContext } from "@/lib/live-context";
import { modeLabel } from "@/lib/orchestration";
import { incidentStatus, verdict } from "@/lib/overview";
import { useOrchestrationStatus } from "@/lib/use-orchestration";
import { useNow } from "@/lib/use-now";
import { useReceipt } from "@/lib/use-receipt";

import { AgentLanes } from "./agent-lanes";
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
  const polled = useOrchestrationStatus(link !== "demo");
  // the replay has no gateway to ask: its coordinated run brings its own answer
  const orch = link === "demo" ? (incident?.orch ? DEMO_STATUS : null) : polled;
  const mode = modeLabel(orch);
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
        title={headline(incident, elapsed)}
        meta={incident ? <><span className="mono">{incident.id}</span> · opened {clock(incident.openedAt)}</> : undefined}
        aside={<>
          <span className={styles.picker}>{picker}</span>
          {mode && <Tag tone={mode.tone} title={mode.title}>{mode.label}</Tag>}
          {status && <Tag tone={statusTag(incident, status).tone}>{statusTag(incident, status).label}</Tag>}
          {link === "demo" && <button type="button" className="btn" onClick={replay}>Replay demo</button>}
        </>}
      />

      {incident && (
        <Kpis label="Incident figures" items={[
          { label: "Severity", value: sev ?? "–", tone: sev ? "warn" : "ok", title: incident.severityAtOpen != null ? `${incident.severityAtOpen} at open` : undefined },
          { label: "Unhealthy", value: incident.unhealthy.length, title: incident.unhealthy.join(", ") || undefined },
          { label: "Culprit", value: incident.culprit ?? "–", title: incident.victims.length ? `victims: ${incident.victims.join(", ")}` : undefined },
          { label: "Pattern", value: incident.pattern ? words(incident.pattern) : "–", title: incident.tools.length ? `rule proposes ${incident.tools.join(", ")}` : undefined },
          { label: "Gates passed", value: gates.length ? `${gates.filter((g) => g.passed).length} of ${gates.length}` : "–" },
          { label: open ? "Open for" : "Took", value: elapsed == null ? "–" : duration(elapsed), title: incident.onsetAt != null ? `detected ${duration(incident.openedAt - incident.onsetAt)} after onset` : undefined },
        ]} />
      )}

      <div className={styles.layout}>
        <div className={styles.list}>{list}</div>
        <div className={styles.center}>
          <StageStrip incident={incident} now={now} />
          {incident && (
            <AgentLanes incident={incident} live={status === "open"} maxRequests={orch?.max_model_requests ?? null}
              now={status === "lost" ? incident.events.at(-1)?.ts ?? now : now} />
          )}
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
