"use client";

import { useLayoutEffect, useRef } from "react";

import { since } from "@/lib/format";
import { useMoreRight } from "@/lib/use-more-right";
import { EDGE_LABEL, flowAt, NODES, type NodeId, nodesFor } from "@/lib/request-flow";
import type { Incident } from "@/lib/live";

import styles from "./flow-map.module.css";

// sized for the centre pane (~560-900 px wide), so 1 viewBox unit stays close to 1 css px
const W = 660;
const H = 318;
const NW = 116;
const NH = 58;

// component centres; the main row is the incident's path left to right
const POS: Record<NodeId, [number, number]> = {
  shop: [62, 160], observer: [194, 160], brain: [326, 160], gateway: [458, 160], k8s: [598, 160],
  llm: [326, 40], notifier: [458, 40], verifier: [528, 278], specialist: [194, 40],
};

type Pt = [number, number];
const L = (id: NodeId) => POS[id][0] - NW / 2;
const R = (id: NodeId) => POS[id][0] + NW / 2;
const T = (id: NodeId) => POS[id][1] - NH / 2;
const B = (id: NodeId) => POS[id][1] + NH / 2;
const Y = (id: NodeId) => POS[id][1];
const X = (id: NodeId) => POS[id][0];

// links drawn one way; a pulse going the other way walks the same points backwards
const EDGES: Record<string, Pt[]> = {
  "shop>observer": [[R("shop"), Y("shop")], [L("observer"), Y("observer")]],
  "observer>brain": [[R("observer"), Y("observer")], [L("brain"), Y("brain")]],
  "brain>gateway": [[R("brain"), Y("brain")], [L("gateway"), Y("gateway")]],
  "gateway>k8s": [[R("gateway"), Y("gateway")], [L("k8s"), Y("k8s")]],
  "brain>llm": [[X("brain"), T("brain")], [X("llm"), B("llm")]],
  // above the shop>brain line (y 100), below the specialist box
  "brain>specialist": [[X("brain") - 14, T("brain")], [X("brain") - 14, 84], [X("specialist") + 30, 84],
    [X("specialist") + 30, B("specialist")]],
  "specialist>llm": [[R("specialist"), Y("specialist")], [L("llm"), Y("llm")]],
  "gateway>notifier": [[X("gateway"), T("gateway")], [X("notifier"), B("notifier")]],
  "shop>brain": [[X("shop"), T("shop")], [X("shop"), 100], [X("brain") - 34, 100], [X("brain") - 34, T("brain")]],
  "observer>verifier": [[X("observer"), B("observer")], [X("observer"), Y("verifier")], [L("verifier"), Y("verifier")]],
  "k8s>verifier": [[X("k8s"), B("k8s")], [X("k8s"), Y("verifier")], [R("verifier"), Y("verifier")]],
};

function edge(from: NodeId, to: NodeId): Pt[] | null {
  return EDGES[`${from}>${to}`] ?? EDGES[`${to}>${from}`]?.slice().reverse() ?? null;
}

const d = (pts: Pt[]) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ");

// the focused event's whole route as one polyline, for the travelling pulse
function route(path: NodeId[]): Pt[] {
  const pts: Pt[] = [];
  for (let i = 1; i < path.length; i++) pts.push(...(edge(path[i - 1], path[i]) ?? []));
  return pts;
}

// dot walking the focused route (the explainer, so it may run past 300 ms; capped at 900 ms); begun
// before paint, since SMIL begin=0 is already over on a newly mounted node
function Pulse({ pts }: { pts: Pt[] }) {
  const ref = useRef<SVGAnimateMotionElement>(null);
  useLayoutEffect(() => { ref.current?.beginElement(); }, []);
  return (
    <circle r="5" cx="0" cy="0" className={styles.pulse}>
      <animateMotion ref={ref} begin="indefinite" dur={`${Math.min(0.9, Math.max(0.5, pts.length * 0.15))}s`}
        path={d(pts)} fill="freeze" calcMode="spline" keyPoints="0;1" keyTimes="0;1" keySplines="0.77 0 0.175 1" />
    </circle>
  );
}

function cut(text: string, n: number) {
  return text.length > n ? `${text.slice(0, n - 1)}…` : text;
}

