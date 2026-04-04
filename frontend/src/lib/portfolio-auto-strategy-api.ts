/**
 * portfolio-auto-strategy-api.ts — Typed API client for the Portfolio
 * Auto-Strategy & Intervention Prioritization endpoint (PR-V7-06).
 *
 * Backend endpoint:
 *   GET /api/v1/portfolio/auto-strategy
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type { PortfolioAutoStrategyResponse } from "./portfolio-auto-strategy-types";

/**
 * Fetch portfolio-level intervention priorities and auto-strategy summary.
 *
 * All values are backend-owned — no values are recomputed here.
 * Read-only — no records are mutated.
 */
export async function getPortfolioAutoStrategy(
  signal?: AbortSignal,
): Promise<PortfolioAutoStrategyResponse> {
  return apiFetch<PortfolioAutoStrategyResponse>("/portfolio/auto-strategy", {
    signal,
  });
}
