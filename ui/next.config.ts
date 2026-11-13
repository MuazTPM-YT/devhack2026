import type { NextConfig } from "next";

// same env names as .env.example; defaults are the local ports from the plan.
// chaos is not a rewrite: app/api/chaos adds the API token on the server side
const gateway = process.env.GATEWAY_URL ?? "http://127.0.0.1:7003";
const observer = process.env.OBSERVER_URL ?? "http://127.0.0.1:7001";

const config: NextConfig = {
  // gzip would buffer the proxied SSE stream
  compress: false,
  async rewrites() {
    return [
      { source: "/api/gateway/:path*", destination: `${gateway}/:path*` },
      { source: "/api/observer/:path*", destination: `${observer}/:path*` },
    ];
  },
};

export default config;
