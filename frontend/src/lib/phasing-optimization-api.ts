/**
 * phasing-optimization-api.ts — Typed API clients for the Phasing
 * Optimization Engine endpoints (PR-V7-03).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/phasing-recommendations
 *   GET /api/v1/portfolio/phasing-insights
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type {
  PortfolioPhasingInsightsResponse,
  ProjectPhasingRecommendationResponse,
} from "./phasing-optimization-types";

/**
 * Fetch deterministic phasing recommendations for a single project.
 *
 * All recommendations are backend-owned — no values are recomputed here.
 * Returns HTTP 404 when the project does not exist.
 */
export async function getProjectPhasingRecommendations(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectPhasingRecommendationResponse> {
  return apiFetch<ProjectPhasingRecommendationResponse>(
    `/projects/${encodeURIComponent(projectId)}/phasing-recommendations`,
    { signal },
  );
}

/**
 * Fetch portfolio-wide phasing intelligence.
 *
 * All values are backend-owned — no values are recomputed here.
 */
export async function getPortfolioPhasingInsights(
  signal?: AbortSignal,
): Promise<PortfolioPhasingInsightsResponse> {
  return apiFetch<PortfolioPhasingInsightsResponse>("/portfolio/phasing-insights", {
    signal,
  });
}
