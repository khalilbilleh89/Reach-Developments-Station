/**
 * portfolio-variance-api.ts — Typed API client for the Portfolio Cost
 * Variance roll-up endpoint (PR-V6-12).
 *
 * Responsibility: issue the GET /portfolio/cost-variance request and return
 * a typed response. No business logic, no metric transformation, and no
 * client-side recomputation of variance values.
 *
 * Backend endpoint:
 *   GET /api/v1/portfolio/cost-variance
 *
 * Error handling:
 *   All ApiError instances from apiFetch propagate to the caller so that
 *   the page component can render a safe error state.
 */

import { apiFetch } from "./api-client";
import type { PortfolioCostVarianceResponse } from "./portfolio-variance-types";

/**
 * Fetch the read-only portfolio cost variance roll-up from the backend.
 *
 * All variance values are backend-owned — no values are recomputed or
 * transformed here.
 */
export async function getPortfolioCostVariance(): Promise<PortfolioCostVarianceResponse> {
  return apiFetch<PortfolioCostVarianceResponse>("/portfolio/cost-variance");
}
