import assert from "node:assert/strict";
import { test } from "node:test";

import type { HealthNow, ServiceHealth } from "./chaos-api.ts";
import { type Call, callersOf, carriesFailure, columns, impact, layout, needsOf, parseCalls } from "./service-map.ts";

// the shop's checkout path, as Jaeger reports it
const jaeger = {
  data: [
    { parent: "frontend-proxy", child: "frontend", callCount: 900 },
    { parent: "frontend", child: "checkout", callCount: 40 },
    { parent: "frontend", child: "cart", callCount: 300 },
    { parent: "checkout", child: "payment", callCount: 40 },
    { parent: "checkout", child: "cart", callCount: 40 },
    { parent: "checkout", child: "cart", callCount: 2 },
    { parent: "cart", child: "cart", callCount: 7 },
    { parent: "frontend", child: "ad", callCount: 120 },
  ],
};
const calls = parseCalls(jaeger);

const ok: ServiceHealth = { err_ratio: 0, p95_ms: 10, baseline_p95_ms: 10, breaching: false, bad_pods: 0, unhealthy: false };
const healthWith = (sick: string[]): HealthNow => ({
  ts: 1, severity: sick.length, prometheus_ok: true,
  services: Object.fromEntries(["frontend-proxy", "frontend", "checkout", "cart", "payment", "ad"]
    .map((n) => [n, sick.includes(n) ? { ...ok, err_ratio: 0.4, breaching: true, unhealthy: true } : ok])),
});

test("parseCalls drops self calls and sums repeats", () => {
  assert.equal(calls.length, 6);
  assert.equal(calls.find((c) => c.from === "checkout" && c.to === "cart")?.calls, 42);
  assert.deepEqual(parseCalls(null), []);
  assert.deepEqual(parseCalls({ data: "nope" }), []);
});

test("callersOf walks up: payment failing breaks checkout, frontend, frontend-proxy", () => {
  assert.deepEqual([...callersOf(calls, "payment")].sort(), ["checkout", "frontend", "frontend-proxy"]);
  assert.deepEqual([...needsOf(calls, "checkout")].sort(), ["cart", "payment"]);
  assert.equal(callersOf(calls, "frontend-proxy").size, 0);
});

test("columns use the longest chain, so cart sits after checkout", () => {
  const col = columns(calls);
  assert.equal(col["frontend-proxy"], 0);
  assert.equal(col.frontend, 1);
  assert.equal(col.checkout, 2);
  assert.equal(col.cart, 3);
  assert.equal(col.ad, 2);
});

test("columns survive a cycle", () => {
  const loop: Call[] = [{ from: "a", to: "b", calls: 1 }, { from: "b", to: "c", calls: 1 }, { from: "c", to: "a", calls: 1 }];
  const col = columns(loop);
  assert.deepEqual([col.a, col.b, col.c], [0, 1, 2]);
});

test("layout puts every node inside the box", () => {
  const box = { colW: 100, rowH: 50, nodeW: 80, nodeH: 30, pad: 10 };
  const l = layout(calls, box);
  for (const [x, y] of Object.values(l.pos)) {
    assert.ok(x >= box.pad && x + box.nodeW <= l.width - box.pad + 0.001);
    assert.ok(y >= box.pad && y + box.nodeH <= l.height - box.pad + 0.001);
  }
  assert.equal(new Set(Object.values(l.pos).map((p) => p.join())).size, Object.keys(l.pos).length);
});

test("impact: callers of a failing service are at risk, its siblings are not", () => {
  const m = impact(calls, healthWith(["payment"]), false);
  assert.deepEqual([...m.failing], ["payment"]);
  assert.deepEqual([...m.atRisk].sort(), ["checkout", "frontend", "frontend-proxy"]);
  assert.ok(!m.atRisk.has("cart") && !m.atRisk.has("ad"));
  const hot = calls.filter((c) => carriesFailure(c, m)).map((c) => `${c.from}>${c.to}`).sort();
  assert.deepEqual(hot, ["checkout>payment", "frontend-proxy>frontend", "frontend>checkout"]);
});

test("impact: blind observer marks nothing failing", () => {
  const m = impact(calls, healthWith(["payment"]), true);
  assert.equal(m.failing.size, 0);
  assert.equal(m.status.payment, "unknown");
});
