"use client";

import { useEffect, useMemo, useState } from "react";

import { Tag } from "@/components/ui/tag";
import { drawExperiment, previewExperiment, startExperiment } from "@/lib/chaos-api";
import { duration } from "@/lib/format";
import { byFamily, choiceLabel, type Experiment, FAMILY, type Preview, type Registry, runKey, type Spec, STANDING, value } from "@/lib/lab";

import styles from "./lab.module.css";

const STANDING_TONE = { actable: "ok", approval_only: "warn", watch_only: "idle", unwatched: "idle" } as const;

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <fieldset className={styles.step}>
      <legend><span className={styles.stepNo}>{n}</span>{title}</legend>
      {children}
    </fieldset>
  );
}

// what would change, before anything changes. An impact estimate, never Akira's answer
function PreviewPane({ pre }: { pre: Preview }) {
  return (
    <>
      {pre.problems.length > 0 && (
        <ul className={styles.problems} role="alert">{pre.problems.map((p) => <li key={p}>{p}</li>)}</ul>
      )}
      {pre.changes.length > 0 && (
        <dl className={styles.facts}>
          {pre.changes.map((c) => (
            <div key={c.place} style={{ display: "contents" }}>
              <dt>{c.role === "decoy" ? `Decoy, ${c.after_s} s later` : "Changes"}</dt>
              <dd className={styles.change}>{c.place}<br />{value(c.before)} <span className={styles.arrow}>-&gt;</span> {value(c.after)}</dd>
            </div>
          ))}
          <dt>Journeys touched</dt>
          <dd>{pre.journeys.length ? pre.journeys.join(", ") : "none mapped"} (estimate)</dd>
          <dt>Ends</dt>
          <dd>when the cause is reversed, when you stop it, or after {duration(pre.ends_after_s)} at the latest</dd>
          <dt>Stop</dt>
          <dd>restores the old value only if the field still holds the injected one</dd>
          {!pre.tested && <><dt>Symptom</dt><dd>not yet seen on this cluster; it may produce no measurable breach</dd></>}
        </dl>
      )}
    </>
  );
}

