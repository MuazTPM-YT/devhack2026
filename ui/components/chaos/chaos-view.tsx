"use client";

import { useEffect, useState } from "react";

import page from "@/components/page.module.css";
import { Kpis } from "@/components/ui/kpis";
import { PageHead } from "@/components/ui/page-head";
import { groundTruth, type TruthEntry } from "@/lib/chaos-api";
import { clock } from "@/lib/format";
import { useLiveContext } from "@/lib/live-context";

import { CliGuide } from "./cli-guide";
import { Health } from "./health";
import { TruthLog } from "./truth-log";

const POLL_MS = 5000;

// watch-only: faults are injected with chaos/cli.py; faults come from outside the page, so poll
export function ChaosView() {
  const { health, error: obsError } = useLiveContext().observer;
  const [truth, setTruth] = useState<TruthEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const tick = () => groundTruth()
      .then((all) => { if (live) { setTruth(all); setError(null); } })
      .catch((e: Error) => { if (live) setError(e.message); });
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { live = false; clearInterval(id); };
  }, []);

  const lastReset = truth?.findLast((e) => e.type === "reset");
  const faults = truth ? truth.filter((e) => e.type !== "reset" && e.ts > (lastReset?.ts ?? 0)) : [];
  const unhealthy = health ? Object.values(health.services).filter((s) => s.unhealthy).length : null;

  return (
    <div className={page.page}>
      <PageHead eyebrow="Chaos monitor · admin kubeconfig · the agent never calls it" title="Break it, watch Akira fix it" />
      <Kpis label="Chaos figures" items={[
        { label: "Severity", value: health ? health.severity : "–", sub: "0 is healthy", tone: health?.severity ? "warn" : "ok" },
        { label: "Unhealthy services", value: unhealthy ?? "–", tone: unhealthy ? "bad" : undefined },
        { label: "Faults since reset", value: truth ? faults.length : "–", sub: faults.length ? faults.map((f) => f.type).join(", ") : "shop restored", tone: faults.length ? "bad" : undefined },
        { label: "Last reset", value: lastReset ? clock(lastReset.ts) : "–" },
      ]} />
      <div className={page.grid}>
        <div className={page.span8}><CliGuide /></div>
        <div className={`${page.span4} ${page.stack}`}>
          <Health health={health} error={obsError} />
          <TruthLog entries={truth} error={error} />
        </div>
      </div>
    </div>
  );
}
