/**
 * construction-scorecard-api.ts — Typed API client for the Construction
 * Analytics & Project Scorecard endpoints (PR-V6-14).
 *
 * Backend endpoints used:
 *   GET /projects/{projectId}/construction-scorecard
 *     → ConstructionProjectScorecard
 *   GET /construction/portfolio/scorecards
 *     → ConstructionPortfolioScorecardsResponse
 *   GET /portfolio/construction-scorecards
 *     → ConstructionPortfolioScorecardsResponse (portfolio API surface)
 *
 * No business logic, no metric transformation, and no client-side
 * re-computation of scorecard values.
 */

import { apiFetch } from "./api-client";
import type {
  ConstructionPortfolioScorecardsResponse,
  ConstructionProjectScorecard,
} from "./construction-scorecard-types";

/**
 * Fetch the construction health scorecard for a single project.
 *
 * Returns an incomplete-state scorecard when no approved baseline exists.
 * Throws ApiError on HTTP errors (including 404 for unknown projects).
 */
export async function getProjectConstructionScorecard(
  projectId: string,
): Promise<ConstructionProjectScorecard> {
  return apiFetch<ConstructionProjectScorecard>(
    `/projects/${projectId}/construction-scorecard`,
  );
}

/**
 * Fetch the portfolio-wide construction health scorecards.
 *
 * Returns a summary with health counts, all project items ordered by
 * severity, top-risk projects, and projects missing an approved baseline.
 */
export async function getConstructionPortfolioScorecards(): Promise<ConstructionPortfolioScorecardsResponse> {
  return apiFetch<ConstructionPortfolioScorecardsResponse>(
    "/portfolio/construction-scorecards",
  );
}
