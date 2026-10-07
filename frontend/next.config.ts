import type { NextConfig } from "next";

const backend = process.env.DEV_BACKEND_URL ?? "http://localhost:8000";
const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  agentRules: false,
  // In production Nginx routes /api, /ws and /media to the backend. In local development
  // (`npm run dev`) the Next dev server proxies the HTTP routes instead.
  async rewrites() {
    if (!isDev) return [];
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/media/:path*", destination: `${backend}/media/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: "/logos/:file*",
        headers: [{ key: "Cache-Control", value: "public, max-age=86400, stale-while-revalidate=604800" }],
      },
    ];
  },
};

export default nextConfig;
