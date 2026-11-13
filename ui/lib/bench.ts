// bench/out/summary.json (bench/report.py) in either shape: plain summarize() or compare()

export interface Stat { samples: number; median: number | null; worst: number | null }

export interface ScenarioSummary {
  runs: number;
  failures: number;
  detect_s: Stat;
  diagnose_s: Stat;
  recover_s: Stat;
  failed_customer_requests: Stat;
  diagnosis_accuracy: number | null;
  false_wakes: number | null;
  missed_wakes: number | null;
  blocked: number;
  harm_clean: { samples: number; pass_rate: number | null };
  prediction_held: { samples: number; pass_rate: number | null };
}

export interface BenchRow {
  scenario: string;
  agent: ScenarioSummary;
  manual: ScenarioSummary | null;
  speedup: number | null;
}

type Summary = Record<string, ScenarioSummary>;

function isCompare(raw: unknown): raw is { agent: Summary; manual: Summary; recovery_speedup: Record<string, number | null> } {
  return typeof raw === "object" && raw !== null && "agent" in raw && "manual" in raw && "recovery_speedup" in raw;
}

export function benchRows(raw: unknown): BenchRow[] {
  if (isCompare(raw)) {
    return Object.keys(raw.agent).sort().map((scenario) => ({
      scenario,
      agent: raw.agent[scenario],
      manual: raw.manual[scenario] ?? null,
      speedup: raw.recovery_speedup[scenario] ?? null,
    }));
  }
  const plain = (raw ?? {}) as Summary;
  return Object.keys(plain).sort().map((scenario) => ({ scenario, agent: plain[scenario], manual: null, speedup: null }));
}

// longest worst-case time across all rows: one shared scale for the bars
export function scaleMax(rows: BenchRow[]): number {
  let max = 0;
  for (const r of rows) {
    for (const s of [r.agent, r.manual]) {
      if (!s) continue;
      for (const m of [s.detect_s, s.diagnose_s, s.recover_s]) max = Math.max(max, m.worst ?? 0);
    }
  }
  return max;
}
