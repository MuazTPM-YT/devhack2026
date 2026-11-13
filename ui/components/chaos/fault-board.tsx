"use client";

import { useState } from "react";

import { inject, type TruthEntry } from "@/lib/chaos-api";
import { clock } from "@/lib/format";

import styles from "./fault-board.module.css";

// §7 scenarios the panel can cause; path matches chaos/main.py FAULTS
const FAULTS = [
  { path: "bad-deploy", scenario: 1, name: "Bad deploy", target: "payment", what: "Ships payment:v2-bad, ~40% of charges fail." },
  { path: "broken-config", scenario: 2, name: "Broken config", target: "checkout", what: "Points checkout at payment:9999, every order fails." },
  { path: "flag-flip", scenario: 3, name: "Flag flip", target: "payment", what: "Sets paymentFailure to 50%." },
  { path: "memory-leak", scenario: 4, name: "Memory leak", target: "recommendation", what: "Cache leak flag on, OOMKilled in about 2 min." },
  { path: "datastore-down", scenario: 5, name: "Datastore down", target: "valkey-cart", what: "Scales the cart store to 0, cart stops." },
  { path: "shared-outage", scenario: 10, name: "Shared outage", target: "kafka", what: "Scales kafka to 0; checkout errors within 90 s." },
];

export function FaultBoard({ onChange }: { onChange: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [last, setLast] = useState<{ path: string; entry?: TruthEntry; error?: string } | null>(null);

  async function fire(path: string) {
    setBusy(path);
    try {
      setLast({ path, entry: await inject(path) });
    } catch (e) {
      setLast({ path, error: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
      onChange();
    }
  }

  return (
    <section className={styles.board} aria-label="Faults">
      {FAULTS.map((f) => (
        <button key={f.path} type="button" className={`card ${styles.fault}`} disabled={busy !== null}
          onClick={() => fire(f.path)} aria-busy={busy === f.path}>
          <span className="label">Scenario {f.scenario} · {f.target}</span>
          <span className={styles.name}>{f.name}</span>
          <span className={styles.what}>{f.what}</span>
          <span className={styles.go}>{busy === f.path ? "injecting…" : "Inject"}</span>
        </button>
      ))}

      <div className={`card ${styles.resetCard}`}>
        <span className="label">Every fault stays until this runs</span>
        <span className={styles.name}>Reset</span>
        <span className={styles.what}>Restores deployments and flags from the healthy snapshot.</span>
        <button type="button" className={styles.reset} disabled={busy !== null} onClick={() => fire("reset")}>
          {busy === "reset" ? "resetting…" : "Reset shop"}
        </button>
      </div>

      {last && (
        <p className={`${styles.status} ${last.error ? "bad" : ""}`} role="status">
          {last.error
            ? `${last.path} failed: ${last.error}`
            : `${clock(last.entry!.ts)} · ${last.entry!.type}${last.entry!.target ? ` → ${last.entry!.target}` : ""}`}
        </p>
      )}
    </section>
  );
}
