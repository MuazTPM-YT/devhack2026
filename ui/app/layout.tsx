import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible_Next, Atkinson_Hyperlegible_Mono } from "next/font/google";
import type { ReactNode } from "react";

import { Shell } from "@/components/shell";
import { readPolicy } from "@/lib/config";

import "./globals.css";

// built to be read fast and without mistakes (slashed zero, open shapes): this page is read under stress.
// next/font has no fallback metrics for it, so no size-adjusted fallback
const sans = Atkinson_Hyperlegible_Next({ subsets: ["latin"], variable: "--font-sans", adjustFontFallback: false });
const mono = Atkinson_Hyperlegible_Mono({ subsets: ["latin"], variable: "--font-mono", adjustFontFallback: false });

export const metadata: Metadata = {
  title: { default: "Akira", template: "%s · Akira" },
  description: "Akira, the on-call agent that has to earn its autonomy",
};

export const viewport: Viewport = { themeColor: "#f3f0e9" };

export default async function RootLayout({ children }: { children: ReactNode }) {
  const policy = await readPolicy();
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <Shell policy={policy}>{children}</Shell>
      </body>
    </html>
  );
}
