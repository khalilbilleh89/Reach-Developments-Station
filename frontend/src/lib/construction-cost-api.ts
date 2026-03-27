/**
 * construction-cost-api.ts — API wrapper for the Construction Cost Records domain.
 *
 * All construction cost data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *
 * Project-scoped:
 *   GET  /projects/{projectId}/construction-cost-records         → list records
 *   POST /projects/{projectId}/construction-cost-records         → create record
 *   GET  /projects/{projectId}/construction-cost-records/summary → summary totals
 *
 * Record-level:
 *   GET   /construction-cost-records/{id}          → get record
 *   PATCH /construction-cost-records/{id}          → update record
 *   POST  /construction-cost-records/{id}/archive  → archive record
 */

import { apiFetch } from "./api-client";
import type {
  ConstructionCostRecord,
  ConstructionCostRecordCreate,
  ConstructionCostRecordList,
  ConstructionCostRecordUpdate,
  ConstructionCostSummary,
  CostCategory,
  CostStage,
} from "./construction-cost-types";

// ---------------------------------------------------------------------------
// Project-scoped endpoints
// ---------------------------------------------------------------------------

export async function listProjectConstructionCostRecords(
  projectId: string,
  params?: {
    is_active?: boolean;
    cost_category?: CostCategory;
    cost_stage?: CostStage;
    skip?: number;
    limit?: number;
  },
): Promise<ConstructionCostRecordList> {
  const query = new URLSearchParams();
  if (params?.is_active !== undefined)
    query.set("is_active", String(params.is_active));
  if (params?.cost_category) query.set("cost_category", params.cost_category);
  if (params?.cost_stage) query.set("cost_stage", params.cost_stage);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));

  const qs = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<ConstructionCostRecordList>(
    `/projects/${projectId}/construction-cost-records${qs}`,
  );
}

export async function createConstructionCostRecord(
  projectId: string,
  payload: ConstructionCostRecordCreate,
): Promise<ConstructionCostRecord> {
  return apiFetch<ConstructionCostRecord>(
    `/projects/${projectId}/construction-cost-records`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function getConstructionCostSummary(
  projectId: string,
): Promise<ConstructionCostSummary> {
  return apiFetch<ConstructionCostSummary>(
    `/projects/${projectId}/construction-cost-records/summary`,
  );
}

// ---------------------------------------------------------------------------
// Record-level endpoints
// ---------------------------------------------------------------------------

export async function getConstructionCostRecord(
  id: string,
): Promise<ConstructionCostRecord> {
  return apiFetch<ConstructionCostRecord>(`/construction-cost-records/${id}`);
}

export async function updateConstructionCostRecord(
  id: string,
  payload: ConstructionCostRecordUpdate,
): Promise<ConstructionCostRecord> {
  return apiFetch<ConstructionCostRecord>(`/construction-cost-records/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function archiveConstructionCostRecord(
  id: string,
): Promise<ConstructionCostRecord> {
  return apiFetch<ConstructionCostRecord>(
    `/construction-cost-records/${id}/archive`,
    { method: "POST" },
  );
}
