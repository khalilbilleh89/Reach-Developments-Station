import type { NextConfig } from "next";

/**
 * Reach Developments Station — MVP 1.0 frontend build.
 *
 * The frontend is exported as static HTML/CSS/JS into `out/`, which the FastAPI
 * service mounts at the site root in production. There is no separate frontend
 * host and no Node runtime in production.
 *
 * `trailingSlash` makes the export emit `out/<route>/index.html`, which is what
 * Starlette's `StaticFiles(..., html=True)` resolves directly — no custom SPA
 * fallback router is needed on the backend.
 */
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  reactStrictMode: true,
};

export default nextConfig;
