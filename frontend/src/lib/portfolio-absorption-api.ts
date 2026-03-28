/**
 * portfolio-absorption-api.ts — Typed API client for the Portfolio
 * Absorption endpoint (PR-V7-01).
 *
 * Backend endpoint:
 *   GET /api/v1/portfolio/absorption
 */

import { apiFetch } from "./api-client";
import type { PortfolioAbsorptionResponse } from "./portfolio-absorption-types";

/**
 * Fetch the read-only portfolio absorption aggregation from the backend.
 *
 * All values are backend-owned — no values are recomputed or transformed here.
 */
export async function getPortfolioAbsorption(
  signal?: AbortSignal,
): Promise<PortfolioAbsorptionResponse> {
  return apiFetch<PortfolioAbsorptionResponse>("/portfolio/absorption", {
    signal,
  });
}
