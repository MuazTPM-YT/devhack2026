"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import page from "@/components/page.module.css";
import { Tag, type Tone } from "@/components/ui/tag";
import { dependencies } from "@/lib/chaos-api";
import { plural } from "@/lib/format";
import { telemetry } from "@/lib/lab";
import { useLiveContext } from "@/lib/live-context";
import { incidentStatus, type ServiceInfo, type ServiceStatus } from "@/lib/overview";
import { type Call, callersOf, carriesFailure, impact, layout, needsOf, parseCalls } from "@/lib/service-map";
import { useNow } from "@/lib/use-now";

import styles from "./service-map.module.css";

const POLL_MS = 30_000;

// last graph seen, so switching Cards -> Map shows it at once instead of "Loading" every time
let lastCalls: Call[] | null = null;
const BOX = { colW: 158, rowH: 46, nodeW: 128, nodeH: 30, pad: 18 };

const STATUS: Record<ServiceStatus, { tone: Tone; label: string }> = {
  unhealthy: { tone: "bad", label: "Unhealthy" },
  breaching: { tone: "warn", label: "Breaching" },
  ok: { tone: "ok", label: "OK" },
  nodata: { tone: "idle", label: "No data" },
  unknown: { tone: "idle", label: "Unknown" },
};

const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

// caller's right edge to callee's left edge; a call back to an earlier column bows out below both
function curve([x1, y1]: [number, number], [x2, y2]: [number, number]): string {
  const ax = x1 + BOX.nodeW, ay = y1 + BOX.nodeH / 2, by = y2 + BOX.nodeH / 2;
  if (x2 > x1) {
    const mx = (ax + x2) / 2;
    return `M${ax},${ay} C${mx},${ay} ${mx},${by} ${x2 - 4},${by}`;
  }
  const low = Math.max(ay, by) + BOX.rowH;
  return `M${ax},${ay} C${ax + 60},${low} ${x2 - 60},${low} ${x2 - 4},${by}`;
}

function Names({ names, onPick }: { names: string[]; onPick: (n: string, keyboard: boolean) => void }) {
  if (!names.length) return <p className="muted">None.</p>;
  return (
    <ul className={styles.names}>
      {names.map((n) => <li key={n}><button type="button" className={styles.nameBtn} onClick={(e) => onPick(n, e.detail === 0)}>{n}</button></li>)}
    </ul>
  );
}

