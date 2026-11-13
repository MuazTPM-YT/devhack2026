"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { type ReactNode, Suspense, useEffect, useState } from "react";

import { clock, words } from "@/lib/format";
import type { Incident } from "@/lib/live";
import { LiveProvider, useLiveContext } from "@/lib/live-context";
import type { Link as LinkState } from "@/lib/use-live";

import { Icon, type IconName } from "./icon";
import styles from "./shell.module.css";

const NAV: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Live incident", icon: "live" },
  { href: "/chaos", label: "Chaos monitor", icon: "chaos" },
  { href: "/trust", label: "Trust", icon: "trust" },
  { href: "/receipts", label: "Receipts", icon: "receipts" },
  { href: "/benchmark", label: "Benchmark", icon: "bench" },
];

const MAX_LISTED = 30;

const LINK_DOT: Record<LinkState, string> = { live: "dot-ok", connecting: "dot-warn", down: "dot-bad", demo: "dot-warn" };
const LINK_TEXT: Record<LinkState, string> = { live: "streaming", connecting: "connecting", down: "unreachable", demo: "demo replay" };

// pulse line in a ring: the agent's mark
function Mark() {
  return (
    <svg width="28" height="28" viewBox="0 0 26 26" aria-hidden="true">
      <circle cx="13" cy="13" r="12" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <path d="M5 13.5h4l2-5 3 9 2-4h5" fill="none" stroke="currentColor" strokeWidth="1.4"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function statusOf(inc: Incident): { text: string; dot: string } {
  if (!inc.outcome) return { text: "open", dot: "dot-warn dot-live" };
  return { text: words(inc.outcome), dot: inc.outcome === "resolved" ? "dot-ok" : "dot-bad" };
}

// past and open incidents from the bus replay; picks one on the live page via ?incident=
function IncidentList({ onPick }: { onPick: () => void }) {
  const { state } = useLiveContext();
  const params = useSearchParams();
  const path = usePathname();
  const picked = path === "/" ? (params.get("incident") ?? state.current) : null;
  const ids = state.order.slice(0, MAX_LISTED);
  if (ids.length === 0) return <p className={styles.none}>No incidents yet.</p>;
  return (
    <ul className={styles.incidents}>
      {ids.map((id) => {
        const inc = state.incidents[id];
        const st = statusOf(inc);
        const who = inc.culprit ?? inc.unhealthy[0] ?? "detecting…";
        return (
          <li key={id}>
            <Link href={`/?incident=${encodeURIComponent(id)}`} onClick={onPick}
              className={id === picked ? `${styles.incident} ${styles.incidentOn}` : styles.incident}
              aria-current={id === picked ? "true" : undefined}>
              <span className={`dot ${st.dot}`} />
              <span className={styles.incMain}>
                <span className={styles.incWho}>{who}</span>
                <span className={styles.incSub}>{clock(inc.openedAt)} · {st.text}</span>
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function Status() {
  const { link, observer } = useLiveContext();
  const sev = observer.health?.severity;
  const obsDot = observer.error ? "dot-bad" : observer.health ? (sev ? "dot-warn" : "dot-ok") : "dot-warn";
  return (
    <dl className={styles.status}>
      <div title={`Gateway event stream: ${LINK_TEXT[link]}`}>
        <dt><span className={`dot ${LINK_DOT[link]}`} /><span className={styles.statusName}>Gateway</span></dt>
        <dd>{LINK_TEXT[link]}</dd>
      </div>
      <div title={observer.error ? `Observer: ${observer.error}` : "Observer severity, 0 is healthy"}>
        <dt><span className={`dot ${obsDot}`} /><span className={styles.statusName}>Observer</span></dt>
        <dd>{observer.error ? "unreachable" : sev == null ? "–" : `severity ${sev}`}</dd>
      </div>
    </dl>
  );
}

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const path = usePathname();
  const { state } = useLiveContext();
  const openCount = state.order.filter((id) => !state.incidents[id].outcome).length;
  return (
    <aside id="sidebar" className={styles.side} data-open={open} aria-label="Main">
      <div className={styles.brandRow}>
        <Link href="/" className={styles.brand} onClick={onClose}>
          <Mark />
          <span className={styles.brandText}>
            <span className={styles.brandName}>Akira</span>
            <span className={styles.brandSub}>on-call agent</span>
          </span>
        </Link>
        <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close menu">
          <Icon name="close" />
        </button>
      </div>

      <nav className={styles.nav} aria-label="Pages">
        {NAV.map((item) => {
          const on = path === item.href;
          return (
            <Link key={item.href} href={item.href} onClick={onClose} title={item.label}
              className={on ? `${styles.link} ${styles.on}` : styles.link} aria-current={on ? "page" : undefined}>
              <Icon name={item.icon} />
              <span className={styles.linkText}>{item.label}</span>
              {item.href === "/" && openCount > 0 && (
                <span className={styles.badge} aria-label={`${openCount} open`}>{openCount}</span>
              )}
            </Link>
          );
        })}
      </nav>

      <section className={styles.section} aria-labelledby="side-incidents">
        <h2 id="side-incidents" className={styles.sectionTitle}>
          Incidents <span className={styles.count}>{state.order.length || ""}</span>
        </h2>
        <Suspense fallback={null}>
          <IncidentList onPick={onClose} />
        </Suspense>
      </section>

      <Status />
    </aside>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const path = usePathname();

  // drawer closes on navigation and on Escape
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <LiveProvider>
      <a href="#main" className={styles.skip}>Skip to content</a>
      <div className={styles.app}>
        <header className={styles.top}>
          <button type="button" className={styles.menuBtn} onClick={() => setOpen(true)}
            aria-expanded={open} aria-controls="sidebar" aria-label="Open menu">
            <Icon name="menu" />
          </button>
          <span className={styles.topBrand}><Mark /> Akira</span>
        </header>
        <Sidebar open={open} onClose={() => setOpen(false)} />
        {open && <div className={styles.scrim} onClick={() => setOpen(false)} aria-hidden="true" />}
        <main id="main" className={styles.main}>{children}</main>
      </div>
    </LiveProvider>
  );
}
