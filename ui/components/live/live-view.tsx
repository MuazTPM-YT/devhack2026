"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { words } from "@/lib/format";
import type { Incident } from "@/lib/live";
import { useLiveContext } from "@/lib/live-context";
import { useNow } from "@/lib/use-now";
import { useReceipt } from "@/lib/use-receipt";

import { Blast } from "./blast";
import { Checklist } from "./checklist";
import { Evidence } from "./evidence";
import { FlowMap } from "./flow-map";
import { Outcome } from "./outcome";
import { Severity } from "./severity";
import { StageStrip } from "./stage-strip";
import { Timeline } from "./timeline";
import styles from "./live-view.module.css";

const secs = (s: number) => (s < 60 ? `${s.toFixed(1)} s` : `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, "0")}s`);

// everything for one incident; keyed by id so inspecting an old event resets on switch
function IncidentBody({ incident, demo }: { incident: Incident | null; demo: boolean }) {
  const [selected, setSelected] = useState<number | null>(null);
  const open = incident != null && incident.outcome == null;
  const now = useNow(open);
  const receipt = useReceipt(incident?.action?.receiptId ?? null, incident?.outcome != null, demo);
  const elapsed = incident ? (incident.closedAt ?? now) - incident.openedAt : null;

  return (
    <>
      <div className={styles.stats}>
        <span className="pill" title="Time since the incident opened">
          {open ? "open for" : "took"} <b className={styles.num}>{elapsed == null ? "–" : secs(Math.max(0, elapsed))}</b>
        </span>
        {incident?.onsetAt != null && (
          <span className="pill" title="Detection delay: first breach to incident opened">
            detected <b className={styles.num}>{secs(Math.max(0, incident.openedAt - incident.onsetAt))}</b> after onset
          </span>
        )}
        {incident?.action && <span className="pill">action <b className="mono">{incident.action.tool} → {incident.action.target}</b></span>}
      </div>

      <StageStrip incident={incident} now={now} />
      <FlowMap incident={incident} upto={selected} />

      <div className={styles.grid}>
        <Timeline incident={incident} selected={selected} onSelect={setSelected} now={now} className={styles.main} />
        <div className={styles.side}>
          <Severity incident={incident} receipt={receipt} />
          <Outcome incident={incident} receipt={receipt} />
          <Checklist incident={incident} />
        </div>
        <Blast incident={incident} className={styles.half} />
        <Evidence incident={incident} className={styles.half} />
      </div>
    </>
  );
}

export function LiveView() {
  const { state, link, replay } = useLiveContext();
  const asked = useSearchParams().get("incident");
  const id = asked && state.incidents[asked] ? asked : state.current;
  const incident = id ? state.incidents[id] : null;
  const latest = id === state.current;

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <div>
          <p className="label">
            {incident ? <>Incident <span className="mono">{incident.id}</span>{!latest && " · older incident"}</> : "No incident yet"}
          </p>
          <h1 className={styles.title}>Live incident</h1>
        </div>
        <div className={styles.meta}>
          {incident && (
            <span className={`pill ${incident.outcome && incident.outcome !== "resolved" ? "pill-dark" : ""}`}>
              <span className={`dot ${!incident.outcome ? "dot-warn dot-live" : incident.outcome === "resolved" ? "dot-ok" : "dot-bad"}`} />
              {incident.outcome ? words(incident.outcome) : "in progress"}
            </span>
          )}
          {link === "demo" && <button type="button" className="pill" onClick={replay}>Replay demo</button>}
        </div>
      </header>

      {asked && !state.incidents[asked] && state.order.length > 0 && (
        <p className={styles.note}>Incident <span className="mono">{asked}</span> is not on the bus; showing the latest one.</p>
      )}

      <IncidentBody key={incident?.id ?? "none"} incident={incident} demo={link === "demo"} />
    </div>
  );
}
