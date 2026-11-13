import assert from "node:assert/strict";
import { test } from "node:test";

import { benchRows, pct, secs } from "./pages.ts";

const scenario = {
  runs: 10, failures: 1, detect_s: { samples: 9, median: 42.1, worst: 50 }, diagnose_s: {}, recover_s: {},
  diagnosis_accuracy: 0.9, false_wakes: 0, missed_wakes: 1, blocked: 0,
  harm_clean: { samples: 9, pass_rate: 1 }, prediction_held: { samples: 9, pass_rate: 0.8 },
};

test("plain summary is the agent's rows", () => {
  const { rows, speedup } = benchRows({ "bad-deploy": scenario });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].group, "agent");
  assert.equal(rows[0].detect.median, 42.1);
  assert.equal(rows[0].prediction, 0.8);
  assert.deepEqual(speedup, {});
});

test("comparison summary keeps agent and manual apart", () => {
  const { rows, speedup } = benchRows({ agent: { a: scenario }, manual: { a: scenario }, recovery_speedup: { a: 4 } });
  assert.deepEqual(rows.map((r) => r.group), ["agent", "manual"]);
  assert.equal(speedup.a, 4);
});

test("missing or junk input renders nothing, numbers render a dash", () => {
  assert.deepEqual(benchRows(null).rows, []);
  assert.equal(pct(null), "–");
  assert.equal(pct(0.905), "90.5%");
  assert.equal(secs(undefined), "–");
});
