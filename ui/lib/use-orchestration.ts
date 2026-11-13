"use client";

import { useEffect, useState } from "react";

import type { OrchestrationStatus } from "./orchestration.ts";

const EVERY_MS = 10000;

// null until the gateway answers (or in demo mode, or on an older gateway without the route)
export function useOrchestrationStatus(enabled = true): OrchestrationStatus | null {
  const [status, setStatus] = useState<OrchestrationStatus | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const load = () => fetch("/api/gateway/orchestration/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((body: OrchestrationStatus | null) => { if (alive) setStatus(body); })
      .catch(() => {});
    load();
    const timer = setInterval(load, EVERY_MS);
    return () => { alive = false; clearInterval(timer); };
  }, [enabled]);
  return status;
}
