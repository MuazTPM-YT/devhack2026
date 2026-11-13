// trust ledger rows for /trust. GET /trust (gateway, requested from M) carries the bound and gate;
// until it exists we fall back to raw GET /ledger counts and leave those two unknown.

export type Pair = [successes: number, failures: number];

export interface TrustRow {
  pattern: string;
  action: string;
  target: string;
  rehearsal: Pair;
  real: Pair;
  lower_bound: number | null;
  bar: number | null;
  open: boolean | null;
}

export interface LedgerRow {
  pattern: string;
  action: string;
  target: string;
  source: "rehearsal" | "real";
  successes: number;
  failures: number;
  last_failure_at: number | null;
}

// one ledger row per source -> one trust row per (pattern, action, target)
export function fromLedger(rows: LedgerRow[]): TrustRow[] {
  const byKey = new Map<string, TrustRow>();
  for (const r of rows) {
    const key = `${r.pattern}\u0000${r.action}\u0000${r.target}`;
    const row = byKey.get(key) ?? {
      pattern: r.pattern, action: r.action, target: r.target,
      rehearsal: [0, 0], real: [0, 0], lower_bound: null, bar: null, open: null,
    };
    row[r.source === "real" ? "real" : "rehearsal"] = [r.successes, r.failures];
    byKey.set(key, row);
  }
  return [...byKey.values()];
}

async function get<T>(url: string): Promise<T | null> {
  const res = await fetch(url);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

// `full` false means the bound and gate came from nowhere yet (fallback)
export async function loadTrust(): Promise<{ rows: TrustRow[]; full: boolean }> {
  const trust = await get<TrustRow[]>("/api/gateway/trust");
  if (trust) return { rows: trust, full: true };
  const ledger = await get<LedgerRow[]>("/api/gateway/ledger");
  return { rows: fromLedger(ledger ?? []), full: false };
}
