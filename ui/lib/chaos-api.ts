// chaos panel (:7004) and observer (:7001) through the Next rewrites

export interface TruthEntry { ts: number; type: string; target?: string; [k: string]: unknown }

export interface ServiceHealth {
  err_ratio: number | null;
  p95_ms: number | null;
  baseline_p95_ms: number | null;
  breaching: boolean;
  bad_pods: number;
  unhealthy: boolean;
}

export interface HealthNow { ts: number; severity: number; services: Record<string, ServiceHealth> }

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
  return body as T;
}

export const inject = (path: string) => call<TruthEntry>(`/api/chaos/${path}`, { method: "POST" });

export const groundTruth = () => call<TruthEntry[]>("/api/chaos/ground-truth");

export const healthNow = () => call<HealthNow>("/api/observer/health/now");

export const runKubectl = (command: string) =>
  call<{ ok: boolean; output: string; recorded: boolean }>("/api/chaos/kubectl", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
