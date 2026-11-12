"use client";

import { useSearchParams } from "next/navigation";

import { words } from "@/lib/format";
import { type Link, useLive } from "@/lib/use-live";

import { StageStrip } from "./stage-strip";
import styles from "./live-view.module.css";

const LINK_COPY: Record<Link, { text: string; dot: string }> = {
  connecting: { text: "connecting to gateway", dot: "dot-warn" },
  live: { text: "live", dot: "dot-ok" },
  down: { text: "gateway unreachable", dot: "dot-bad" },
  demo: { text: "demo replay", dot: "dot-warn" },
};

export function LiveView() {
  const demo = useSearchParams().get("demo") === "1";
  const { state, link, replay } = useLive(demo);
  const incident = state.current ? state.incidents[state.current] : null;

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          <p className="label">{incident ? `Incident ${incident.id}` : "No open incident"}</p>
          <h1 className={styles.title}>Live incident</h1>
        </div>
        <div className={styles.meta}>
          {incident?.outcome && (
            <span className={`pill ${incident.outcome === "resolved" ? "" : "pill-dark"}`}>
              <span className={`dot ${incident.outcome === "resolved" ? "dot-ok" : "dot-bad"}`} />
              {words(incident.outcome)}
            </span>
          )}
          <span className="pill">
            <span className={`dot ${LINK_COPY[link].dot}`} />
            {LINK_COPY[link].text}
          </span>
          {demo && (
            <button type="button" className={`pill ${styles.button}`} onClick={replay}>Replay</button>
          )}
        </div>
      </div>

      <StageStrip incident={incident} />
    </div>
  );
}
