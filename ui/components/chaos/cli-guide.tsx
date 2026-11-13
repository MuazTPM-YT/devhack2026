"use client";

import { useState } from "react";

import { Icon } from "@/components/icon";
import page from "@/components/page.module.css";

import styles from "./cli-guide.module.css";

// --env-file: the chaos panel answers only to CHAOS_JUDGE_TOKEN
const CLI = "uv run --env-file .env python -m chaos.cli";

// §7 scenarios; names match chaos/cli.py FAULTS (and chaos/main.py routes)
const FAULTS = [
  { name: "bad-deploy", scenario: 1, target: "payment", what: "Ships payment:v2-bad, about 40% of charges fail." },
  { name: "broken-config", scenario: 2, target: "checkout", what: "Points checkout at payment:9999, every order fails." },
  { name: "flag-flip", scenario: 3, target: "payment", what: "Sets flag paymentFailure to 50%." },
  { name: "memory-leak", scenario: 4, target: "recommendation", what: "Cache leak flag on, OOMKilled in about 2 min." },
  { name: "datastore-down", scenario: 5, target: "valkey-cart", what: "Scales the cart store to 0, cart stops." },
  { name: "shared-outage", scenario: 10, target: "kafka", what: "Scales kafka to 0, checkout errors within 90 s." },
];

const OTHER = [
  { cmd: `${CLI} status`, what: "Severity and per-service health." },
  { cmd: `${CLI} kubectl -n shop scale deploy/cart --replicas=0`, what: "Scenario 6: break it your own way, as admin. Writes are logged as ground truth." },
  { cmd: `${CLI} truth`, what: "What was really broken and when." },
  { cmd: `${CLI} reset`, what: "Undo every fault, then wait until severity is 0." },
];

function Copy({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "done" | "failed">("idle");
  const copy = () => navigator.clipboard.writeText(text)
    .then(() => setState("done"), () => setState("failed"))
    .finally(() => setTimeout(() => setState("idle"), 1600));
  return (
    <button type="button" className={styles.copy} onClick={copy} aria-label={`Copy: ${text}`}>
      <Icon name={state === "done" ? "check" : "copy"} size={16} />
      <span className={styles.copyText} aria-live="polite">{state === "done" ? "Copied" : state === "failed" ? "Select it" : "Copy"}</span>
    </button>
  );
}

// `short` shows a compact form in tight cells; Copy always copies the full command
function Command({ cmd, short }: { cmd: string; short?: string }) {
  return (
    <div className={styles.cmd}>
      <code className={styles.code} title={cmd}><span className={styles.prompt}>$</span> {short ?? cmd}</code>
      <Copy text={cmd} />
    </div>
  );
}

// faults come from a terminal, not this page: the panel only watches
export function CliGuide() {
  return (
    <article className="card">
      <div className="card-head">
        <h2 className="card-title">Break it from a terminal</h2>
        <span className="label">run from the repo root · each fault stays until reset</span>
      </div>
      <div className={page.scroll}>
        <table className={page.table}>
          <thead><tr><th>Fault</th><th>Target</th><th>What happens</th><th>Command</th></tr></thead>
          <tbody>
            {FAULTS.map((f) => (
              <tr key={f.name}>
                <td><span className={styles.name}>{f.name}</span><span className={styles.scenario}>scenario {f.scenario}</span></td>
                <td className="mono">{f.target}</td>
                <td className={styles.what}>{f.what}</td>
                <td className={styles.cmdCell}><Command cmd={`${CLI} inject ${f.name}`} short={`inject ${f.name}`} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className={styles.sub}>Watch, break your own way, undo</h3>
      <ul className={styles.other}>
        {OTHER.map((o) => (
          <li key={o.cmd}>
            <p className={styles.what}>{o.what}</p>
            <Command cmd={o.cmd} />
          </li>
        ))}
      </ul>
    </article>
  );
}
