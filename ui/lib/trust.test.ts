import assert from "node:assert/strict";
import { test } from "node:test";

import { fromLedger, type LedgerRow } from "./trust.ts";

function ledger(source: "real" | "rehearsal", successes: number, failures: number, target = "payment"): LedgerRow {
  return { pattern: "recent_change", action: "rollback_deploy", target, source, successes, failures, last_failure_at: null };
}

test("fromLedger merges rehearsal and real into one row per key", () => {
  const rows = fromLedger([ledger("rehearsal", 30, 0), ledger("real", 2, 1), ledger("real", 1, 0, "checkout")]);
  assert.equal(rows.length, 2);
  const payment = rows.find((r) => r.target === "payment")!;
  assert.deepEqual(payment.rehearsal, [30, 0]);
  assert.deepEqual(payment.real, [2, 1]);
  assert.equal(payment.lower_bound, null);
  assert.equal(payment.open, null);
  assert.deepEqual(rows.find((r) => r.target === "checkout")!.rehearsal, [0, 0]);
});
