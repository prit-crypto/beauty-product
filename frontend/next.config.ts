import type { NextConfig } from "next";

const API_URL = process.env.API_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // a separate build folder lets a second copy run side by side (e.g. tests on other ports)
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // The browser calls /api/*; Next forwards it to the FastAPI backend (no CORS, one origin for basic auth).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  // Concept demo: keep it out of search engines.
  async headers() {
    return [{ source: "/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] }];
  },
};

export default nextConfig;
