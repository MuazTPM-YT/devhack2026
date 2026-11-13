"use client";

import { useEffect, useState } from "react";

import page from "@/components/page.module.css";
import { Kpis } from "@/components/ui/kpis";
import { PageHead } from "@/components/ui/page-head";
import { Tag } from "@/components/ui/tag";
import { words } from "@/lib/format";
import { loadTrust, type Pair, type TrustRow } from "@/lib/trust";

import styles from "./trust-view.module.css";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const pair = ([s, f]: Pair) => (s || f ? `${s} / ${f}` : "–");

// bound against the bar: filled to the bound, tick at the bar
function Meter({ bound, bar }: { bound: number; bar: number }) {
  return (
    <span className={styles.meter} role="img" aria-label={`bound ${pct(bound)}, bar ${pct(bar)}`}>
      <span className={bound >= bar ? styles.fillOk : styles.fill} style={{ width: `${bound * 100}%` }} />
      <span className={styles.tick} style={{ left: `${bar * 100}%` }} />
    </span>
  );
}

function Gate({ open }: { open: boolean | null }) {
  if (open == null) return <Tag tone="idle">Unknown</Tag>;
  return open ? <Tag tone="ok">Open · auto</Tag> : <Tag tone="warn">Closed · asks</Tag>;
}

export function TrustView() {
  const [data, setData] = useState<{ rows: TrustRow[]; full: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTrust().then(setData).catch((e: Error) => setError(e.message));
  }, []);

  const rows = data?.rows ?? [];
  const bar = rows.find((r) => r.bar != null)?.bar ?? null;
  const open = rows.filter((r) => r.open).length;

  return (
    <div className={page.page}>
      <PageHead eyebrow="Trust · ledger of verified fixes" title="Earned autonomy" />
      <Kpis label="Trust figures" items={[
        { label: "Fix kinds on record", value: rows.length },
        { label: "Gates open", value: data?.full ? open : "–", sub: "act without asking", tone: open ? "ok" : undefined },
        { label: "Bar to open", value: bar != null ? pct(bar) : "–", sub: "95% lower bound must reach it" },
      ]} />
      <p className={page.lede}>
        Akira acts on its own only for a (pattern, action, target) whose record proves it: the 95% lower bound on its
        success rate must clear the bar, and any failure closes the gate again. Everything else waits for a human.
      </p>

      {data && !data.full && (
        <p className={page.note}>
          Bound and gate need <span className="mono">GET /trust</span> on the gateway (not there yet). Showing raw
          ledger counts.
        </p>
      )}

      <article className="card">
        <div className="card-head">
          <h2 className="card-title">Ledger</h2>
          <span className="label">successes / failures · 95% lower bound · any failure closes the gate</span>
        </div>
        {error ? (
          <p className="empty bad">Gateway unreachable: {error}</p>
        ) : !data ? (
          <p className="empty">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="empty">No fix has been verified yet. Rehearsal and real outcomes land here.</p>
        ) : (
          <div className={page.scroll}>
            <table className={page.table}>
              <thead>
                <tr>
                  <th>Pattern</th><th>Action</th><th>Target</th>
                  <th>Rehearsal</th><th>Real</th><th>Proven bound</th><th>Gate</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.pattern}-${r.action}-${r.target}`}>
                    <td className={styles.cap}>{words(r.pattern)}</td>
                    <td className="mono">{r.action}</td>
                    <td className="mono">{r.target}</td>
                    <td className={page.num}>{pair(r.rehearsal)}</td>
                    <td className={page.num}>{pair(r.real)}</td>
                    <td>
                      {r.lower_bound != null && r.bar != null ? (
                        <span className={styles.bound}><Meter bound={r.lower_bound} bar={r.bar} /><span className={page.num}>{pct(r.lower_bound)}</span></span>
                      ) : <span className="muted">–</span>}
                    </td>
                    <td><Gate open={r.open} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>
    </div>
  );
}
