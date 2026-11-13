"use client";

import { useCallback, useEffect, useState } from "react";

import page from "@/components/page.module.css";
import { PageHead } from "@/components/ui/page-head";
import { Tag } from "@/components/ui/tag";
import { experiments, groundTruth, registry as loadRegistry, resetShop, revealExperiment, stopExperiment, type TruthEntry, unlockLab } from "@/lib/chaos-api";
import { clock } from "@/lib/format";
import { type Experiment, OPEN, type Registry, runState, telemetry } from "@/lib/lab";
import { useLiveContext } from "@/lib/live-context";
import { useNow } from "@/lib/use-now";

import { ActiveRun } from "./active-run";
import { CliGuide } from "./cli-guide";
import { Composer } from "./composer";
import { EnvStrip } from "./env-strip";
import { Health } from "./health";
import styles from "./lab.module.css";
import { TruthLog } from "./truth-log";

const RUNS_MS = 3000;
const REGISTRY_MS = 15000;

// the judge's workspace: compose a bounded fault, watch Akira respond, stop it, reveal it
export function ChaosView() {
  const { state, observer, policy } = useLiveContext();
  const now = useNow(true, 2000);
  const [reg, setReg] = useState<Registry | null>(null);
  const [runs, setRuns] = useState<Experiment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [truth, setTruth] = useState<TruthEntry[] | null>(null);
  const [truthError, setTruthError] = useState<string | null>(null);
  const [history, setHistory] = useState(false);
  const [passcode, setPasscode] = useState("");

  const refresh = useCallback(async (what: "runs" | "all") => {
    try {
      const [list, lab] = await Promise.all([experiments(), what === "all" ? loadRegistry() : null]);
      setRuns(list);
      if (lab) setReg(lab);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh("all");
    const a = setInterval(() => refresh("runs"), RUNS_MS);
    const b = setInterval(() => refresh("all"), REGISTRY_MS);
    return () => { clearInterval(a); clearInterval(b); };
  }, [refresh]);

  // the log holds every answer, so it loads only when the judge opens it
  useEffect(() => {
    if (!history) return;
    groundTruth().then((all) => { setTruth(all); setTruthError(null); }).catch((e: Error) => setTruthError(e.message));
  }, [history, runs]);

  async function act(name: string, work: () => Promise<unknown>) {
    setBusy(name);
    try { await work(); setError(null); } catch (e) { setError((e as Error).message); } finally { setBusy(null); refresh("all"); }
  }

  const tele = telemetry(observer.health, observer.error, now);
  const openRun = runs?.find((r) => OPEN.includes(r.status)) ?? null;
  const labRun = runs?.find((r) => OPEN.includes(r.status) && !r.legacy) ?? null;
  const shown = openRun ?? runs?.find((r) => r.status !== "rejected") ?? null;

  return (
    <div className={page.page}>
      <PageHead eyebrow="Chaos Lab · judge controls · Akira has no path here" title="Break it your way, watch Akira respond" />
      {!tele.ok && <p className={styles.banner} role="alert">{tele.text}. An experiment started now cannot be read.</p>}
      <EnvStrip telemetry={tele} registry={reg} run={openRun} error={error} busy={busy === "reset"}
                onReset={() => {
                  if (window.confirm("Restore the whole shop from its healthy snapshot? This ends every experiment and can take a few minutes.")) {
                    act("reset", resetShop);
                  }
                }} />

      <div className={page.grid}>
        <div className={page.span8}>
          {reg ? (
            <Composer registry={reg} locked={labRun ? `Experiment ${labRun.id} is still ${labRun.status.replace("_", " ")}.` : null}
                      onStarted={() => refresh("all")} />
          ) : error?.startsWith("locked") ? (
            <article className="card">
              <div className="card-head"><h2 className="card-title">Lab locked</h2></div>
              <form className={styles.actions} onSubmit={(e) => { e.preventDefault(); act("unlock", () => unlockLab(passcode)).then(() => setPasscode("")); }}>
                <label className="sr-only" htmlFor="lab-passcode">Judge passcode</label>
                <input id="lab-passcode" className={styles.select} type="password" autoComplete="off" placeholder="Judge passcode"
                       value={passcode} onChange={(e) => setPasscode(e.target.value)} />
                <button type="submit" className="btn btn-dark" disabled={!passcode || busy === "unlock"}>Unlock</button>
              </form>
              <p className={styles.hint}>You are not on the machine that runs Akira, so the lab needs the judge passcode once.</p>
            </article>
          ) : (
            <article className="card"><p className={`empty ${error ? "bad" : ""}`}>
              {error ? `Chaos lab unavailable: ${error}` : "Loading what can be broken…"}
            </p></article>
          )}
        </div>
        <div className={`${page.span4} ${page.stack}`}>
          {shown ? (
            <ActiveRun key={shown.id} run={shown} live={state} health={observer.health} policy={policy} busy={busy === shown.id}
                       onStop={() => act(shown.id, () => stopExperiment(shown.id))}
                       onReveal={() => act(shown.id, () => revealExperiment(shown.id))} />
          ) : (
            <article className="card"><p className="empty">
              {runs ? "No experiment yet. Compose one on the left." : "Experiment state unknown, lab not loaded."}
            </p></article>
          )}
        </div>
      </div>

      <details className={styles.more}>
        <summary>Past experiments</summary>
        <div className={`${styles.moreBody} ${page.scroll}`}>
          {!runs?.length ? <p className="empty">None yet.</p> : (
            <table className={page.table}>
              <thead><tr><th>Started</th><th>State</th><th>Target</th><th>Fault</th><th>Ended by</th></tr></thead>
              <tbody>
                {runs.map((r) => {
                  const s = runState(r, null, null);
                  return (
                    <tr key={r.id}>
                      <td className={page.num}>{clock(r.created_at)}</td>
                      <td><Tag tone={s.tone}>{r.status.replace("_", " ")}</Tag></td>
                      <td>{r.hidden ? "hidden" : r.target}</td>
                      <td className={page.num}>{r.hidden ? "hidden" : `${r.spec?.capability} ${r.spec?.choice}`}</td>
                      <td>{r.status === "rejected" ? r.error : (r.ended_by ?? "–").replace("_", " ")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </details>

      <details className={styles.more}>
        <summary>Health now</summary>
        <div className={styles.moreBody}><Health health={observer.health} error={observer.error} /></div>
      </details>

      <details className={styles.more} onToggle={(e) => setHistory(e.currentTarget.open)}>
        <summary>Ground truth log (shows every answer)</summary>
        <div className={styles.moreBody}>{history && <TruthLog entries={truth} error={truthError} />}</div>
      </details>

      <details className={styles.more}>
        <summary>Expert: the same lab from a terminal</summary>
        <div className={styles.moreBody}><CliGuide /></div>
      </details>
    </div>
  );
}