// overview's map view: who calls whom, and how a failure climbs to the callers
export function ServiceMap({ services }: { services: Record<string, ServiceInfo> }) {
  const { state, observer, policy } = useLiveContext();
  const now = useNow(true, 5000);
  const [calls, setCalls] = useState<Call[] | null>(lastCalls);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  // set by keyboard picks and Escape, cleared by pointer picks
  const [instant, setInstant] = useState(false);

  useEffect(() => {
    let live = true;
    const tick = () => dependencies()
      .then((j) => { lastCalls = parseCalls(j); if (live) { setCalls(lastCalls); setError(null); } })
      .catch((e: Error) => { if (live) setError(e.message); });
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { live = false; clearInterval(id); };
  }, []);

  useEffect(() => {
    if (!picked) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setInstant(true); setPicked(null); } };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [picked]);

  const list = calls ?? [];
  const box = useMemo(() => layout(calls ?? [], BOX), [calls]);
  const health = observer.health;
  const blind = health != null && !telemetry(health, observer.error, now).ok;
  const m = impact(list, health, blind);
  const names = Object.keys(box.pos);
  const unlinked = Object.keys(services).filter((n) => !box.pos[n]).sort();
  const openId = state.order.find((id) => incidentStatus(state.incidents[id], now, policy.maxAgeS) === "open") ?? null;
  const culprit = openId ? state.incidents[openId].culprit : null;

  const sel = picked && box.pos[picked] ? picked : null;
  const up = sel ? callersOf(list, sel) : new Set<string>();
  const down = sel ? needsOf(list, sel) : new Set<string>();
  const lit = (n: string) => !sel || n === sel || up.has(n) || down.has(n);
  const pick = (n: string, keyboard = false) => { setInstant(keyboard); setPicked((p) => (p === n ? null : n)); };
  const failing = [...m.failing].filter((n) => box.pos[n]);
  const atRisk = [...m.atRisk].sort();

  return (
    <div className={page.stack}>
        <article className="card">
          <div className="card-head">
            <h2 className="card-title">Calls in the last hour</h2>
            <div className={styles.legend} aria-hidden="true">
              <span><i className={styles.kBad} />failing</span>
              <span><i className={styles.kRisk} />at risk</span>
              <span><i className={styles.kHot} />failure path</span>
            </div>
          </div>
          {error && !calls ? (
            <p className="empty bad">Jaeger unreachable ({error}). Check <span className="mono">JAEGER_URL</span>.</p>
          ) : !calls ? (
            <p className="empty">Loading the call graph…</p>
          ) : list.length === 0 ? (
            <p className="empty">Jaeger saw no calls in the last hour. Is the load generator running?</p>
          ) : (
            <div className={styles.scroll}>
              <svg viewBox={`0 0 ${box.width} ${box.height}`} className={styles.map} style={{ minWidth: Math.min(box.width, 720), maxWidth: box.width }}
                data-instant={instant} role="group" aria-label="Service call graph; callers on the left, the services they call on the right">
                <defs>
                  {["", "Hot", "Lit"].map((k) => (
                    <marker key={k} id={`arrow${k}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto">
                      <path d="M0,0 L8,4 L0,8 z" className={styles[`head${k}`]} />
                    </marker>
                  ))}
                </defs>
                {list.map((c) => {
                  const hot = !sel && carriesFailure(c, m);
                  const chain = sel != null && ((c.to === sel || up.has(c.to)) && up.has(c.from)
                    || (c.from === sel || down.has(c.from)) && down.has(c.to));
                  const dim = sel != null && !chain;
                  const cls = hot ? styles.edgeHot : chain ? styles.edgeLit : styles.edge;
                  return (
                    <path key={`${c.from}>${c.to}`} d={curve(box.pos[c.from], box.pos[c.to])} data-dim={dim}
                      className={cls} strokeWidth={1 + Math.log10(c.calls + 1) * 0.45}
                      markerEnd={`url(#arrow${hot ? "Hot" : chain ? "Lit" : ""})`}>
                      <title>{`${c.from} → ${c.to} · ${c.calls} calls`}</title>
                    </path>
                  );
                })}
                {names.map((n) => {
                  const [x, y] = box.pos[n];
                  const st = m.status[n];
                  const role = m.failing.has(n) ? "bad" : m.atRisk.has(n) ? "risk" : st === "breaching" ? "warn" : "ok";
                  const hit = callersOf(list, n).size;
                  return (
                    <g key={n} transform={`translate(${x},${y})`} tabIndex={0} role="button" aria-pressed={sel === n}
                      aria-label={`${n}, ${STATUS[st].label}${m.atRisk.has(n) ? ", at risk" : ""}; ${plural(hit, "service")} break if it fails`}
                      className={`${styles.node} ${styles[role]} ${sel === n ? styles.picked : ""}`} data-dim={!lit(n)}
                      onClick={() => pick(n)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(n, true); } }}>
                      <rect width={BOX.nodeW} height={BOX.nodeH} rx="3" className={styles.box} />
                      <text x="10" y="19" className={styles.name}>{cut(n, 17)}</text>
                      {culprit === n && <text x={BOX.nodeW} y="-4" textAnchor="end" className={styles.culprit}>culprit</text>}
                      <title>{n}</title>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}
          {unlinked.length > 0 && calls && (
            <p className={styles.foot}>No traced calls for {unlinked.join(", ")}: Jaeger links only services that send spans to each other.</p>
          )}
        </article>

        <aside className="card" aria-live="polite">
          {sel ? (
            <>
              <div className="card-head">
                <h2 className="card-title mono">{sel}</h2>
                {m.atRisk.has(sel)
                  ? <Tag tone="warn" title="Healthy now, but calls a failing service">At risk</Tag>
                  : <Tag tone={STATUS[m.status[sel]].tone}>{STATUS[m.status[sel]].label}</Tag>}
              </div>
              <p className={styles.meta}>
                {services[sel] ? `${services[sel].kind}${services[sel].critical ? " · critical" : ""}` : "not in services.yaml"}
                {health?.services[sel]?.err_ratio != null && ` · errors ${(health.services[sel].err_ratio! * 100).toFixed(1)}%`}
                {health?.services[sel]?.p95_ms != null && ` · p95 ${Math.round(health.services[sel].p95_ms!)} ms`}
              </p>
              {culprit === sel && openId && (
                <p><Link href={`/live?incident=${encodeURIComponent(openId)}`}>Culprit of the open incident →</Link></p>
              )}
              <h3 className={styles.sub}>If it fails, these break · {up.size}</h3>
              <Names names={[...up].sort()} onPick={pick} />
              <h3 className={styles.sub}>It needs · {down.size}</h3>
              <Names names={[...down].sort()} onPick={pick} />
              <button type="button" className={`btn ${styles.clear}`} onClick={(e) => { setInstant(e.detail === 0); setPicked(null); }}>Clear</button>
            </>
          ) : (
            <>
              <div className="card-head"><h2 className="card-title">Blast radius</h2></div>
              {failing.length ? (
                <>
                  <h3 className={styles.sub}>Failing · {failing.length}</h3>
                  <Names names={failing} onPick={pick} />
                  <h3 className={styles.sub}>Breaking with it · {atRisk.length}</h3>
                  <Names names={atRisk} onPick={pick} />
                </>
              ) : (
                <p className="muted">Pick a service to see what breaks if it fails and what it needs. Arrows point from caller to callee; thicker means more calls.</p>
              )}
            </>
          )}
        </aside>
    </div>
  );
}