export function Composer({ registry, locked, onStarted }: {
  registry: Registry; locked: string | null; onStarted: (exp: Experiment) => void;
}) {
  const [mode, setMode] = useState<"guided" | "blind">("guided");
  const names = useMemo(() => Object.keys(registry.targets).sort((a, b) =>
    Number(registry.targets[b].capabilities.some((c) => c.available)) - Number(registry.targets[a].capabilities.some((c) => c.available))
    || a.localeCompare(b)), [registry]);
  const [target, setTarget] = useState(names[0] ?? "");
  const [capId, setCapId] = useState("");
  const [choice, setChoice] = useState("");
  const [delay, setDelay] = useState(0);
  const [bounded, setBounded] = useState(false);
  const [lasts, setLasts] = useState(registry.limits.min_duration_s * 3);
  const [decoy, setDecoy] = useState(false);
  const [blind, setBlind] = useState(false);
  const [force, setForce] = useState(false);
  const [seed, setSeed] = useState("");
  const [testedOnly, setTestedOnly] = useState(true);
  const [pre, setPre] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const entry = registry.targets[target];
  const cap = entry?.capabilities.find((c) => c.id === capId && c.available) ?? null;
  const spec: Spec | null = cap && cap.choices.includes(choice) ? {
    target, capability: cap.id, choice, delay_s: delay, duration_s: bounded ? lasts : null,
    decoy: decoy && cap.decoy, blind, skip_baseline: force,
  } : null;
  const specKey = JSON.stringify(spec);

  // a preview answers one exact spec; any edit makes it stale
  useEffect(() => { setPre(null); setError(null); }, [specKey]);

  function pickCap(id: string) {
    const next = entry?.capabilities.find((c) => c.id === id);
    setCapId(id);
    setChoice(next?.choices.length === 1 ? next.choices[0] : "");
    if (!next?.decoy) setDecoy(false);
  }

  async function act(work: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try { await work(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const begin = (exp: Experiment) => {
    if (exp.status === "rejected") setError(exp.error ?? "rejected");
    onStarted(exp);
  };
  const onlyBaseline = pre != null && !pre.ok && pre.problems.length === 1 && pre.problems[0] === pre.baseline.reason;

  return (
    <article className="card">
      <div className="card-head">
        <h2 className="card-title">Compose an experiment</h2>
        <div className={styles.tabs}>
          {(["guided", "blind"] as const).map((m) => (
            <button key={m} type="button" className={`btn ${styles.tab}`} aria-pressed={mode === m} onClick={() => setMode(m)}>
              {m === "guided" ? "Guided" : "Blind challenge"}
            </button>
          ))}
        </div>
      </div>
      {locked && <p className={styles.hint} role="status">{locked} Stop it or wait for it to end before the next one.</p>}

      {mode === "blind" ? (
        <div className={styles.form}>
          <p className={styles.hint}>
            The lab draws one valid fault. This screen hides what it was until you reveal it or it ends. Akira gets
            telemetry and the change journal only, never the experiment.
          </p>
          <div className={styles.inline}>
            <label>Seed <input className={styles.number} inputMode="numeric" placeholder="random" value={seed}
                               onChange={(e) => setSeed(e.target.value.replace(/\D/g, "").slice(0, 9))} /></label>
            <label><input type="checkbox" checked={testedOnly} onChange={(e) => setTestedOnly(e.target.checked)} />
              only faults seen to breach here</label>
            <label><input type="checkbox" checked={decoy} onChange={(e) => setDecoy(e.target.checked)} />
              add a harmless decoy change</label>
          </div>
          <div className={styles.actions}>
            <button type="button" className="btn btn-dark" disabled={busy || locked != null}
                    onClick={() => act(async () => begin(await drawExperiment({ seed: seed ? Number(seed) : null, blind: true, decoy, tested_only: testedOnly })))}>
              {busy ? "Starting…" : "Draw and start"}
            </button>
            <span className={styles.hint}>The same seed draws the same fault again.</span>
          </div>
          {error && <p className={styles.error} role="alert">{error}</p>}
        </div>
      ) : (
        <div className={styles.form}>
          <Step n={1} title="Target">
            <select className={styles.select} value={target} aria-label="Target service"
                    onChange={(e) => { setTarget(e.target.value); setCapId(""); setChoice(""); setDecoy(false); }}>
              {names.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            {entry && (
              <p className={styles.hint}>
                <Tag tone={STANDING_TONE[entry.policy]}>{STANDING[entry.policy].label}</Tag>{" "}
                {STANDING[entry.policy].hint}{entry.critical ? " · critical service" : ""}
              </p>
            )}
          </Step>

          <Step n={2} title="What breaks">
            {byFamily(entry).map(({ family, caps }) => (
              <div key={family}>
                <p className={styles.family}>{FAMILY[family] ?? family}</p>
                <div className={styles.options}>
                  {caps.map((c) => (
                    <label key={c.id} className={styles.option} data-off={!c.available} title={c.what ?? undefined}>
                      <input type="radio" name="capability" disabled={!c.available} checked={capId === c.id} onChange={() => pickCap(c.id)} />
                      <span>
                        {c.label}{" "}
                        <span className={styles.optionNote}>
                          {c.available ? `now ${value(c.current)}${c.tested ? "" : " · untested here"}` : `unavailable: ${c.reason}`}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
            {entry && entry.capabilities.length === 0 && <p className="empty">Nothing reviewed for this service.</p>}
          </Step>

          {cap && (
            <Step n={3} title={`How hard${cap.unit ? ` (${cap.unit})` : ""}`}>
              <div className={styles.options}>
                {cap.choices.map((c) => (
                  <label key={c} className={styles.option}>
                    <input type="radio" name="choice" checked={choice === c} onChange={() => setChoice(c)} />
                    <span>{choiceLabel(cap, c)}</span>
                  </label>
                ))}
              </div>
            </Step>
          )}

          {cap && (
            <Step n={4} title="When">
              <div className={styles.inline}>
                <label>Start after <input className={styles.number} type="number" min={0} max={registry.limits.max_delay_s} value={delay}
                                          onChange={(e) => setDelay(Math.max(0, Math.min(registry.limits.max_delay_s, Number(e.target.value) || 0)))} /> s</label>
                <label><input type="checkbox" checked={bounded} onChange={(e) => setBounded(e.target.checked)} /> remove it after</label>
                <label><input className={styles.number} type="number" disabled={!bounded} min={registry.limits.min_duration_s}
                              max={registry.limits.max_duration_s} value={lasts}
                              onChange={(e) => setLasts(Number(e.target.value) || registry.limits.min_duration_s)} /> s</label>
              </div>
              <p className={styles.hint}>
                {bounded ? "A fault removed by its timer is credited to the timer, never to Akira."
                  : `Stays until someone reverses the cause. The lab removes it after ${duration(registry.limits.max_lifetime_s)} at the latest.`}
              </p>
            </Step>
          )}

          {cap && (
            <Step n={5} title="Make it harder">
              <div className={styles.options}>
                <label className={styles.option} data-off={!cap.decoy}>
                  <input type="checkbox" disabled={!cap.decoy} checked={decoy && cap.decoy} onChange={(e) => setDecoy(e.target.checked)} />
                  <span>Add a harmless change {registry.decoy.gap_s} s after the fault{" "}
                    <span className={styles.optionNote}>
                      {cap.decoy ? `sets ${registry.decoy.env} on ${target}; the newest change is then not the cause`
                        : "not offered with this fault"}
                    </span>
                  </span>
                </label>
                <label className={styles.option}>
                  <input type="checkbox" checked={blind} onChange={(e) => setBlind(e.target.checked)} />
                  <span>Hide the answer on this screen until reveal</span>
                </label>
              </div>
            </Step>
          )}

          <div className={styles.preview}>
            <div className={styles.actions}>
              <button type="button" className="btn" disabled={!spec || busy}
                      onClick={() => act(async () => setPre(await previewExperiment(spec!)))}>
                Preview
              </button>
              <button type="button" className="btn btn-dark" disabled={!spec || !pre?.ok || busy || locked != null}
                      onClick={() => act(async () => begin(await startExperiment(spec!, runKey())))}>
                {busy ? "Working…" : "Start experiment"}
              </button>
              {!spec && <span className={styles.hint}>Pick a target, what breaks and how hard.</span>}
              {spec && !pre && <span className={styles.hint}>Preview first: it shows the exact field that will change.</span>}
            </div>
            {(onlyBaseline || force) && (
              <label className={styles.option}>
                <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
                <span>Start anyway on a baseline that is not ready <span className={styles.optionNote}>the result will be harder to read</span></span>
              </label>
            )}
            {pre && <PreviewPane pre={pre} />}
            {error && <p className={styles.error} role="alert">{error}</p>}
          </div>
        </div>
      )}
    </article>
  );
}
