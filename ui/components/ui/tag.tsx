import type { ReactNode } from "react";

import styles from "./tag.module.css";

export type Tone = "bad" | "warn" | "ok" | "idle" | "dark" | "accent";

// shape carries the meaning too, so status never relies on colour alone
function Shape({ tone }: { tone: Tone }) {
  const p = { width: 9, height: 9, viewBox: "0 0 10 10", "aria-hidden": true as const };
  if (tone === "bad") return <svg {...p}><path d="M5 0.5 9.5 5 5 9.5 0.5 5z" fill="currentColor" /></svg>;
  if (tone === "warn") return <svg {...p}><path d="M5 0.8 9.6 9.2H0.4z" fill="currentColor" /></svg>;
  if (tone === "ok") return <svg {...p}><circle cx="5" cy="5" r="4.2" fill="currentColor" /></svg>;
  return <svg {...p}><circle cx="5" cy="5" r="3.6" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>;
}

export function Tag({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={`${styles.tag} ${styles[tone]}`} title={title}>
      <Shape tone={tone} />
      {children}
    </span>
  );
}
