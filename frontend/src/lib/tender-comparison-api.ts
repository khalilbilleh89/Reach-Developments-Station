/**
 * tender-comparison-api.ts — API wrapper for the Tender Comparison &
 * Cost Variance domain.
 *
 * All tender comparison data fetching and mutation is centralised here.
 * No business logic — thin API client only.
 *
 * Backend endpoints used:
 *
 * Project-scoped:
 *   GET  /projects/{projectId}/tender-comparisons         → list sets
 *   POST /projects/{projectId}/tender-comparisons         → create set
 *
 * Set-level:
 *   GET   /tender-comparisons/{setId}          → get set (with lines)
 *   PATCH /tender-comparisons/{setId}          → update set
 *   GET   /tender-comparisons/{setId}/summary  → get set summary
 *
 * Line-level:
 *   POST   /tender-comparisons/{setId}/lines        → create line
 *   PATCH  /tender-comparisons/lines/{lineId}       → update line
 *   DELETE /tender-comparisons/lines/{lineId}       → delete line
 */

import { apiFetch } from "./api-client";
import type {
  ConstructionCostComparisonLine,
  ConstructionCostComparisonLineCreate,
  ConstructionCostComparisonLineUpdate,
  ConstructionCostComparisonSet,
  ConstructionCostComparisonSetCreate,
  ConstructionCostComparisonSetList,
  ConstructionCostComparisonSetListItem,
  ConstructionCostComparisonSetUpdate,
  ConstructionCostComparisonSummary,
} from "./tender-comparison-types";

// ---------------------------------------------------------------------------
// Project-scoped endpoints
// ---------------------------------------------------------------------------

export async function listProjectTenderComparisons(
  projectId: string,
  params?: {
    is_active?: boolean;
    skip?: number;
    limit?: number;
  },
): Promise<ConstructionCostComparisonSetList> {
  const query = new URLSearchParams();
  if (params?.is_active !== undefined)
    query.set("is_active", String(params.is_active));
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));

  const qs = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<ConstructionCostComparisonSetList>(
    `/projects/${projectId}/tender-comparisons${qs}`,
  );
}

export async function createTenderComparison(
  projectId: string,
  payload: ConstructionCostComparisonSetCreate,
): Promise<ConstructionCostComparisonSet> {
  return apiFetch<ConstructionCostComparisonSet>(
    `/projects/${projectId}/tender-comparisons`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

// ---------------------------------------------------------------------------
// Set-level endpoints
// ---------------------------------------------------------------------------

export async function getTenderComparison(
  setId: string,
): Promise<ConstructionCostComparisonSet> {
  return apiFetch<ConstructionCostComparisonSet>(`/tender-comparisons/${setId}`);
}

export async function updateTenderComparison(
  setId: string,
  payload: ConstructionCostComparisonSetUpdate,
): Promise<ConstructionCostComparisonSet> {
  return apiFetch<ConstructionCostComparisonSet>(
    `/tender-comparisons/${setId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export async function getTenderComparisonSummary(
  setId: string,
): Promise<ConstructionCostComparisonSummary> {
  return apiFetch<ConstructionCostComparisonSummary>(
    `/tender-comparisons/${setId}/summary`,
  );
}

// ---------------------------------------------------------------------------
// Line-level endpoints
// ---------------------------------------------------------------------------

export async function createComparisonLine(
  setId: string,
  payload: ConstructionCostComparisonLineCreate,
): Promise<ConstructionCostComparisonLine> {
  return apiFetch<ConstructionCostComparisonLine>(
    `/tender-comparisons/${setId}/lines`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function updateComparisonLine(
  lineId: string,
  payload: ConstructionCostComparisonLineUpdate,
): Promise<ConstructionCostComparisonLine> {
  return apiFetch<ConstructionCostComparisonLine>(
    `/tender-comparisons/lines/${lineId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export async function deleteComparisonLine(lineId: string): Promise<void> {
  return apiFetch<void>(`/tender-comparisons/lines/${lineId}`, {
    method: "DELETE",
  });
}
