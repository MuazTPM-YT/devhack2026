"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import styles from "./shell.module.css";

const NAV = [
  { href: "/", label: "Live incident" },
  { href: "/chaos", label: "Chaos" },
  { href: "/trust", label: "Trust" },
  { href: "/receipts", label: "Receipts" },
];

// pulse line in a ring: the agent's mark
function Mark() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
      <circle cx="13" cy="13" r="12" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <path d="M5 13.5h4l2-5 3 9 2-4h5" fill="none" stroke="currentColor" strokeWidth="1.4"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  return (
    <div className="frame">
      <header className={styles.bar}>
        <Link href="/" className={styles.brand}>
          <Mark />
          <span>On-call</span>
        </Link>
        <nav className={styles.nav} aria-label="Pages">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href}
              className={path === item.href ? `${styles.link} ${styles.on}` : styles.link}
              aria-current={path === item.href ? "page" : undefined}>
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}
