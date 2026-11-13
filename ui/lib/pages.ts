// pure helpers for the /trust, /receipts and /benchmark pages (plan §6.8)

export interface TrustRow {
  pattern: string; action: string; target: string;
  rehearsal: [number, number]; real: [number, number];
  successes: number; failures: number; lower_bound: number; bar: number; open: boolean;
}

export interface TrustTable { bar: number; confidence: number; rows: TrustRow[] }

export interface ReceiptItem {
  id: number;
  receipt: { incident_id: string; tool: string; target: string; outcome: string;
             prediction_held: boolean | null; harm_clean: boolean | null; elapsed_s: number | null };
  card: { status: string; text: string };
}

export const pct = (v: number | null | undefined): string =>
  typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(1)}%` : "–";

export const secs = (v: number | null | undefined): string =>
  typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(1)} s` : "–";

type Stat = { samples?: number; median?: number | null; worst?: number | null };
export interface BenchRow {
  group: string; scenario: string; runs: number; failures: number;
  detect: Stat; diagnose: Stat; recover: Stat;
  accuracy: number | null; falseWakes: number | null; missedWakes: number | null;
  blocked: number; harm: number | null; prediction: number | null;
}

function rowsOf(group: string, scenarios: Record<string, Record<string, unknown>>): BenchRow[] {
  return Object.entries(scenarios).map(([scenario, r]) => ({
    group, scenario, runs: Number(r.runs ?? 0), failures: Number(r.failures ?? 0),
    detect: (r.detect_s ?? {}) as Stat, diagnose: (r.diagnose_s ?? {}) as Stat, recover: (r.recover_s ?? {}) as Stat,
    accuracy: (r.diagnosis_accuracy as number | null) ?? null,
    falseWakes: (r.false_wakes as number | null) ?? null, missedWakes: (r.missed_wakes as number | null) ?? null,
    blocked: Number(r.blocked ?? 0),
    harm: ((r.harm_clean as { pass_rate?: number | null }) ?? {}).pass_rate ?? null,
    prediction: ((r.prediction_held as { pass_rate?: number | null }) ?? {}).pass_rate ?? null,
  }));
}

// bench.report summary.json: per-scenario dict, or {agent, manual, recovery_speedup} with --manual
export function benchRows(summary: unknown): { rows: BenchRow[]; speedup: Record<string, number | null> } {
  if (!summary || typeof summary !== "object") return { rows: [], speedup: {} };
  const s = summary as Record<string, unknown>;
  if (s.agent && s.manual) {
    return {
      rows: [...rowsOf("agent", s.agent as Record<string, Record<string, unknown>>),
             ...rowsOf("manual", s.manual as Record<string, Record<string, unknown>>)],
      speedup: (s.recovery_speedup ?? {}) as Record<string, number | null>,
    };
  }
  return { rows: rowsOf("agent", s as Record<string, Record<string, unknown>>), speedup: {} };
}
