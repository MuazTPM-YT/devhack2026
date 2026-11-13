"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { LiveProvider, useLiveContext } from "@/lib/live-context";
import { incidentStatus, type Policy } from "@/lib/overview";
import { useNow } from "@/lib/use-now";
import type { Link as LinkState } from "@/lib/use-live";

import { Icon, type IconName } from "./icon";
import styles from "./shell.module.css";

const NAV: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Overview", icon: "grid" },
  { href: "/live", label: "Live incident", icon: "live" },
  { href: "/map", label: "Service map", icon: "map" },
  { href: "/chaos", label: "Chaos Lab", icon: "chaos" },
  { href: "/receipts", label: "Receipts", icon: "receipts" },
  { href: "/benchmark", label: "Benchmark", icon: "bench" },
];

const LINK_DOT: Record<LinkState, string> = { live: "dot-ok", connecting: "dot-warn", down: "dot-bad", demo: "dot-warn" };
const LINK_TEXT: Record<LinkState, string> = { live: "streaming", connecting: "connecting", down: "unreachable", demo: "demo replay" };

// pulse line in a ring: the agent's mark
function Mark({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true">
      <circle cx="13" cy="13" r="12" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <path d="M5 13.5h4l2-5 3 9 2-4h5" fill="none" stroke="currentColor" strokeWidth="1.6"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Status() {
  const { link, observer } = useLiveContext();
  const sev = observer.health?.severity;
  // the observer answering is not the observer seeing: prometheus_ok false means its numbers are old
  const blind = observer.health?.prometheus_ok === false;
  const obsDot = observer.error || blind ? "dot-bad" : observer.health ? (sev ? "dot-warn" : "dot-ok") : "dot-warn";
  return (
    <dl className={styles.status}>
      <div title={`Gateway event stream: ${LINK_TEXT[link]}`}>
        <dt><span className={`dot ${LINK_DOT[link]}`} /><span className={styles.statusName}>Gateway</span></dt>
        <dd>{LINK_TEXT[link]}</dd>
      </div>
      <div title={observer.error ? `Observer: ${observer.error}` : blind ? "Observer cannot read Prometheus; health unknown" : "Observer severity, 0 is healthy"}>
        <dt><span className={`dot ${obsDot}`} /><span className={styles.statusName}>Observer</span></dt>
        <dd>{observer.error ? "unreachable" : blind ? "blind" : sev == null ? "–" : `severity ${sev}`}</dd>
      </div>
    </dl>
  );
}

function Sidebar({ open, instant, onClose }: { open: boolean; instant: boolean; onClose: () => void }) {
  const path = usePathname();
  const { state, policy } = useLiveContext();
  const now = useNow(true, 5000);
  const openCount = state.order.filter((id) => incidentStatus(state.incidents[id], now, policy.maxAgeS) === "open").length;
  return (
    <aside id="sidebar" className={styles.side} data-open={open} data-instant={instant} aria-label="Main">
      <div className={styles.brandRow}>
        <Link href="/" className={styles.brand} onClick={onClose}>
          <Mark />
          <span className={styles.brandName}>Akira</span>
        </Link>
        <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close menu">
          <Icon name="close" />
        </button>
      </div>

      <nav className={styles.nav} aria-label="Pages">
        {NAV.map((item) => {
          const on = item.href === "/" ? path === "/" : path.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href} onClick={onClose} title={item.label}
              className={on ? `${styles.link} ${styles.on}` : styles.link} aria-current={on ? "page" : undefined}>
              <Icon name={item.icon} size={18} />
              <span className={styles.linkText}>{item.label}</span>
              {item.href === "/live" && openCount > 0 && (
                <span className={styles.badge} aria-label={`${openCount} open`}>{openCount}</span>
              )}
            </Link>
          );
        })}
      </nav>

      <Status />
    </aside>
  );
}

export function Shell({ children, policy }: { children: ReactNode; policy: Policy }) {
  const [open, setOpen] = useState(false);
  // Escape closes without animation: keyboard actions never animate
  const [instant, setInstant] = useState(false);
  const path = usePathname();

  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setInstant(true);
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const show = () => { setInstant(false); setOpen(true); };

  return (
    <LiveProvider policy={policy}>
      <a href="#main" className={styles.skip}>Skip to content</a>
      <div className={styles.app}>
        <header className={styles.top}>
          <button type="button" className={styles.menuBtn} onClick={show}
            aria-expanded={open} aria-controls="sidebar" aria-label="Open menu">
            <Icon name="menu" />
          </button>
          <span className={styles.topBrand}><Mark size={20} /> Akira</span>
        </header>
        <Sidebar open={open} instant={instant} onClose={() => setOpen(false)} />
        {open && <div className={styles.scrim} onClick={() => setOpen(false)} aria-hidden="true" />}
        <main id="main" className={styles.main}>{children}</main>
      </div>
    </LiveProvider>
  );
}
