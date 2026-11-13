import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import type { ReactNode } from "react";

import { Shell } from "@/components/shell";
import { readPolicy } from "@/lib/config";

import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-sans" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

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
