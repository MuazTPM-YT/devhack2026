import type { DrawOptions, Experiment, Preview, Registry, Spec } from "./lab.ts";

// observer and chaos panel calls. Chaos goes through app/api/chaos, which adds the judge token on the server.
export interface TruthEntry { ts: number; type: string; target?: string; [k: string]: unknown }

export interface ServiceHealth {
  err_ratio: number | null;
  p95_ms: number | null;
  baseline_p95_ms: number | null;
  breaching: boolean;
  first_breach_ts?: number | null;
  bad_pods: number;
  unhealthy: boolean;
}

// ts is when the observer last asked; last_ok_ts is how old the numbers are; prometheus_ok false = stale
export interface HealthNow {
  ts: number;
  severity: number;
  prometheus_ok?: boolean;
  last_ok_ts?: number;
  services: Record<string, ServiceHealth>;
}

// a rejected experiment comes back as 409 with the experiment as body: that is an answer, not a failure
async function call<T>(url: string, init?: RequestInit, accept: number[] = []): Promise<T> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => null);
  if (!res.ok && !accept.includes(res.status)) throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
  return body as T;
}

function post(body?: unknown, extra: Record<string, string> = {}): RequestInit {
  return {
    method: "POST",
    headers: { "X-Akira-Lab": "1", ...(body === undefined ? {} : { "Content-Type": "application/json" }), ...extra },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}

export const groundTruth = () => call<TruthEntry[]>("/api/chaos/ground-truth");

export const healthNow = () => call<HealthNow>("/api/observer/health/now");

export const registry = () => call<Registry>("/api/chaos/registry");

export const experiments = () => call<Experiment[]>("/api/chaos/experiments");

export const previewExperiment = (spec: Spec) => call<Preview>("/api/chaos/experiments/preview", post(spec));

// key: one per press of Start, so a retry after a timeout cannot inject twice
export const startExperiment = (spec: Spec, key: string) =>
  call<Experiment>("/api/chaos/experiments", post(spec, { "Idempotency-Key": key }), [409]);

export const drawExperiment = (options: DrawOptions) => call<Experiment>("/api/chaos/experiments/draw", post(options), [409]);

export const stopExperiment = (id: string) => call<Experiment>(`/api/chaos/experiments/${id}/stop`, post());

export const revealExperiment = (id: string) => call<Experiment>(`/api/chaos/experiments/${id}/reveal`, post());

export const resetShop = () => call<TruthEntry>("/api/chaos/reset", post());

// from a tunnel or the LAN the proxy answers "locked" until the judge passcode was typed once
export const unlockLab = (passcode: string) => call<{ unlocked: boolean }>("/api/chaos/unlock", post({ passcode }));
