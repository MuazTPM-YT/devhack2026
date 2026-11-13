import type { NextRequest } from "next/server";

import { COOKIE, refusal, same, sessionValue } from "@/lib/lab-guard";

const CHAOS = process.env.CHAOS_URL ?? "http://127.0.0.1:7004";
const EXP = "experiments/exp-[0-9a-f]{10}";

// the browser reaches only the bounded lab routes; /chaos/kubectl (admin shell) is never proxied
const ALLOWED: Record<string, RegExp> = {
  GET: new RegExp(`^(ground-truth|registry|experiments|${EXP})$`),
  POST: new RegExp(`^(reset|experiments|experiments/preview|experiments/draw|${EXP}/(stop|reveal))$`),
};

const deny = (status: number, detail: string) => Response.json({ detail }, { status });

// the passcode is the judge token; a right answer sets an HttpOnly session cookie for this address
async function unlock(req: NextRequest, token: string): Promise<Response> {
  const body = await req.json().catch(() => null);
  if (typeof body?.passcode !== "string" || !same(body.passcode.trim(), token)) return deny(401, "wrong passcode");
  const secure = req.nextUrl.protocol === "https:" || req.headers.get("x-forwarded-proto") === "https";
  return new Response(JSON.stringify({ unlocked: true }), {
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie": `${COOKIE}=${sessionValue(token)}; Path=/api/chaos; HttpOnly; SameSite=Strict; Max-Age=28800${secure ? "; Secure" : ""}`,
    },
  });
}

// adds the judge token on the server, so it never reaches browser JavaScript
async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const path = (await ctx.params).path.join("/");
  const open = req.method === "POST" && path === "unlock";
  if (!open && !ALLOWED[req.method]?.test(path)) return deny(404, "not available from the browser");
  // a custom header forces a CORS preflight, so another site's page cannot fire a fault through this proxy
  if (req.method === "POST" && req.headers.get("x-akira-lab") !== "1") return deny(403, "missing X-Akira-Lab header");
  const token = process.env.CHAOS_JUDGE_TOKEN;
  if (!token) return deny(503, "CHAOS_JUDGE_TOKEN is not set on the UI server");
  const caller = { host: req.headers.get("host"), origin: req.headers.get("origin"), cookie: req.cookies.get(COOKIE)?.value ?? null };
  if (open) {
    const cross = refusal({ ...caller, cookie: sessionValue(token) }, token);  // only the cross-site checks apply
    return cross ? deny(cross.status, cross.detail) : unlock(req, token);
  }
  const no = refusal(caller, token);
  if (no) return deny(no.status, no.detail);
  const headers: Record<string, string> = { "X-Chaos-Token": token };
  const key = req.headers.get("idempotency-key");
  if (key) headers["Idempotency-Key"] = key;
  const body = req.method === "POST" ? await req.text() : "";
  if (body) headers["Content-Type"] = "application/json";
  try {
    const res = await fetch(`${CHAOS}/chaos/${path}`, { method: req.method, headers, body: body || undefined, cache: "no-store" });
    return new Response(await res.text(), {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return deny(502, "chaos panel unreachable; start it on :7004");
  }
}

export const GET = forward;
export const POST = forward;
