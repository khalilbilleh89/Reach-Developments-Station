/**
 * pricing-optimization-api.ts — Typed API clients for the Pricing
 * Optimization Engine endpoints (PR-V7-02).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/pricing-recommendations
 *   GET /api/v1/portfolio/pricing-insights
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type {
  PortfolioPricingInsightsResponse,
  ProjectPricingRecommendationsResponse,
} from "./pricing-optimization-types";

/**
 * Fetch demand-responsive pricing recommendations for a single project.
 *
 * All recommendations are backend-owned — no values are recomputed here.
 * Returns HTTP 404 when the project does not exist.
 */
export async function getProjectPricingRecommendations(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectPricingRecommendationsResponse> {
  return apiFetch<ProjectPricingRecommendationsResponse>(
    `/projects/${encodeURIComponent(projectId)}/pricing-recommendations`,
    { signal },
  );
}

/**
 * Fetch portfolio-wide pricing intelligence.
 *
 * All values are backend-owned — no values are recomputed here.
 */
export async function getPortfolioPricingInsights(
  signal?: AbortSignal,
): Promise<PortfolioPricingInsightsResponse> {
  return apiFetch<PortfolioPricingInsightsResponse>("/portfolio/pricing-insights", {
    signal,
  });
}
