import page from "@/components/page.module.css";
import { Kpis } from "@/components/ui/kpis";
import { PageHead } from "@/components/ui/page-head";
import { type BenchRow, scaleMax, type ScenarioSummary, type Stat } from "@/lib/bench";

import styles from "./bench-view.module.css";

const TIMINGS = [["detect_s", "Detect"], ["diagnose_s", "Diagnose"], ["recover_s", "Recover"]] as const;

const s = (v: number | null) => (v == null ? "–" : `${v < 10 ? v.toFixed(1) : Math.round(v)} s`);
const rate = (v: number | null) => (v == null ? "–" : `${Math.round(v * 100)}%`);
const stat = (x: Stat) => (x.samples ? `${s(x.median)} / ${s(x.worst)}` : "–");

// filled to the median, outlined to the worst, on one shared scale
function Bar({ value, max, manual }: { value: Stat; max: number; manual?: boolean }) {
  if (!value.samples || !max) return <span className={styles.none}>not measured</span>;
  return (
    <span className={styles.track} role="img" aria-label={`median ${s(value.median)}, worst ${s(value.worst)}`}>
      <span className={manual ? styles.worstManual : styles.worst} style={{ width: `${((value.worst ?? 0) / max) * 100}%` }} />
      <span className={manual ? styles.medianManual : styles.median} style={{ width: `${((value.median ?? 0) / max) * 100}%` }} />
    </span>
  );
}

function Timings({ who, data, max, manual }: { who: string; data: ScenarioSummary; max: number; manual?: boolean }) {
  return (
    <div className={styles.who}>
      <span className={styles.whoLabel}>{who}</span>
      {TIMINGS.map(([key, label]) => (
        <div key={key} className={styles.metric}>
          <span className={styles.metricLabel}>{label}</span>
          <Bar value={data[key]} max={max} manual={manual} />
          <span className={page.num}>{stat(data[key])}</span>
        </div>
      ))}
    </div>
  );
}

export function BenchView({ rows, error }: { rows: BenchRow[] | null; error: string | null }) {
  const list = rows ?? [];
  const max = scaleMax(list);
  const compare = list.some((r) => r.manual);
  const runs = list.reduce((n, r) => n + r.agent.runs, 0);

  return (
    <div className={page.page}>
      <PageHead eyebrow="Benchmark · fault, wait, measure" title="Akira against a person with kubectl" />
      <Kpis label="Benchmark figures" items={[
        { label: "Scenarios", value: list.length || "–" },
        { label: "Runs", value: runs || "–" },
        { label: "Compared with manual", value: compare ? "yes" : "no" },
      ]} />

      {error ? (
        <article className="card"><p className="empty bad">{error}</p></article>
      ) : list.length === 0 ? (
        <article className="card">
          <p className="empty">
            No benchmark run yet. After a harness run: <span className="mono">uv run python -m bench.report
            bench/results.jsonl --output-dir bench/out</span> (add <span className="mono">--manual</span> for the
            comparison), then reload.
          </p>
        </article>
      ) : (
        <>
          <article className="card">
            <div className="card-head">
              <h2 className="card-title">Time from fault</h2>
              <span className="label">filled = median · outline = worst · seconds{compare ? " · grey = manual" : ""}</span>
            </div>
            <div className={styles.scenarios}>
              {list.map((r) => (
                <section key={r.scenario} className={styles.scenario}>
                  <h3 className={styles.name}>{r.scenario}</h3>
                  <Timings who="Agent" data={r.agent} max={max} />
                  {r.manual && <Timings who="Manual" data={r.manual} max={max} manual />}
                </section>
              ))}
            </div>
          </article>

          <article className="card">
            <div className="card-head">
              <h2 className="card-title">Results</h2>
              <span className="label">times are median / worst</span>
            </div>
            <div className={page.scroll}>
              <table className={page.table}>
                <thead>
                  <tr>
                    <th>Scenario</th><th>Runs</th><th>Failed</th><th>Detect</th><th>Diagnose</th><th>Recover</th>
                    <th>Diagnosis right</th><th>False / missed wakes</th><th>Blocked</th><th>Harm clean</th>
                    <th>Prediction held</th><th>Failed requests</th>{compare && <th>Faster than manual</th>}
                  </tr>
                </thead>
                <tbody>
                  {list.map(({ scenario, agent: a, speedup }) => (
                    <tr key={scenario}>
                      <td className={page.num}>{scenario}</td>
                      <td className={page.num}>{a.runs}</td>
                      <td className={page.num}>{a.failures}</td>
                      <td className={page.num}>{stat(a.detect_s)}</td>
                      <td className={page.num}>{stat(a.diagnose_s)}</td>
                      <td className={page.num}>{stat(a.recover_s)}</td>
                      <td className={page.num}>{rate(a.diagnosis_accuracy)}</td>
                      <td className={page.num}>{a.false_wakes == null ? "–" : `${a.false_wakes} / ${a.missed_wakes}`}</td>
                      <td className={page.num}>{a.blocked}</td>
                      <td className={page.num}>{rate(a.harm_clean.pass_rate)}</td>
                      <td className={page.num}>{rate(a.prediction_held.pass_rate)}</td>
                      <td className={page.num}>{a.failed_customer_requests.samples ? a.failed_customer_requests.median : "–"}</td>
                      {compare && <td className={page.num}>{speedup == null ? "–" : `${speedup.toFixed(1)}×`}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </>
      )}
    </div>
  );
}
