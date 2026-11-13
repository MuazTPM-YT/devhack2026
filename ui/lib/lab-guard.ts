import { createHmac, timingSafeEqual } from "node:crypto";

// who may use the chaos proxy (app/api/chaos). The server holds the judge token, so the proxy must not
// lend it to whoever can reach the UI: this machine's own browser passes; everyone else unlocks first.

export const COOKIE = "akira_judge";
const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

const hostname = (host: string): string => host.replace(/:\d+$/, "").toLowerCase();

// the session cookie proves the passcode was typed, without holding the passcode itself
export function sessionValue(token: string): string {
  return createHmac("sha256", token).update("akira-lab-session").digest("hex");
}

export function same(a: string, b: string): boolean {
  const x = Buffer.from(a), y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

export interface Caller { host: string | null; origin: string | null; cookie: string | null }

// -> null when allowed, else why not. A page on another site (or a rebinding name) never has a loopback
// Host and never has our cookie.
export function refusal(caller: Caller, token: string): { status: number; detail: string } | null {
  const host = caller.host ?? "";
  if (caller.origin) {
    let from: string;
    try { from = new URL(caller.origin).host; } catch { return { status: 403, detail: "bad Origin" }; }
    if (from.toLowerCase() !== host.toLowerCase()) return { status: 403, detail: "cross-site request refused" };
  }
  if (LOOPBACK.has(hostname(host))) return null;
  if (caller.cookie && same(caller.cookie, sessionValue(token))) return null;
  return { status: 401, detail: "locked: enter the judge passcode to use the lab from this address" };
}
