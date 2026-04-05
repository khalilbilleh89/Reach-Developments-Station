/**
 * strategy-execution-outcome-api.ts — Typed API clients for the Strategy
 * Execution Outcome module endpoints (PR-V7-10).
 *
 * Backend endpoints:
 *   POST /api/v1/execution-triggers/{id}/outcome
 *   GET  /api/v1/projects/{id}/strategy-execution-outcome
 *   GET  /api/v1/portfolio/execution-outcomes
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type {
  PortfolioExecutionOutcomeSummaryResponse,
  ProjectExecutionOutcomeResponse,
  RecordExecutionOutcomeRequest,
  StrategyExecutionOutcomeResponse,
} from "./strategy-execution-outcome-types";

/**
 * Record the realized execution outcome for an in-progress or completed trigger.
 *
 * Returns HTTP 401 when the authenticated user identity (sub) is absent.
 * Returns HTTP 404 when the trigger does not exist.
 * Returns HTTP 422 when the trigger is not in 'in_progress' or 'completed' state.
 */
export async function recordStrategyExecutionOutcome(
  triggerId: string,
  body: RecordExecutionOutcomeRequest,
  signal?: AbortSignal,
): Promise<StrategyExecutionOutcomeResponse> {
  return apiFetch<StrategyExecutionOutcomeResponse>(
    `/execution-triggers/${encodeURIComponent(triggerId)}/outcome`,
    { method: "POST", body: JSON.stringify(body), signal },
  );
}

/**
 * Fetch the latest execution outcome state for a project.
 *
 * Returns the most recent trigger context, eligibility flag, and the latest
 * recorded outcome (null when none has been recorded yet).
 * Returns HTTP 404 when the project does not exist.
 */
export async function getProjectStrategyExecutionOutcome(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectExecutionOutcomeResponse> {
  return apiFetch<ProjectExecutionOutcomeResponse>(
    `/projects/${encodeURIComponent(projectId)}/strategy-execution-outcome`,
    { signal },
  );
}

/**
 * Fetch the portfolio-level execution outcome summary.
 *
 * Returns outcome result counts, recent recorded outcomes, and projects
 * with completed triggers awaiting outcome recording.
 */
export async function getPortfolioExecutionOutcomes(
  signal?: AbortSignal,
): Promise<PortfolioExecutionOutcomeSummaryResponse> {
  return apiFetch<PortfolioExecutionOutcomeSummaryResponse>(
    "/portfolio/execution-outcomes",
    { signal },
  );
}
