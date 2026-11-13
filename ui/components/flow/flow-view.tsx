"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type KeyboardEvent, useEffect, useState } from "react";

import { EDGES, EVENT_NODE, type Edge, type FlowState, GATES, NODES, type NodeId, flowState, liveEdge } from "@/lib/flow";
import { words } from "@/lib/format";
import type { Incident } from "@/lib/live";
import { useLive } from "@/lib/use-live";

import styles from "./flow-view.module.css";

// fixed drawing; the viewBox scales it
const POS: Record<NodeId, [number, number]> = {
  chaos: [110, 520], shop: [110, 310], observer: [330, 310], llm: [540, 160], brain: [540, 310],
  gateway: [820, 310], human: [820, 548], kube: [1050, 310], verifier: [1050, 548],
};
const WALL_X = 672;
const GATE_TOP = 168;
const GATE_STEP = 34;

const PATHS: Record<string, { d: string; at: [number, number] }> = {
  "chaos>shop": { d: "M110,484 L110,346", at: [124, 420] },
  "shop>observer": { d: "M146,310 L294,310", at: [220, 296] },
  "observer>brain": { d: "M366,310 L504,310", at: [435, 296] },
  "brain>llm": { d: "M540,274 L540,196", at: [590, 250] },
  "brain>gateway": { d: "M576,310 L745,310", at: [625, 334] },
  "gateway>human": { d: "M820,462 L820,512", at: [834, 490] },
  "gateway>kube": { d: "M895,310 L1014,310", at: [955, 296] },
  "kube>shop": { d: "M1050,274 C1050,36 110,36 110,274", at: [580, 84] },
  "observer>verifier": { d: "M330,346 L330,650 L1110,650 L1110,548 L1086,548", at: [560, 642] },
  "verifier>human": { d: "M1014,548 L856,548", at: [935, 536] },
};
const key = (e: Edge) => `${e.from}>${e.to}`;

const LINK_COPY = { connecting: "connecting to gateway", live: "live", down: "gateway unreachable", demo: "demo replay" };

function usePrefersStill(): boolean {
  const [still, setStill] = useState(false);
  useEffect(() => {
    const q = window.matchMedia("(prefers-reduced-motion: reduce)");
    setStill(q.matches);
    const on = () => setStill(q.matches);
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, []);
  return still;
}

// what the selected part is doing for this incident, in one or two plain lines
function nowLine(id: NodeId, inc: Incident | null): string {
  if (!inc) return "Waiting. No incident is open.";
  switch (id) {
    case "observer": return `Opened ${inc.id}. Sick: ${inc.unhealthy.join(", ") || "none yet"}.`;
    case "brain": return inc.culprit
      ? `Culprit ${inc.culprit}${inc.victims.length ? `, hurting ${inc.victims.join(", ")}` : ""}. Pattern: ${inc.pattern ? words(inc.pattern) : "deciding"}.`
      : "Reading traces and recent changes.";
    case "llm": return inc.llmCalls ? `Asked ${inc.llmCalls} time${inc.llmCalls > 1 ? "s" : ""} to explain and predict.` : "Not asked yet.";
    case "gateway": {
      const failed = inc.checklist.find((s) => !s.passed);
      if (failed) return `Stopped at ${words(failed.name)}: ${failed.reason ?? "no reason given"}.`;
      return inc.checklist.length ? `${inc.checklist.length} checks passed.` : "No fix proposed yet.";
    }
    case "human": {
      if (inc.outcome === "escalated" || inc.outcome === "handed_off") return inc.briefing || "Woken with the evidence.";
      if (inc.approval) return `Approval ${inc.approval.decision ?? "waiting"} for: ${inc.approval.diff}`;
      return "Not needed so far.";
    }
    case "kube": return inc.blocked ? "Refused a write. The wall held." : inc.action ? `Applied ${words(inc.action.tool)} to ${inc.action.target}.` : "Nothing written.";
    case "verifier": {
      const t = inc.ticks.at(-1);
      if (!t) return "Starts after a fix lands.";
      return `Severity ${t.severity ?? "?"}${t.recovered ? ", recovered" : ""}. Harm check: ${inc.harmClean == null ? "pending" : inc.harmClean ? "clean" : "found harm"}.`;
    }
    case "shop": return inc.outcome === "resolved" ? "Healthy again." : `Severity ${inc.ticks.at(-1)?.severity ?? inc.severityAtOpen ?? "?"}.`;
    case "chaos": return "Outside the agent. Its faults are the only planned breakage.";
  }
}

function Station({ id, flow, selected, onPick }: {
  id: NodeId; flow: FlowState; selected: boolean; onPick: (id: NodeId) => void;
}) {
  const [x, y] = POS[id];
  const state = flow.nodes[id];
  const node = NODES[id];
  const keys = (e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(id); } };
  const cls = `${styles.station} ${styles[state]} ${selected ? styles.picked : ""}`;
  if (id === "gateway") {
    return (
      <g className={cls} role="button" tabIndex={0} aria-label={`${node.name}: ${state}`} onClick={() => onPick(id)} onKeyDown={keys}>
        <rect x={x - 75} y={GATE_TOP - 18} width={150} height={GATE_STEP * 8 + 22} rx={18} className={styles.body} />
        {GATES.map((g, i) => (
          <g key={g} className={styles[`gate_${flow.gates[g]}`]}>
            <circle cx={x - 52} cy={GATE_TOP + i * GATE_STEP} r={5} className={styles.gateDot} />
            <text x={x - 40} y={GATE_TOP + i * GATE_STEP + 4} className={styles.gateText}>{i + 1} {words(g)}</text>
          </g>
        ))}
        <text x={x} y={GATE_TOP + GATE_STEP * 8 + 34} className={styles.name}>{node.name}</text>
      </g>
    );
  }
  return (
    <g className={cls} role="button" tabIndex={0} aria-label={`${node.name}: ${state}`} onClick={() => onPick(id)} onKeyDown={keys}>
      {state === "active" && <circle cx={x} cy={y} r={36} className={styles.ring} />}
      <circle cx={x} cy={y} r={36} className={styles.body} />
      {id === "kube" && <circle cx={x} cy={y} r={27} className={styles.inner} />}
      <text x={x} y={y + 58} className={styles.name}>{node.name}</text>
      <text x={x} y={y + 74} className={styles.where}>{node.where}</text>
    </g>
  );
}

