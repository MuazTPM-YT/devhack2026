import page from "@/components/page.module.css";
import { Tag } from "@/components/ui/tag";
import type { HealthNow } from "@/lib/chaos-api";
import { clock } from "@/lib/format";
import { serviceStatus } from "@/lib/overview";

const RANK = { unhealthy: 0, breaching: 1, ok: 2, nodata: 3 } as const;
const TAG = {
  unhealthy: <Tag tone="bad">Unhealthy</Tag>, breaching: <Tag tone="warn">Breaching</Tag>,
  ok: <Tag tone="ok">OK</Tag>, nodata: <Tag tone="idle">No data</Tag>,
};

// observer /health/now as a table, worst first
export function Health({ health, error }: { health: HealthNow | null; error: string | null }) {
  const rows = health ? Object.entries(health.services)
    .sort(([an, a], [bn, b]) => RANK[serviceStatus(a)] - RANK[serviceStatus(b)] || an.localeCompare(bn)) : [];
  return (
    <article className="card">
      <div className="card-head">
        <h2 className="card-title">Health now</h2>
        <span className="label">{error ? "observer offline" : health ? `read ${clock(health.ts)}` : "waiting"}</span>
      </div>
      {error && !health ? (
        <p className="empty bad">No reading from the observer ({error}). Start it on :7001.</p>
      ) : (
        <div className={page.scroll}>
          <table className={page.table}>
            <thead><tr><th>Status</th><th>Service</th><th>Errors</th><th>p95</th></tr></thead>
            <tbody>
              {rows.map(([name, s]) => (
                <tr key={name}>
                  <td>{TAG[serviceStatus(s)]}</td>
                  <td>{name}</td>
                  <td className={page.num}>{s.err_ratio == null ? "–" : `${(s.err_ratio * 100).toFixed(1)}%`}</td>
                  <td className={page.num}>{s.p95_ms == null ? "–" : `${Math.round(s.p95_ms)} ms`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}
