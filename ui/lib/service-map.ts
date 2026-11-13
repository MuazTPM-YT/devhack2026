// service map: who calls whom (Jaeger /api/dependencies, last hour) and how a failure climbs to the callers.
// Pure functions; components/map/service-map.tsx draws them.

import type { HealthNow } from "./chaos-api.ts";
import { type ServiceStatus, serviceStatus } from "./overview.ts";

export interface Call { from: string; to: string; calls: number }

// Jaeger links are {parent, child, callCount}; parent is the caller. Self calls dropped, repeats summed.
export function parseCalls(json: unknown): Call[] {
  const data = (json as { data?: unknown } | null)?.data;
  if (!Array.isArray(data)) return [];
  const sum = new Map<string, Call>();
  for (const d of data) {
    const from = d?.parent, to = d?.child;
    if (typeof from !== "string" || typeof to !== "string" || from === to) continue;
    const key = `${from}>${to}`;
    const prev = sum.get(key);
    const n = Number(d.callCount) || 0;
    if (prev) prev.calls += n;
    else sum.set(key, { from, to, calls: n });
  }
  return [...sum.values()];
}

function walk(calls: Call[], start: string, next: (c: Call) => [string, string]): Set<string> {
  const out = new Set<string>();
  const todo = [start];
  while (todo.length) {
    const cur = todo.pop()!;
    for (const c of calls) {
      const [a, b] = next(c);
      if (a === cur && b !== start && !out.has(b)) { out.add(b); todo.push(b); }
    }
  }
  return out;
}

// everything that calls svc, directly or not: what breaks if svc does (same walk as brain/graph.py upstream)
export const callersOf = (calls: Call[], svc: string) => walk(calls, svc, (c) => [c.to, c.from]);

// everything svc calls, directly or not: what it needs to work
export const needsOf = (calls: Call[], svc: string) => walk(calls, svc, (c) => [c.from, c.to]);

export const nodesOf = (calls: Call[]) => [...new Set(calls.flatMap((c) => [c.from, c.to]))].sort();

// column = longest call chain from an entry point; a call back into its own chain (a cycle) is ignored
export function columns(calls: Call[]): Record<string, number> {
  const names = nodesOf(calls);
  const back = new Set<Call>();
  const state: Record<string, 1 | 2> = {};
  const visit = (n: string) => {
    state[n] = 1;
    for (const c of calls) {
      if (c.from !== n) continue;
      if (state[c.to] === 1) back.add(c);
      else if (!state[c.to]) visit(c.to);
    }
    state[n] = 2;
  };
  const roots = names.filter((n) => !calls.some((c) => c.to === n));
  for (const n of [...roots, ...names]) if (!state[n]) visit(n);
  const col: Record<string, number> = Object.fromEntries(names.map((n) => [n, 0]));
  // acyclic now, so names.length rounds settle every chain
  for (let i = 0; i < names.length; i++) {
    for (const c of calls) if (!back.has(c) && col[c.to] < col[c.from] + 1) col[c.to] = col[c.from] + 1;
  }
  return col;
}

export interface Layout { pos: Record<string, [number, number]>; width: number; height: number }

// left to right by column; inside a column, ordered under the callers' average row so lines cross less
export function layout(calls: Call[], box: { colW: number; rowH: number; nodeW: number; nodeH: number; pad: number }): Layout {
  const col = columns(calls);
  const groups: string[][] = [];
  for (const n of nodesOf(calls)) (groups[col[n]] ??= []).push(n);
  const tall = Math.max(1, ...groups.map((g) => g.length));
  const pos: Layout["pos"] = {};
  groups.forEach((g, i) => {
    const at = (n: string) => {
      const ys = calls.filter((c) => c.to === n && pos[c.from]).map((c) => pos[c.from][1]);
      return ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : Infinity;
    };
    g.sort((a, b) => at(a) - at(b) || a.localeCompare(b));
    const shift = ((tall - g.length) * box.rowH) / 2;
    g.forEach((n, j) => { pos[n] = [box.pad + i * box.colW, box.pad + shift + j * box.rowH]; });
  });
  return {
    pos,
    width: box.pad * 2 + Math.max(0, groups.length - 1) * box.colW + box.nodeW,
    height: box.pad * 2 + (tall - 1) * box.rowH + box.nodeH,
  };
}

export interface Impact {
  status: Record<string, ServiceStatus>;
  failing: Set<string>;
  // healthy now, but calls a failing service somewhere down its chain
  atRisk: Set<string>;
}

export function impact(calls: Call[], health: HealthNow | null, blind: boolean, extra: string[] = []): Impact {
  const names = [...new Set([...nodesOf(calls), ...extra])];
  const status = Object.fromEntries(names.map((n) => [n, serviceStatus(health?.services[n], blind)]));
  const failing = new Set(names.filter((n) => status[n] === "unhealthy"));
  const atRisk = new Set<string>();
  for (const f of failing) for (const c of callersOf(calls, f)) if (!failing.has(c)) atRisk.add(c);
  return { status, failing, atRisk };
}

// a call carries the failure when its callee is failing or already hit by it
export const carriesFailure = (c: Call, m: Impact) =>
  (m.failing.has(c.to) || m.atRisk.has(c.to)) && (m.atRisk.has(c.from) || m.failing.has(c.from));
