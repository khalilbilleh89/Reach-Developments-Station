/**
 * commission-api.ts — API wrapper for the Commission domain.
 *
 * All commission data fetching is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *
 * Plans:
 *   GET  /commission/projects/{project_id}/plans → list plans for a project
 *   GET  /commission/plans/{plan_id}             → get a single plan
 *
 * Slabs:
 *   GET  /commission/plans/{plan_id}/slabs       → list slabs for a plan
 *
 * Payouts:
 *   GET  /commission/projects/{project_id}/payouts  → list payouts for a project
 *   GET  /commission/payouts/{payout_id}            → get a single payout
 *
 * Summary:
 *   GET  /commission/projects/{project_id}/summary → aggregate analytics
 */

import { apiFetch } from "./api-client";
import type {
  CommissionPlan,
  CommissionPayoutList,
  CommissionPayout,
  CommissionSlab,
  CommissionSummary,
} from "./commission-types";

// ---------------------------------------------------------------------------
// Plans
// ---------------------------------------------------------------------------

/**
 * List all commission plans for a project.
 *
 * Backend endpoint: GET /commission/projects/{projectId}/plans
 */
export async function listProjectCommissionPlans(
  projectId: string,
): Promise<CommissionPlan[]> {
  return apiFetch<CommissionPlan[]>(
    `/commission/projects/${encodeURIComponent(projectId)}/plans`,
  );
}

/**
 * Retrieve a single commission plan by ID.
 *
 * Backend endpoint: GET /commission/plans/{planId}
 */
export async function getCommissionPlan(
  planId: string,
): Promise<CommissionPlan> {
  return apiFetch<CommissionPlan>(
    `/commission/plans/${encodeURIComponent(planId)}`,
  );
}

// ---------------------------------------------------------------------------
// Slabs
// ---------------------------------------------------------------------------

/**
 * List all slabs for a commission plan.
 *
 * Backend endpoint: GET /commission/plans/{planId}/slabs
 */
export async function listCommissionSlabs(
  planId: string,
): Promise<CommissionSlab[]> {
  return apiFetch<CommissionSlab[]>(
    `/commission/plans/${encodeURIComponent(planId)}/slabs`,
  );
}

// ---------------------------------------------------------------------------
// Payouts
// ---------------------------------------------------------------------------

/**
 * List all commission payouts for a project.
 *
 * Backend endpoint: GET /commission/projects/{projectId}/payouts
 */
export async function listProjectCommissionPayouts(
  projectId: string,
  params?: { skip?: number; limit?: number },
): Promise<CommissionPayoutList> {
  const query = new URLSearchParams();
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<CommissionPayoutList>(
    `/commission/projects/${encodeURIComponent(projectId)}/payouts${qs ? `?${qs}` : ""}`,
  );
}

/**
 * Retrieve a single commission payout by ID (includes per-line detail).
 *
 * Backend endpoint: GET /commission/payouts/{payoutId}
 */
export async function getCommissionPayout(
  payoutId: string,
): Promise<CommissionPayout> {
  return apiFetch<CommissionPayout>(
    `/commission/payouts/${encodeURIComponent(payoutId)}`,
  );
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

/**
 * Retrieve commission aggregate analytics for a project.
 *
 * Backend endpoint: GET /commission/projects/{projectId}/summary
 */
export async function getProjectCommissionSummary(
  projectId: string,
): Promise<CommissionSummary> {
  return apiFetch<CommissionSummary>(
    `/commission/projects/${encodeURIComponent(projectId)}/summary`,
  );
}
