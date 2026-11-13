import type { NextConfig } from "next";

// same env names as .env.example; defaults are the local ports from the plan
const gateway = process.env.GATEWAY_URL ?? "http://127.0.0.1:7003";
const observer = process.env.OBSERVER_URL ?? "http://127.0.0.1:7001";
const jaeger = process.env.JAEGER_URL ?? "http://127.0.0.1:8080/jaeger/ui";

const config: NextConfig = {
  // gzip would buffer the proxied SSE stream
  compress: false,
  async rewrites() {
    return [
      { source: "/api/gateway/:path*", destination: `${gateway}/:path*` },
      { source: "/api/observer/:path*", destination: `${observer}/:path*` },
      // service map reads Jaeger's call graph; read-only, same source as brain/graph.py
      { source: "/api/jaeger/:path*", destination: `${jaeger}/:path*` },
      // chaos is not rewritten: app/api/chaos/[...path]/route.ts adds the judge token on the server
    ];
  },
};

export default config;
