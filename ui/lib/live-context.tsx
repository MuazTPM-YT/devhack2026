"use client";

import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

import { type HealthNow, healthNow } from "./chaos-api.ts";
import { useLive } from "./use-live.ts";

const HEALTH_POLL_MS = 3000;

export interface HealthState { health: HealthNow | null; error: string | null }

type LiveCtx = ReturnType<typeof useLive> & { observer: HealthState };

const Ctx = createContext<LiveCtx | null>(null);

// observer /health/now, polled once for the sidebar and the chaos monitor
function useObserver(): HealthState {
  const [state, setState] = useState<HealthState>({ health: null, error: null });
  useEffect(() => {
    let live = true;
    const tick = () => healthNow()
      .then((health) => { if (live) setState({ health, error: null }); })
      .catch((e: Error) => { if (live) setState((s) => ({ health: s.health, error: e.message })); });
    tick();
    const id = setInterval(tick, HEALTH_POLL_MS);
    return () => { live = false; clearInterval(id); };
  }, []);
  return state;
}

// one SSE stream for the whole app: lives in the layout, so changing page keeps the incident history
export function LiveProvider({ children }: { children: ReactNode }) {
  // read once on load; ?demo=1 is a dev aid (see lib/demo.ts)
  const [demo, setDemo] = useState<boolean | null>(null);
  useEffect(() => setDemo(new URLSearchParams(window.location.search).get("demo") === "1"), []);
  const live = useLive(demo);
  const observer = useObserver();
  return <Ctx.Provider value={{ ...live, observer }}>{children}</Ctx.Provider>;
}

export function useLiveContext(): LiveCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLiveContext needs <LiveProvider> (components/shell.tsx)");
  return ctx;
}
