/**
 * strategy-learning-api.ts — Typed API clients for the Strategy Learning
 * & Confidence Recalibration Engine endpoints (PR-V7-11).
 *
 * Backend endpoints:
 *   POST /api/v1/projects/{id}/strategy-learning/recalibrate
 *   GET  /api/v1/projects/{id}/strategy-learning
 *   GET  /api/v1/portfolio/strategy-learning
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type {
  PortfolioLearningSummaryResponse,
  StrategyLearningResponse,
} from "./strategy-learning-types";

/**
 * Trigger a learning recalibration for a project.
 *
 * Reads all recorded outcomes, recomputes confidence scores and accuracy
 * metrics, upserts the results, and returns the updated panel payload.
 * Returns HTTP 404 when the project does not exist.
 */
export async function recalibrateProjectLearning(
  projectId: string,
  signal?: AbortSignal,
): Promise<StrategyLearningResponse> {
  return apiFetch<StrategyLearningResponse>(
    `/projects/${encodeURIComponent(projectId)}/strategy-learning/recalibrate`,
    { method: "POST", signal },
  );
}

/**
 * Fetch the current stored strategy learning metrics for a project.
 *
 * Returns confidence score, accuracy breakdown, and trend indicator.
 * Returns an empty payload (has_sufficient_data=false) when no metrics have
 * been computed yet.
 * Returns HTTP 404 when the project does not exist.
 */
export async function getProjectStrategyLearning(
  projectId: string,
  signal?: AbortSignal,
): Promise<StrategyLearningResponse> {
  return apiFetch<StrategyLearningResponse>(
    `/projects/${encodeURIComponent(projectId)}/strategy-learning`,
    { signal },
  );
}

/**
 * Fetch the portfolio-level strategy learning summary.
 *
 * Provides average confidence, high/low confidence counts,
 * top performing and weak-area project lists.
 */
export async function getPortfolioStrategyLearning(
  signal?: AbortSignal,
): Promise<PortfolioLearningSummaryResponse> {
  return apiFetch<PortfolioLearningSummaryResponse>(
    "/portfolio/strategy-learning",
    { signal },
  );
}