// live map of the services one incident passes through; `upto` picks the event in focus
export function FlowMap({ incident, upto }: { incident: Incident | null; upto: number | null }) {
  const events = incident?.events ?? [];
  const at = upto ?? events.length - 1;
  const open = incident != null && incident.outcome == null && upto == null;
  const view = flowAt(events, at, open);
  const shown = nodesFor(events);
  const hop = route(view.path);
  const routeKeys = new Set(view.path.slice(1).map((id, i) => `${view.path[i]}>${id}`));
  const caption = view.path.length > 1
    ? view.path.slice(1).map((id, i) => `${NODES[view.path[i]].title} → ${NODES[id].title}: ${EDGE_LABEL[`${view.path[i]}>${id}`] ?? ""}`).join("   ·   ")
    : view.path.length === 1 ? `inside ${NODES[view.path[0]].title}` : "";
  const focusLine = view.focus ? view.nodes[view.path.at(-1) ?? "brain"].last : null;
  const [scrollRef, moreRight] = useMoreRight();

  return (
    <article className="card">
      <div className="card-head">
        <h2 className="card-title">Request flow</h2>
        <div className={styles.legend} aria-hidden="true">
          <span><i className={styles.kDone} />passed through</span>
          <span><i className={styles.kActive} />working now</span>
          <span><i className={styles.kFailed} />failed here</span>
        </div>
      </div>

      <div className={styles.scroll} ref={scrollRef} data-more={moreRight}>
        <svg viewBox={`0 0 ${W} ${H}`} className={styles.map} role="img"
          aria-label={view.focus && focusLine ? `${focusLine.title}. ${caption}` : "No incident yet; every service idle"}>
          {Object.entries(EDGES).map(([key, pts]) => {
            const [a, b] = key.split(">") as [NodeId, NodeId];
            if (!shown.includes(a) || !shown.includes(b)) return null;
            const used = (view.edges[key] ?? 0) + (view.edges[`${b}>${a}`] ?? 0);
            const now = routeKeys.has(key) || routeKeys.has(`${b}>${a}`);
            const cls = now ? styles.edgeNow : used ? styles.edgeUsed : styles.edge;
            return (
              <g key={key}>
                <path d={d(pts)} className={cls}>
                  <title>{`${NODES[a].title} ↔ ${NODES[b].title}: ${EDGE_LABEL[key] ?? ""}${used ? ` · ${used}×` : ""}`}</title>
                </path>
              </g>
            );
          })}

          {shown.map((id) => {
            const n = view.nodes[id];
            const [cx, cy] = POS[id];
            return (
              <g key={id} className={`${styles.node} ${styles[n.state] ?? ""} ${id === "specialist" ? styles.appear : ""}`} transform={`translate(${cx - NW / 2},${cy - NH / 2})`}>
                <title>{`${NODES[id].title} (${NODES[id].sub})${n.last ? `\n${n.last.title}${n.last.detail ? `\n${n.last.detail}` : ""}` : ""}`}</title>
                <rect width={NW} height={NH} rx="3" className={styles.box} />
                <text x="9" y="18" className={styles.title}>{NODES[id].title}</text>
                <text x="9" y="31" className={styles.sub}>{NODES[id].sub}</text>
                <text x="9" y="48" className={styles.last}>{n.last ? cut(n.last.title, 19) : "idle"}</text>
                {n.count > 0 && (
                  <g transform={`translate(${NW - 7},12)`}>
                    <rect x="-20" y="-8" width="20" height="14" rx="2" className={styles.countBox} />
                    <text x="-10" y="2.5" textAnchor="middle" className={styles.count}>{n.count}</text>
                  </g>
                )}
              </g>
            );
          })}

          {/* only a new live event gets the pulse; a row picked from the timeline jumps */}
          {hop.length > 1 && upto == null && <Pulse key={view.focus?.seq} pts={hop} />}
        </svg>
      </div>

      <p className={styles.caption} aria-live="polite">
        {view.focus && incident && focusLine ? (
          <>
            <span className={styles.capTime}>{since(view.focus.ts, incident.openedAt)}</span>
            <b className={styles[focusLine.tone] ?? ""}>{focusLine.title}</b>
            {caption && <span className={styles.capRoute}>{caption}</span>}
          </>
        ) : (
          <span className="muted">
            Waiting for an incident. Break something from a terminal:{" "}
            <code className="mono">uv run python -m chaos.cli inject bad-deploy</code>
          </span>
        )}
      </p>
    </article>
  );
}
