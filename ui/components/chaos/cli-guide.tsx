"use client";

import { useState } from "react";

import { Icon } from "@/components/icon";

import styles from "./cli-guide.module.css";

const CLI = "uv run python -m chaos.cli";

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

function Command({ cmd }: { cmd: string }) {
  return (
    <div className={styles.cmd}>
      <code className={styles.code}><span className={styles.prompt}>$</span> {cmd}</code>
      <Copy text={cmd} />
    </div>
  );
}

// faults come from a terminal, not this page: the panel only watches
export function CliGuide({ className }: { className?: string }) {
  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Break it from a terminal</h2>
        <span className="pill pill-dark">admin · namespace shop</span>
      </div>
      <p className={styles.intro}>
        Run these from the repo root. Each fault stays until <span className="mono">reset</span>, and the
        live page shows the agent working on it.
      </p>

      <ul className={styles.faults}>
        {FAULTS.map((f) => (
          <li key={f.name}>
            <div className={styles.faultHead}>
              <span className={styles.name}>{f.name}</span>
              <span className="label">scenario {f.scenario} · {f.target}</span>
            </div>
            <p className={styles.what}>{f.what}</p>
            <Command cmd={`${CLI} inject ${f.name}`} />
          </li>
        ))}
      </ul>

      <h3 className={styles.sub}>More</h3>
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
