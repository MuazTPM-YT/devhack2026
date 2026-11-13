// gateway receipts and audit check for /receipts, through the Next rewrite

export interface Step { name: string; passed: boolean; reason: string | null }

export interface Receipt {
  incident_id: string;
  tool: string;
  target: string;
  diff: Record<string, unknown>;
  inverse: Record<string, unknown>;
  evidence_ids: string[];
  outcome: string;
  prediction_held: boolean | null;
  harm_clean: boolean | null;
  elapsed_s: number | null;
  added_disruption_s: number | null;
  forecast_s: number | null;
  pods_touched: string[];
  blast: { upstream?: string[]; healthy_affected?: string[] };
  trust: { lower_bound?: number; bar?: number; open?: boolean; approved_by?: string };
  checklist: Step[];
  hash_before: string | null;
  hash_after: string | null;
}

export interface ReceiptItem {
  id: number;
  receipt: Receipt;
  card: { status: string; text: string; evidence_ids: string[] };
}

export type AuditResult = { ok: true; records: number } | { ok: false; error: string };

// null = this gateway does not have the route yet
async function get<T>(url: string): Promise<T | null> {
  const res = await fetch(url);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const getReceipt = (id: number) => get<ReceiptItem>(`/api/gateway/receipts/${id}`);

export const verifyAudit = () => get<AuditResult>("/api/gateway/audit/verify");

// GET /receipts (requested from T); without it, walk ids up from 1 until the first gap
// shortcut: probe stops at 40 receipts, fine for a demo; drop it once the list route lands
export async function listReceipts(): Promise<{ items: ReceiptItem[]; listed: boolean }> {
  const listed = await get<ReceiptItem[]>("/api/gateway/receipts?limit=50");
  if (listed) return { items: listed, listed: true };
  const items: ReceiptItem[] = [];
  for (let id = 1; id <= 40; id++) {
    const item = await getReceipt(id);
    if (!item) break;
    items.push(item);
  }
  return { items: items.reverse(), listed: false };
}
