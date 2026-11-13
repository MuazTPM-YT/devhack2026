import type { NextRequest } from "next/server";

const CHAOS = process.env.CHAOS_URL ?? "http://127.0.0.1:7004";
const EXP = "experiments/exp-[0-9a-f]{10}";

// the browser reaches only the bounded lab routes; /chaos/kubectl (admin shell) is never proxied
const ALLOWED: Record<string, RegExp> = {
  GET: new RegExp(`^(ground-truth|registry|experiments|${EXP})$`),
  POST: new RegExp(`^(reset|experiments|experiments/preview|experiments/draw|${EXP}/(stop|reveal))$`),
};

// adds the judge token on the server, so it never reaches browser JavaScript
async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const path = (await ctx.params).path.join("/");
  if (!ALLOWED[req.method]?.test(path)) return Response.json({ detail: "not available from the browser" }, { status: 404 });
  // a custom header forces a CORS preflight, so another site's page cannot fire a fault through this proxy
  if (req.method === "POST" && req.headers.get("x-akira-lab") !== "1") {
    return Response.json({ detail: "missing X-Akira-Lab header" }, { status: 403 });
  }
  const token = process.env.CHAOS_JUDGE_TOKEN;
  if (!token) return Response.json({ detail: "CHAOS_JUDGE_TOKEN is not set on the UI server" }, { status: 503 });
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
    return Response.json({ detail: "chaos panel unreachable; start it on :7004" }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
