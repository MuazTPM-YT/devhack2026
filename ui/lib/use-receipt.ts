"use client";

import { useEffect, useState } from "react";

import { DEMO_RECEIPT } from "./demo.ts";

// the parts of gateway Receipt the live page shows
export interface ReceiptView {
  forecast_s?: number | null;
  elapsed_s?: number | null;
  prediction_held?: boolean | null;
  harm_clean?: boolean | null;
  outcome?: string;
  trust?: Record<string, unknown>;
}

// refetch when the incident closes: the gateway fills elapsed_s and outcome at the end
export function useReceipt(receiptId: number | null, closed: boolean, demo: boolean): ReceiptView | null {
  const [receipt, setReceipt] = useState<ReceiptView | null>(null);
  useEffect(() => {
    if (!receiptId) {
      setReceipt(null);
      return;
    }
    if (demo) {
      setReceipt(closed ? DEMO_RECEIPT : { forecast_s: DEMO_RECEIPT.forecast_s });
      return;
    }
    const ctrl = new AbortController();
    fetch(`/api/gateway/receipts/${receiptId}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      // GET /receipts/{id} answers {id, receipt, card}; the numbers live under receipt
      .then((body: { receipt?: ReceiptView } | null) => setReceipt(body?.receipt ?? null))
      .catch(() => {});
    return () => ctrl.abort();
  }, [receiptId, closed, demo]);
  return receipt;
}
