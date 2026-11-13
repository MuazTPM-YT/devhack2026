// chaos panel writes are admin kubectl: the token is added here on the server, the browser never sees it
const chaos = process.env.CHAOS_URL ?? "http://127.0.0.1:7004";

type Context = { params: Promise<{ path: string[] }> };

async function forward(req: Request, { params }: Context): Promise<Response> {
  const { path } = await params;
  const headers: Record<string, string> = { "X-Oncall-Token": process.env.ONCALL_API_TOKEN ?? "" };
  const type = req.headers.get("content-type");
  if (type) headers["Content-Type"] = type;
  const res = await fetch(`${chaos}/chaos/${path.map(encodeURIComponent).join("/")}`, {
    method: req.method,
    headers,
    body: req.method === "GET" ? undefined : await req.text(),
    cache: "no-store",
  });
  return new Response(res.body, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
  });
}

export const GET = forward;
export const POST = forward;
