import { Tag } from "@/components/ui/tag";
import type { TruthEntry } from "@/lib/chaos-api";
import { clock, words } from "@/lib/format";

import styles from "./truth-log.module.css";

const SHOWN = 15;

function detail(e: TruthEntry): string {
  if (e.type === "reset") return Array.isArray(e.restored) && e.restored.length ? `restored ${e.restored.join(", ")}` : "nothing to restore";
  if (e.type === "judge_kubectl") return Array.isArray(e.args) ? `kubectl ${e.args.join(" ")}` : "";
  return [e.target, typeof e.key === "string" ? e.key : null].filter(Boolean).join(" · ");
}

// what was really broken and when; the bench scores against this, the agent never sees it
export function TruthLog({ entries, error }: { entries: TruthEntry[] | null; error: string | null }) {
  const shown = entries ? entries.slice(-SHOWN).reverse() : null;
  return (
    <article className="card">
      <div className="card-head">
        <h2 className="card-title">Ground truth</h2>
        <span className="label">bench only · agent never reads it</span>
      </div>
      {error && !shown ? (
        <p className="empty bad">Chaos panel unreachable: {error}</p>
      ) : !shown?.length ? (
        <p className="empty">Nothing injected yet.</p>
      ) : (
        <ol className={styles.list}>
          {shown.map((e) => (
            <li key={`${e.ts}-${e.type}`}>
              <span className={styles.time}>{clock(e.ts)}</span>
              <span>{e.type === "reset" ? <Tag tone="ok">Reset</Tag> : <Tag tone="bad">{words(e.type)}</Tag>}</span>
              <span className={styles.detail}>{detail(e)}</span>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
