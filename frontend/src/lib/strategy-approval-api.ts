/**
 * strategy-approval-api.ts — Typed API clients for the Strategy Approval
 * Workflow endpoints (PR-V7-08).
 *
 * Backend endpoints:
 *   POST /api/v1/projects/{id}/strategy-approval
 *   POST /api/v1/approvals/{id}/approve
 *   POST /api/v1/approvals/{id}/reject
 *   GET  /api/v1/projects/{id}/strategy-approval
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type {
  ApproveStrategyRequest,
  RejectStrategyRequest,
  StrategyApprovalCreateRequest,
  StrategyApprovalResponse,
} from "./strategy-approval-types";

/**
 * Create a new pending strategy approval request for a project.
 *
 * Returns HTTP 409 when a pending approval already exists for the project.
 * Returns HTTP 404 when the project does not exist.
 */
export async function createStrategyApproval(
  projectId: string,
  body: StrategyApprovalCreateRequest,
  signal?: AbortSignal,
): Promise<StrategyApprovalResponse> {
  return apiFetch<StrategyApprovalResponse>(
    `/projects/${encodeURIComponent(projectId)}/strategy-approval`,
    { method: "POST", body: JSON.stringify(body), signal },
  );
}

/**
 * Approve a pending strategy approval request.
 *
 * Returns HTTP 404 when the approval record does not exist.
 * Returns HTTP 422 when the approval is not in pending state.
 */
export async function approveStrategy(
  approvalId: string,
  body: ApproveStrategyRequest,
  signal?: AbortSignal,
): Promise<StrategyApprovalResponse> {
  return apiFetch<StrategyApprovalResponse>(
    `/approvals/${encodeURIComponent(approvalId)}/approve`,
    { method: "POST", body: JSON.stringify(body), signal },
  );
}

/**
 * Reject a pending strategy approval request.
 *
 * Returns HTTP 404 when the approval record does not exist.
 * Returns HTTP 422 when the approval is not in pending state.
 */
export async function rejectStrategy(
  approvalId: string,
  body: RejectStrategyRequest,
  signal?: AbortSignal,
): Promise<StrategyApprovalResponse> {
  return apiFetch<StrategyApprovalResponse>(
    `/approvals/${encodeURIComponent(approvalId)}/reject`,
    { method: "POST", body: JSON.stringify(body), signal },
  );
}

/**
 * Fetch the latest approval record for a project.
 *
 * Returns null when no approval has been requested yet.
 * Returns HTTP 404 when the project does not exist.
 */
export async function getLatestStrategyApproval(
  projectId: string,
  signal?: AbortSignal,
): Promise<StrategyApprovalResponse | null> {
  return apiFetch<StrategyApprovalResponse | null>(
    `/projects/${encodeURIComponent(projectId)}/strategy-approval`,
    { signal },
  );
}
