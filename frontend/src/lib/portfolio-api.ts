/**
 * portfolio-api.ts — Typed API client for the Portfolio Intelligence
 * dashboard endpoint.
 *
 * Responsibility: issue the single GET /portfolio/dashboard request and
 * return a typed response. No business logic, no metric transformation,
 * and no client-side recomputation of portfolio values.
 *
 * Backend endpoint:
 *   GET /api/v1/portfolio/dashboard
 *
 * Error handling:
 *   All ApiError instances from apiFetch propagate to the caller so that
 *   the page component can render a safe error state.
 */

import { apiFetch } from "./api-client";
import type { PortfolioDashboardResponse } from "./portfolio-types";

/**
 * Fetch the read-only portfolio dashboard from the backend.
 *
 * All metrics are backend-owned — no values are recomputed or transformed
 * here.
 */
export async function getPortfolioDashboard(): Promise<PortfolioDashboardResponse> {
  return apiFetch<PortfolioDashboardResponse>("/portfolio/dashboard");
}
