import { readFile } from "node:fs/promises";
import path from "node:path";

import styles from "@/components/pages/pages.module.css";
import { benchRows, pct, secs } from "@/lib/pages";

export const metadata = { title: "Benchmark · On-call" };
export const dynamic = "force-dynamic";

// written by: uv run python -m bench.report bench/results.jsonl --manual ... --output-dir data/report
const REPORT = process.env.BENCH_REPORT ?? path.join(process.cwd(), "..", "data", "report", "summary.json");

async function load(): Promise<unknown> {
  try {
    // the report lives outside ui/ at run time; do not trace it into the build
    return JSON.parse(await readFile(/*turbopackIgnore: true*/ REPORT, "utf8"));
  } catch {
    return null;
  }
}

export default async function BenchmarkPage() {
  const { rows, speedup } = benchRows(await load());
  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          <p className="label">Agent vs a human with kubectl, from injection to recovery</p>
          <h1 className={styles.title}>Benchmark</h1>
        </div>
      </div>
      <section className="card">
        {rows.length === 0 ? (
          <p className="empty">No report yet. Run the bench, then <span className="mono">python -m bench.report bench/results.jsonl --output-dir data/report</span>.</p>
        ) : (
          <div className={styles.wrap}>
            <table className={styles.table}>
              <thead>
                <tr><th>Who</th><th>Scenario</th><th>Runs</th><th>Failed</th><th>Detect (median / worst)</th>
                  <th>Diagnose</th><th>Recover</th><th>Right cause</th><th>False / missed wakes</th>
                  <th>Blocked</th><th>Harm clean</th><th>Prediction held</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.group}/${r.scenario}`}>
                    <td>{r.group}</td><td>{r.scenario}</td><td>{r.runs}</td><td>{r.failures}</td>
                    <td>{secs(r.detect.median)} / {secs(r.detect.worst)}</td>
                    <td>{secs(r.diagnose.median)} / {secs(r.diagnose.worst)}</td>
                    <td>{secs(r.recover.median)} / {secs(r.recover.worst)}</td>
                    <td>{pct(r.accuracy)}</td><td>{r.falseWakes ?? "–"} / {r.missedWakes ?? "–"}</td>
                    <td>{r.blocked}</td><td>{pct(r.harm)}</td><td>{pct(r.prediction)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {Object.keys(speedup).length > 0 && (
          <p className={styles.note}>
            Recovery speed-up vs manual: {Object.entries(speedup)
              .map(([s, v]) => `${s} ${typeof v === "number" ? `${v.toFixed(1)}x` : "–"}`).join(", ")}
          </p>
        )}
      </section>
    </div>
  );
}
