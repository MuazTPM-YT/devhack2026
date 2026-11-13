"use client";

import Link from "next/link";
import { useState } from "react";

import { ServiceMap } from "@/components/map/service-map";
import { Kpis } from "@/components/ui/kpis";
import { More } from "@/components/ui/more";
import { PageHead } from "@/components/ui/page-head";
import { Tag, type Tone } from "@/components/ui/tag";
import type { ServiceHealth } from "@/lib/chaos-api";
import { clock, duration, plural } from "@/lib/format";
import { telemetry } from "@/lib/lab";
import { useLiveContext } from "@/lib/live-context";
import { culpritIncident, modeLabel, nowLine, openIncidentIds } from "@/lib/orchestration";
import {
  incidentStats, latencyLimit, type Policy, serviceSentence, type ServiceInfo, serviceStatus,
  type ServiceStatus,
} from "@/lib/overview";
import { useNow } from "@/lib/use-now";
import { useOrchestrationStatus } from "@/lib/use-orchestration";

import styles from "./overview-view.module.css";

const STATUS: Record<ServiceStatus, { tone: Tone; label: string; rank: number }> = {
  unhealthy: { tone: "bad", label: "Unhealthy", rank: 0 },
  breaching: { tone: "warn", label: "Breaching", rank: 1 },
  ok: { tone: "ok", label: "OK", rank: 2 },
  nodata: { tone: "idle", label: "No data", rank: 3 },
  unknown: { tone: "idle", label: "Unknown", rank: 3 },
};

// what Akira may do to a service, from config/services.yaml: act, act only with a human's yes, or only watch
function standing(info: ServiceInfo): { label: string; title: string } | null {
  if (info.actable) return null;
  if (info.protected) return { label: "Approval only", title: "Protected data store: Akira may restore its replica count, and only after a human approves" };
  return { label: "Watch only", title: "Akira diagnoses this service but never changes it" };
}

// value against a limit: fill to the value, black tick at the limit; past the scale the fill is full
function Bar({ label, value, limit, scale, text, tone }: {
  label: string; value: number | null; limit: number | null; scale: number; text: string; tone: Tone;
}) {
  const pct = (v: number) => `${Math.min(100, (v / scale) * 100)}%`;
  return (
    <div className={styles.metric}>
      <div className={styles.metricHead}>
        <span>{label}</span>
        <span className="num">{text}</span>
      </div>
      <div className={styles.track} role="img"
        aria-label={`${label} ${text}${limit != null ? `, limit ${limit}` : ""}`}>
        {value != null && <span className={`${styles.fill} ${styles[`f_${tone}`] ?? ""}`} style={{ width: pct(value) }} />}
        {limit != null && <span className={styles.tick} style={{ left: pct(limit) }} />}
      </div>
    </div>
  );
}

function ServiceCard({ name, health, info, policy, culprit, incidentId, blind }: {
  name: string; health: ServiceHealth | undefined; info: ServiceInfo | undefined; policy: Policy;
  culprit: boolean; incidentId: string | null; blind: boolean;
}) {
  const st = STATUS[serviceStatus(health, blind)];
  const may = info ? standing(info) : null;
  const limit = latencyLimit(health?.baseline_p95_ms ?? null, policy);
  const errLine = policy.errThreshold ?? 0.05;
  const err = health?.err_ratio ?? null;
  const errTone: Tone = err != null && err > errLine ? "bad" : "ok";
  const p95 = health?.p95_ms ?? null;
  const latTone: Tone = p95 != null && limit != null && p95 > limit ? "bad" : "ok";
  return (
    <article className={`${styles.card} ${styles[`c_${st.tone}`] ?? ""}`}>
      <div className={styles.cardHead}>
        <h2 className={styles.name}>{name}</h2>
        {culprit && <Tag tone="dark">Culprit</Tag>}
      </div>
      <div className={styles.tags}>
        <Tag tone={st.tone}>{st.label}</Tag>
        {may && <Tag tone="idle" title={may.title}>{may.label}</Tag>}
      </div>
      <Bar label="Errors" value={err} limit={policy.errThreshold} scale={errLine * 3}
        text={err == null ? "–" : `${(err * 100).toFixed(1)}%`} tone={errTone} />
      <Bar label="p95 latency" value={p95} limit={limit} scale={(limit ?? p95 ?? 1) * 1.5}
        text={p95 == null ? "–" : `${Math.round(p95)} ms`} tone={latTone} />
      {serviceStatus(health, blind) !== "ok" && <p className={styles.sentence}>{serviceSentence(health, policy, blind)}</p>}
      <div className={styles.foot}>
        <span>{info ? `${info.kind}${info.critical ? " · critical" : ""}` : "not in services.yaml"}</span>
        {culprit && incidentId
          ? <Link href={`/live?incident=${encodeURIComponent(incidentId)}`} className={styles.open}>Open incident →</Link>
          : <span className="num">{!health || blind ? "pod state unknown" : health.bad_pods ? plural(health.bad_pods, "bad pod") : "no bad pods"}</span>}
      </div>
    </article>
  );
}

