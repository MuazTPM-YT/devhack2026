import assert from "node:assert/strict";
import { test } from "node:test";

import { benchRows, scaleMax, type ScenarioSummary } from "./bench.ts";

function summary(recoverWorst: number | null): ScenarioSummary {
  const stat = (worst: number | null) => ({ samples: worst == null ? 0 : 1, median: worst, worst });
  return {
    runs: 1, failures: 0, detect_s: stat(10), diagnose_s: stat(40), recover_s: stat(recoverWorst),
    failed_customer_requests: stat(3), diagnosis_accuracy: 1, false_wakes: 0, missed_wakes: 0, blocked: 0,
    harm_clean: { samples: 1, pass_rate: 1 }, prediction_held: { samples: 1, pass_rate: 1 },
  };
}

test("benchRows reads the plain summarize() shape, sorted", () => {
  const rows = benchRows({ "flag-flip": summary(90), "bad-deploy": summary(80) });
  assert.deepEqual(rows.map((r) => r.scenario), ["bad-deploy", "flag-flip"]);
  assert.equal(rows[0].manual, null);
  assert.equal(scaleMax(rows), 90);
});

test("benchRows reads the compare() shape with manual and speedup", () => {
  const rows = benchRows({
    agent: { "bad-deploy": summary(80) },
    manual: { "bad-deploy": summary(400) },
    recovery_speedup: { "bad-deploy": 5 },
  });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].speedup, 5);
  assert.equal(rows[0].manual?.recover_s.worst, 400);
  assert.equal(scaleMax(rows), 400);
});

test("no summary gives no rows; an unmeasured recover does not break the scale", () => {
  assert.deepEqual(benchRows(null), []);
  assert.equal(scaleMax(benchRows({ x: summary(null) })), 40);
});
