"use client";

import Link from "next/link";

import { Kpis } from "@/components/ui/kpis";
import { PageHead } from "@/components/ui/page-head";
import { Tag, type Tone } from "@/components/ui/tag";
import type { ServiceHealth } from "@/lib/chaos-api";
import { clock, duration, plural } from "@/lib/format";
import { useLiveContext } from "@/lib/live-context";
import {
  incidentStats, incidentStatus, latencyLimit, type Policy, serviceSentence, type ServiceInfo, serviceStatus,
  type ServiceStatus,
} from "@/lib/overview";
import { useNow } from "@/lib/use-now";

import styles from "./overview-view.module.css";

const STATUS: Record<ServiceStatus, { tone: Tone; label: string; rank: number }> = {
  unhealthy: { tone: "bad", label: "Unhealthy", rank: 0 },
  breaching: { tone: "warn", label: "Breaching", rank: 1 },
  ok: { tone: "ok", label: "OK", rank: 2 },
  nodata: { tone: "idle", label: "No data", rank: 3 },
};

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

function ServiceCard({ name, health, info, policy, culprit, incidentId }: {
  name: string; health: ServiceHealth | undefined; info: ServiceInfo | undefined; policy: Policy;
  culprit: boolean; incidentId: string | null;
}) {
  const st = STATUS[serviceStatus(health)];
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
        {info && !info.actable && <Tag tone="idle" title="Akira watches this service but never changes it">Watch only</Tag>}
      </div>
      <Bar label="Errors" value={err} limit={policy.errThreshold} scale={errLine * 3}
        text={err == null ? "–" : `${(err * 100).toFixed(1)}%`} tone={errTone} />
      <Bar label="p95 latency" value={p95} limit={limit} scale={(limit ?? p95 ?? 1) * 1.5}
        text={p95 == null ? "–" : `${Math.round(p95)} ms`} tone={latTone} />
      <p className={styles.sentence}>{serviceSentence(health, policy)}</p>
      <div className={styles.foot}>
        <span>{info ? `${info.kind}${info.critical ? " · critical" : ""}` : "not in services.yaml"}</span>
        {culprit && incidentId
          ? <Link href={`/live?incident=${encodeURIComponent(incidentId)}`} className={styles.open}>Open incident →</Link>
          : <span className="num">{health?.bad_pods ? plural(health.bad_pods, "bad pod") : "pods ready"}</span>}
      </div>
    </article>
  );
}

export function OverviewView({ services }: { services: Record<string, ServiceInfo> }) {
  const { state, observer, policy } = useLiveContext();
  const now = useNow(true, 5000);
  const health = observer.health;
  const names = [...new Set([...Object.keys(services), ...Object.keys(health?.services ?? {})])];
  const rank = (n: string) => STATUS[serviceStatus(health?.services[n])].rank;
  names.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
  const bad = names.filter((n) => serviceStatus(health?.services[n]) === "unhealthy");
  const stats = incidentStats(state, now, policy.maxAgeS);
  const openId = state.order.find((id) => incidentStatus(state.incidents[id], now, policy.maxAgeS) === "open") ?? null;
  const openInc = openId ? state.incidents[openId] : null;

  return (
    <div className={styles.page}>
      <PageHead
        eyebrow={`Overview · namespace shop${health ? ` · as of ${clock(health.ts)}` : ""}`}
        title="Shop at a glance"
        aside={openInc && <Link className="btn btn-dark" href={`/live?incident=${encodeURIComponent(openInc.id)}`}>Open live incident →</Link>}
      />

      <Kpis label="Shop and agent figures" items={[
        { label: "Services", value: names.length || "–" },
        { label: "Unhealthy", value: health ? bad.length : "–", tone: bad.length ? "bad" : undefined },
        { label: "Severity", value: health ? health.severity : "–", sub: "0 is healthy", tone: health?.severity ? "warn" : undefined },
        { label: "Incidents", value: stats.total, sub: `${stats.open} open${stats.lost ? ` · ${stats.lost} lost` : ""}` },
        { label: "Fixed", value: stats.resolved, sub: stats.medianFixS != null ? `median ${duration(stats.medianFixS)}` : "none yet", tone: stats.resolved ? "ok" : undefined },
        { label: "Woke a human", value: stats.escalated + stats.handedOff, sub: `${stats.escalated} escalated · ${stats.handedOff} handed off` },
      ]} />

      <div className={styles.lede}>
        {observer.error && !health ? (
          <p className={styles.alert}>No reading from the observer ({observer.error}). Start it on :7001.</p>
        ) : bad.length ? (
          <p><b>{bad.length} of {names.length} services are unhealthy:</b> {bad.join(", ")}.{" "}
            {openInc ? <>Akira is on it in incident <Link href={`/live?incident=${encodeURIComponent(openInc.id)}`} className="mono">{openInc.id}</Link>.</> : "No incident is open yet."}</p>
        ) : (
          <p>{health ? `All ${names.length} services are inside their baselines.` : "Waiting for the first reading…"}{" "}
            {stats.total > 0 && `Akira has handled ${plural(stats.total, "incident")}: fixed ${stats.resolved}, woke a human for ${stats.escalated + stats.handedOff}.`}</p>
        )}
        <p className={styles.legend}>
          Each card is one service. Top bar: error ratio, the tick is the {((policy.errThreshold ?? 0.05) * 100).toFixed(0)}% line.
          Bottom bar: p95 latency, the tick is its limit ({policy.latencyMultiplier ?? 2}× baseline and at least
          {" "}{policy.latencyFloorMs ?? 100} ms above it). A bar past its tick is a breach; held for 30 s it opens an incident.
        </p>
      </div>

      <div className={styles.grid}>
        {names.map((n) => (
          <ServiceCard key={n} name={n} health={health?.services[n]} info={services[n]} policy={policy}
            culprit={openInc?.culprit === n} incidentId={openInc?.id ?? null} />
        ))}
      </div>
    </div>
  );
}
