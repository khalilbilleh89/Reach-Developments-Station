/**
 * strategy-api.ts — Typed API clients for the Automated Strategy Generator
 * endpoints (PR-V7-05).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/recommended-strategy
 *   GET /api/v1/portfolio/strategy-insights
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type {
  PortfolioStrategyInsightsResponse,
  RecommendedStrategyResponse,
} from "./strategy-types";

/**
 * Fetch the recommended strategy for a single project.
 *
 * All strategy values are backend-owned — no values are recomputed here.
 * Returns HTTP 404 when the project does not exist.
 */
export async function getRecommendedStrategy(
  projectId: string,
  signal?: AbortSignal,
): Promise<RecommendedStrategyResponse> {
  return apiFetch<RecommendedStrategyResponse>(
    `/projects/${encodeURIComponent(projectId)}/recommended-strategy`,
    { signal },
  );
}

/**
 * Fetch portfolio-wide strategy intelligence.
 *
 * All values are backend-owned — no values are recomputed here.
 */
export async function getPortfolioStrategyInsights(
  signal?: AbortSignal,
): Promise<PortfolioStrategyInsightsResponse> {
  return apiFetch<PortfolioStrategyInsightsResponse>(
    "/portfolio/strategy-insights",
    { signal },
  );
}
