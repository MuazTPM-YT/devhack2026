"use client";

import { useLayoutEffect, useRef } from "react";

import { since } from "@/lib/format";
import { EDGE_LABEL, flowAt, NODES, type NodeId } from "@/lib/flow";
import type { Incident } from "@/lib/live";

import styles from "./flow-map.module.css";

const W = 1000;
const H = 344;
const NW = 150;
const NH = 72;

// component centres; the main row is the incident's path left to right
const POS: Record<NodeId, [number, number]> = {
  shop: [90, 172], observer: [280, 172], brain: [470, 172], gateway: [660, 172], k8s: [900, 172],
  llm: [470, 50], notifier: [660, 50], verifier: [780, 294],
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
  "gateway>notifier": [[X("gateway"), T("gateway")], [X("notifier"), B("notifier")]],
  "shop>brain": [[X("shop"), T("shop")], [X("shop"), 108], [X("brain") - 40, 108], [X("brain") - 40, T("brain")]],
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

// dot walking the focused route; begun before paint, since SMIL begin=0 is already over on a new node
function Pulse({ pts }: { pts: Pt[] }) {
  const ref = useRef<SVGAnimateMotionElement>(null);
  useLayoutEffect(() => { ref.current?.beginElement(); }, []);
  return (
    <circle r="6" cx="0" cy="0" className={styles.pulse}>
      <animateMotion ref={ref} begin="indefinite" dur={`${Math.max(0.6, pts.length * 0.25)}s`} path={d(pts)} fill="freeze" />
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
  const hop = route(view.path);
  const routeKeys = new Set(view.path.slice(1).map((id, i) => `${view.path[i]}>${id}`));
  const caption = view.path.length > 1
    ? view.path.slice(1).map((id, i) => `${NODES[view.path[i]].title} → ${NODES[id].title}: ${EDGE_LABEL[`${view.path[i]}>${id}`] ?? ""}`).join("   ·   ")
    : view.path.length === 1 ? `inside ${NODES[view.path[0]].title}` : "";
  const focusLine = view.focus ? view.nodes[view.path.at(-1) ?? "brain"].last : null;

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

      <div className={styles.scroll}>
        <svg viewBox={`0 0 ${W} ${H}`} className={styles.map} role="img"
          aria-label={view.focus && focusLine ? `${focusLine.title}. ${caption}` : "No incident yet; every service idle"}>
          {Object.entries(EDGES).map(([key, pts]) => {
            const [a, b] = key.split(">");
            const used = (view.edges[key] ?? 0) + (view.edges[`${b}>${a}`] ?? 0);
            const now = routeKeys.has(key) || routeKeys.has(`${b}>${a}`);
            const cls = now ? styles.edgeNow : used ? styles.edgeUsed : styles.edge;
            return (
              <g key={key}>
                <path d={d(pts)} className={cls}>
                  <title>{`${NODES[a as NodeId].title} ↔ ${NODES[b as NodeId].title}: ${EDGE_LABEL[key] ?? ""}${used ? ` · ${used}×` : ""}`}</title>
                </path>
              </g>
            );
          })}

          {(Object.keys(NODES) as NodeId[]).map((id) => {
            const n = view.nodes[id];
            const [cx, cy] = POS[id];
            return (
              <g key={id} className={`${styles.node} ${styles[n.state] ?? ""}`} transform={`translate(${cx - NW / 2},${cy - NH / 2})`}>
                <title>{`${NODES[id].title} (${NODES[id].sub})${n.last ? `\n${n.last.title}${n.last.detail ? `\n${n.last.detail}` : ""}` : ""}`}</title>
                <rect width={NW} height={NH} rx="6" className={styles.box} />
                <text x="10" y="20" className={styles.title}>{NODES[id].title}</text>
                <text x="10" y="35" className={styles.sub}>{NODES[id].sub}</text>
                <text x="10" y="58" className={styles.last}>{n.last ? cut(n.last.title, 22) : "idle"}</text>
                {n.count > 0 && (
                  <g transform={`translate(${NW - 10},14)`}>
                    <rect x="-22" y="-9" width="22" height="16" rx="3" className={styles.countBox} />
                    <text x="-11" y="3" textAnchor="middle" className={styles.count}>{n.count}</text>
                  </g>
                )}
              </g>
            );
          })}

          {hop.length > 1 && <Pulse key={view.focus?.seq} pts={hop} />}
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