export function OverviewView({ services }: { services: Record<string, ServiceInfo> }) {
  const { state, observer, policy, link } = useLiveContext();
  const mode = modeLabel(useOrchestrationStatus(link !== "demo"));
  const now = useNow(true, 5000);
  const [view, setView] = useState<"cards" | "map">("cards");
  const health = observer.health;
  const tele = telemetry(health, observer.error, now);
  // old numbers behind a fresh response: every card is unknown, none is healthy
  const blind = health != null && !tele.ok;
  const names = [...new Set([...Object.keys(services), ...Object.keys(health?.services ?? {})])];
  const status = (n: string) => serviceStatus(health?.services[n], blind);
  const rank = (n: string) => STATUS[status(n)].rank;
  names.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
  const bad = names.filter((n) => status(n) === "unhealthy");
  const breaching = names.filter((n) => status(n) === "breaching");
  const unmeasured = names.filter((n) => status(n) === "nodata");
  const stats = incidentStats(state, now, policy.maxAgeS);
  // orchestration can hold several open incidents at once; with one, everything below reads as before
  const openIds = openIncidentIds(state, now, policy.maxAgeS);
  const openId = openIds[0] ?? null;
  const openInc = openId ? state.incidents[openId] : null;
  const doing = openInc ? nowLine(openInc)?.text ?? null : null;

  return (
    <div className={styles.page}>
      <PageHead
        title="Overview"
        meta={`Namespace shop${health ? ` · numbers from ${clock(health.last_ok_ts ?? health.ts)}` : ""}`}
        aside={<>
          {mode && <Tag tone={mode.tone} title={mode.title}>{mode.label}</Tag>}
          {openIds.length > 1
            ? <Link className="btn btn-dark" href="/live">{openIds.length} open incidents →</Link>
            : openInc && <Link className="btn btn-dark" href={`/live?incident=${encodeURIComponent(openInc.id)}`}>Open live incident →</Link>}
        </>}
      />

      <Kpis label="Shop and agent figures" items={[
        { label: "Services", value: names.length || "–" },
        { label: "Unhealthy", value: health && !blind ? bad.length : "–", sub: blind ? "unknown" : undefined, tone: bad.length ? "bad" : undefined },
        { label: "Severity", value: health && !blind ? health.severity : "–", sub: blind ? "unknown" : undefined, title: "0 is healthy", tone: !blind && health?.severity ? "warn" : undefined },
        { label: "Incidents", value: stats.total, sub: `${stats.open} open${stats.lost ? ` · ${stats.lost} lost` : ""}` },
        { label: "Fix verified", value: stats.verified, tone: stats.verified ? "ok" : undefined,
          sub: stats.resolved ? `${stats.resolved - stats.verified} recovered unproven${stats.medianFixS != null ? ` · median ${duration(stats.medianFixS)}` : ""}` : "none yet" },
        { label: "Woke a human", value: stats.escalated + stats.handedOff, sub: `${stats.escalated} escalated · ${stats.handedOff} handed off` },
      ]} />

      <div className={styles.lede}>
        {observer.error && !health ? (
          <p className={styles.alert}>No reading from the observer ({observer.error}). Start it on :7001.</p>
        ) : blind ? (
          <p className={styles.alert} role="alert">{tele.text}. The cards below show the last numbers, not the shop now.</p>
        ) : bad.length ? (
          <p><b>{bad.length} of {names.length} services are unhealthy:</b> {bad.join(", ")}.{" "}
            {openIds.length > 1
              ? <>Akira is on {openIds.length} incidents: {openIds.map((id, i) => (
                <span key={id}>{i > 0 && ", "}<Link href={`/live?incident=${encodeURIComponent(id)}`} className="mono">{id}</Link></span>
              ))}.</>
              : openInc ? <>Akira is on it in incident <Link href={`/live?incident=${encodeURIComponent(openInc.id)}`} className="mono">{openInc.id}</Link>{doing ? `: ${doing[0].toLowerCase()}${doing.slice(1)}` : ""}.</> : "No incident is open yet."}</p>
        ) : (
          <p>{!health ? "Waiting for the first reading…"
            : breaching.length ? `${plural(breaching.length, "service")} over a limit, not yet unhealthy: ${breaching.join(", ")}.`
              : unmeasured.length ? `${names.length - unmeasured.length} of ${names.length} services are inside their baselines; ${unmeasured.length} have no measurements (${unmeasured.join(", ")}).`
                : `All ${names.length} services are inside their baselines.`}{" "}
            {stats.total > 0 && `Akira has handled ${plural(stats.total, "incident")}: ${stats.verified} verified fixed, ${stats.resolved - stats.verified} recovered unproven, woke a human for ${stats.escalated + stats.handedOff}.`}</p>
        )}
        {view === "cards" && (
          <More label="How to read a card">
            <p className={styles.legend}>
              Top bar: error ratio, the tick is the {((policy.errThreshold ?? 0.05) * 100).toFixed(0)}% line.
              Bottom bar: p95 latency, the tick is its limit ({policy.latencyMultiplier ?? 2}× baseline and at least
              {" "}{policy.latencyFloorMs ?? 100} ms above it). A bar past its tick is a breach; held for 30 s it opens an incident.
            </p>
          </More>
        )}
      </div>

      <div className={styles.switch} role="group" aria-label="Show services as">
        {(["cards", "map"] as const).map((v) => (
          <button key={v} type="button" aria-pressed={view === v} className={styles.switchBtn} onClick={() => setView(v)}>
            {v === "cards" ? "Cards" : "Map"}
          </button>
        ))}
      </div>

      {view === "map" ? <ServiceMap services={services} /> : (
        <div className={styles.grid}>
          {names.map((n) => (
            <ServiceCard key={n} name={n} health={health?.services[n]} info={services[n]} policy={policy}
              blind={blind} culprit={culpritIncident(state, openIds, n) != null} incidentId={culpritIncident(state, openIds, n)} />
          ))}
        </div>
      )}
    </div>
  );
}
