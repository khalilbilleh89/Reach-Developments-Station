/**
 * strategy-execution-trigger-api.ts — Typed API clients for the Strategy
 * Execution Trigger module endpoints (PR-V7-09).
 *
 * Backend endpoints:
 *   POST /api/v1/projects/{id}/strategy-execution-trigger
 *   GET  /api/v1/projects/{id}/strategy-execution-trigger
 *   POST /api/v1/execution-triggers/{id}/start
 *   POST /api/v1/execution-triggers/{id}/complete
 *   POST /api/v1/execution-triggers/{id}/cancel
 *   GET  /api/v1/portfolio/execution-triggers
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type {
  CancelExecutionTriggerRequest,
  PortfolioExecutionTriggerSummaryResponse,
  StrategyExecutionTriggerResponse,
} from "./strategy-execution-trigger-types";

/**
 * Create a formal execution handoff trigger for an approved project strategy.
 *
 * Returns HTTP 401 when the authenticated user identity (sub) is absent.
 * Returns HTTP 404 when the project does not exist.
 * Returns HTTP 409 when an active trigger already exists for the project.
 * Returns HTTP 422 when the latest strategy approval is not 'approved'.
 */
export async function createStrategyExecutionTrigger(
  projectId: string,
  signal?: AbortSignal,
): Promise<StrategyExecutionTriggerResponse> {
  return apiFetch<StrategyExecutionTriggerResponse>(
    `/projects/${encodeURIComponent(projectId)}/strategy-execution-trigger`,
    { method: "POST", body: JSON.stringify({}), signal },
  );
}

/**
 * Transition a triggered execution to in_progress.
 *
 * Returns HTTP 404 when the trigger record does not exist.
 * Returns HTTP 422 when the trigger is not in 'triggered' state.
 */
export async function startStrategyExecutionTrigger(
  triggerId: string,
  signal?: AbortSignal,
): Promise<StrategyExecutionTriggerResponse> {
  return apiFetch<StrategyExecutionTriggerResponse>(
    `/execution-triggers/${encodeURIComponent(triggerId)}/start`,
    { method: "POST", body: JSON.stringify({}), signal },
  );
}

/**
 * Transition an in_progress execution to completed.
 *
 * Returns HTTP 404 when the trigger record does not exist.
 * Returns HTTP 422 when the trigger is not in 'in_progress' state.
 */
export async function completeStrategyExecutionTrigger(
  triggerId: string,
  signal?: AbortSignal,
): Promise<StrategyExecutionTriggerResponse> {
  return apiFetch<StrategyExecutionTriggerResponse>(
    `/execution-triggers/${encodeURIComponent(triggerId)}/complete`,
    { method: "POST", body: JSON.stringify({}), signal },
  );
}

/**
 * Cancel a triggered or in_progress execution.
 *
 * Returns HTTP 404 when the trigger record does not exist.
 * Returns HTTP 422 when the trigger is in a terminal state (completed or cancelled).
 */
export async function cancelStrategyExecutionTrigger(
  triggerId: string,
  body: CancelExecutionTriggerRequest,
  signal?: AbortSignal,
): Promise<StrategyExecutionTriggerResponse> {
  return apiFetch<StrategyExecutionTriggerResponse>(
    `/execution-triggers/${encodeURIComponent(triggerId)}/cancel`,
    { method: "POST", body: JSON.stringify(body), signal },
  );
}

/**
 * Fetch the latest execution trigger record for a project.
 *
 * Returns null when no trigger has been created for the project yet.
 * Returns HTTP 404 when the project does not exist.
 */
export async function getProjectStrategyExecutionTrigger(
  projectId: string,
  signal?: AbortSignal,
): Promise<StrategyExecutionTriggerResponse | null> {
  return apiFetch<StrategyExecutionTriggerResponse | null>(
    `/projects/${encodeURIComponent(projectId)}/strategy-execution-trigger`,
    { signal },
  );
}

/**
 * Fetch the portfolio-level execution trigger summary.
 *
 * Returns status counts, active handoffs, and projects awaiting trigger.
 */
export async function getPortfolioExecutionTriggers(
  signal?: AbortSignal,
): Promise<PortfolioExecutionTriggerSummaryResponse> {
  return apiFetch<PortfolioExecutionTriggerSummaryResponse>(
    "/portfolio/execution-triggers",
    { signal },
  );
}