export function FlowView() {
  const demo = useSearchParams().get("demo") === "1";
  const { state, link, replay } = useLive(demo);
  const still = usePrefersStill();
  const incident = state.current ? state.incidents[state.current] : null;
  const last = state.feed.find((f) => f.incidentId === state.current)?.type ?? null;
  const flow = flowState(incident, last);
  const live = liveEdge(flow);
  const [picked, setPicked] = useState<NodeId | null>(null);
  const shown = picked ?? flow.active ?? "gateway";
  const node = NODES[shown];
  const rail = state.feed.filter((f) => !state.current || f.incidentId === state.current).slice().reverse();

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          <p className="label">{incident ? `Following ${incident.id}` : "No incident open; the map shows every part at rest"}</p>
          <h1 className={styles.title}>How a 3 a.m. page travels</h1>
        </div>
        <div className={styles.meta}>
          {incident?.outcome && <span className="pill pill-dark">{words(incident.outcome)}</span>}
          <span className="pill"><span className={`dot ${link === "live" ? "dot-ok" : link === "down" ? "dot-bad" : "dot-warn"}`} />{LINK_COPY[link]}</span>
          {demo
            ? <button type="button" className={`pill ${styles.button}`} onClick={replay}>Replay</button>
            : <Link className={`pill ${styles.button}`} href="/flow?demo=1">Watch a demo incident</Link>}
        </div>
      </div>

      <div className={styles.layout}>
        <section className={`card ${styles.mapCard}`} aria-label="System map">
          <div className={styles.scroll}>
            <svg viewBox="0 0 1200 670" className={styles.map} role="group" aria-label="Parts of the on-call agent and how an incident moves between them">
              <line x1={WALL_X} y1={24} x2={WALL_X} y2={620} className={styles.wall} />
              <text x={WALL_X - 14} y={612} className={`${styles.wallText} ${styles.left}`}>reads the cluster, may ask the LLM</text>
              <text x={WALL_X + 14} y={140} className={styles.wallText}>writes the cluster, never asks an LLM</text>

              {EDGES.map((e) => {
                const p = PATHS[key(e)];
                const lit = flow.nodes[e.from] !== "idle" && flow.nodes[e.to] !== "idle";
                const isLive = live !== null && key(live) === key(e);
                const soft = e.from === "chaos" || e.to === "llm";
                return (
                  <g key={key(e)}>
                    <path id={`edge-${key(e)}`} d={p.d}
                      className={`${styles.edge} ${lit ? styles.lit : ""} ${isLive ? styles.live : ""} ${soft ? styles.soft : ""}`} />
                    <text x={p.at[0]} y={p.at[1]} className={styles.edgeText}>{e.label}</text>
                  </g>
                );
              })}
              {live && !still && (
                <circle r={7} className={styles.token}>
                  <animateMotion dur="1.6s" repeatCount="indefinite"><mpath href={`#edge-${key(live)}`} /></animateMotion>
                </circle>
              )}

              {(Object.keys(POS) as NodeId[]).map((id) => (
                <Station key={id} id={id} flow={flow} selected={id === shown} onPick={setPicked} />
              ))}
            </svg>
          </div>
        </section>

        <aside className={`card ${styles.panel}`} aria-live="polite">
          <p className="label">{node.where}</p>
          <h2 className={styles.panelTitle}>{node.name}</h2>
          <p className={styles.now}>{nowLine(shown, incident)}</p>
          <dl className={styles.facts}>
            <dt>What it does</dt><dd>{node.does}</dd>
            <dt>Allowed</dt><dd>{node.may}</dd>
            <dt>Never</dt><dd>{node.never}</dd>
          </dl>
          {picked && <button type="button" className={`pill ${styles.button}`} onClick={() => setPicked(null)}>Follow the incident again</button>}
        </aside>
      </div>

      <section className={`card ${styles.railCard}`} aria-label="Audit log">
        <div className={styles.railHead}>
          <h2 className={styles.railTitle}>Audit log</h2>
          <p className={styles.railNote}>Every step above is written here first, in a hash chain nobody can quietly edit. <Link href="/receipts">Check the chain</Link></p>
        </div>
        {rail.length === 0 ? <p className="empty">No events yet.</p> : (
          <ol className={styles.rail}>
            {rail.map((f) => {
              const from = EVENT_NODE[f.type] ?? "shop";
              return (
                <li key={f.seq} className={`${styles.tick} ${styles[`from_${from}`]}`}>
                  <button type="button" onClick={() => setPicked(from)} title={`${words(f.type)} (from ${NODES[from].name})`}>
                    <span className={styles.tickDot} />
                    <span className={styles.tickText}>{words(f.type)}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}
