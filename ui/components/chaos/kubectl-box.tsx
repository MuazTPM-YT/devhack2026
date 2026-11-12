"use client";

import { type FormEvent, useState } from "react";

import { runKubectl } from "@/lib/chaos-api";

import styles from "./kubectl-box.module.css";

interface Run { command: string; ok: boolean; output: string; recorded: boolean }

// scenario 6: judges break the shop their own way; runs as cluster admin on the chaos panel
export function KubectlBox({ onChange, className }: { onChange: () => void; className?: string }) {
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const text = command.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      const res = await runKubectl(text);
      setRuns((r) => [{ command: text, ...res }, ...r].slice(0, 10));
      if (res.recorded) onChange();
    } catch (err) {
      setRuns((r) => [{ command: text, ok: false, output: err instanceof Error ? err.message : String(err), recorded: false }, ...r]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Break it yourself</h2>
        <span className="pill pill-dark">admin · namespace shop</span>
      </div>
      <form className={styles.form} onSubmit={submit}>
        <label className={styles.prompt} htmlFor="kubectl-cmd">kubectl</label>
        <input id="kubectl-cmd" className={styles.input} value={command} spellCheck={false}
          autoComplete="off" placeholder="set env deploy/shipping QUOTE_ADDR=quote:1" onChange={(e) => setCommand(e.target.value)} />
        <button type="submit" className={styles.run} disabled={busy || !command.trim()}>{busy ? "running…" : "Run"}</button>
      </form>
      <p className={styles.note}>No shell: pipes and <code>$()</code> are passed to kubectl as plain words. Changes are logged as ground truth.</p>

      <div className={styles.out} aria-live="polite">
        {runs.length === 0 ? (
          <p className="empty">Output shows here.</p>
        ) : runs.map((run, i) => (
          <div key={i} className={styles.entry}>
            <div className={styles.cmd}>
              <span className={run.ok ? "ok" : "bad"}>{run.ok ? "✓" : "✗"}</span> kubectl {run.command}
              {run.recorded && <span className={styles.tag}>logged</span>}
            </div>
            <pre className={styles.pre}>{run.output || "(no output)"}</pre>
          </div>
        ))}
      </div>
    </article>
  );
}
