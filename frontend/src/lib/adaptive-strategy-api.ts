/**
 * adaptive-strategy-api.ts — Typed API clients for the Adaptive Strategy
 * Influence Layer endpoints (PR-V7-12).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/adaptive-strategy
 *   GET /api/v1/portfolio/adaptive-strategy
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no confidence calculations, no client-side ranking.
 */

import { apiFetch } from "./api-client";
import type {
  AdaptiveStrategyResponse,
  PortfolioAdaptiveStrategySummaryResponse,
} from "./adaptive-strategy-types";

/**
 * Fetch the confidence-adjusted strategy recommendation for a project.
 *
 * Returns both the raw simulation-best strategy and the confidence-adjusted
 * best strategy so leadership can compare both outputs.
 * Returns HTTP 404 when the project does not exist.
 */
export async function getProjectAdaptiveStrategy(
  projectId: string,
  signal?: AbortSignal,
): Promise<AdaptiveStrategyResponse> {
  return apiFetch<AdaptiveStrategyResponse>(
    `/projects/${encodeURIComponent(projectId)}/adaptive-strategy`,
    { signal },
  );
}

/**
 * Fetch the portfolio-level adaptive strategy summary.
 *
 * Provides confidence distribution KPIs, projects whose recommendation was
 * shifted by confidence influence, top confident recommendations, and
 * low-confidence project lists.
 */
export async function getPortfolioAdaptiveStrategy(
  signal?: AbortSignal,
): Promise<PortfolioAdaptiveStrategySummaryResponse> {
  return apiFetch<PortfolioAdaptiveStrategySummaryResponse>(
    "/portfolio/adaptive-strategy",
    { signal },
  );
}
