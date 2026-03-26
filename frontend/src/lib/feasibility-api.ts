/**
 * feasibility-api.ts — API wrapper for the Feasibility domain.
 *
 * All feasibility data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   POST   /feasibility/runs                              → create run
 *   GET    /feasibility/runs                              → list runs
 *   GET    /feasibility/runs/{run_id}                     → get run by id
 *   PATCH  /feasibility/runs/{run_id}                     → update run
 *   POST   /feasibility/runs/{run_id}/assumptions         → upsert assumptions
 *   PATCH  /feasibility/runs/{run_id}/assumptions         → partial update assumptions
 *   GET    /feasibility/runs/{run_id}/assumptions         → get assumptions
 *   POST   /feasibility/runs/{run_id}/calculate           → run calculation
 *   GET    /feasibility/runs/{run_id}/results             → get results
 *   GET    /feasibility/runs/{run_id}/lineage             → get lineage trace
 */

import { apiFetch } from "./api-client";
import type {
  FeasibilityAssumptions,
  FeasibilityAssumptionsCreate,
  FeasibilityAssumptionsUpdate,
  FeasibilityLineageResponse,
  FeasibilityResult,
  FeasibilityRun,
  FeasibilityRunCreate,
  FeasibilityRunList,
  FeasibilityRunUpdate,
} from "./feasibility-types";

// ---------------------------------------------------------------------------
// Run endpoints
// ---------------------------------------------------------------------------

export async function listFeasibilityRuns(params?: {
  project_id?: string;
  skip?: number;
  limit?: number;
}): Promise<FeasibilityRunList> {
  const query = new URLSearchParams();
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<FeasibilityRunList>(
    `/feasibility/runs${qs ? `?${qs}` : ""}`,
  );
}

export async function getFeasibilityRun(runId: string): Promise<FeasibilityRun> {
  return apiFetch<FeasibilityRun>(
    `/feasibility/runs/${encodeURIComponent(runId)}`,
  );
}

export async function createFeasibilityRun(
  data: FeasibilityRunCreate,
): Promise<FeasibilityRun> {
  return apiFetch<FeasibilityRun>("/feasibility/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateFeasibilityRun(
  runId: string,
  data: FeasibilityRunUpdate,
): Promise<FeasibilityRun> {
  return apiFetch<FeasibilityRun>(
    `/feasibility/runs/${encodeURIComponent(runId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function assignProjectToRun(
  runId: string,
  projectId: string | null,
): Promise<FeasibilityRun> {
  return updateFeasibilityRun(runId, { project_id: projectId });
}

// ---------------------------------------------------------------------------
// Assumptions endpoints
// ---------------------------------------------------------------------------

export async function upsertFeasibilityAssumptions(
  runId: string,
  data: FeasibilityAssumptionsCreate,
): Promise<FeasibilityAssumptions> {
  return apiFetch<FeasibilityAssumptions>(
    `/feasibility/runs/${encodeURIComponent(runId)}/assumptions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function patchFeasibilityAssumptions(
  runId: string,
  data: FeasibilityAssumptionsUpdate,
): Promise<FeasibilityAssumptions> {
  return apiFetch<FeasibilityAssumptions>(
    `/feasibility/runs/${encodeURIComponent(runId)}/assumptions`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function getFeasibilityAssumptions(
  runId: string,
): Promise<FeasibilityAssumptions> {
  return apiFetch<FeasibilityAssumptions>(
    `/feasibility/runs/${encodeURIComponent(runId)}/assumptions`,
  );
}

// ---------------------------------------------------------------------------
// Calculation and result endpoints
// ---------------------------------------------------------------------------

export async function calculateFeasibility(
  runId: string,
): Promise<FeasibilityResult> {
  return apiFetch<FeasibilityResult>(
    `/feasibility/runs/${encodeURIComponent(runId)}/calculate`,
    { method: "POST" },
  );
}

export async function getFeasibilityResults(
  runId: string,
): Promise<FeasibilityResult> {
  return apiFetch<FeasibilityResult>(
    `/feasibility/runs/${encodeURIComponent(runId)}/results`,
  );
}

// ---------------------------------------------------------------------------
// Lineage endpoint — PR-CONCEPT-065
// ---------------------------------------------------------------------------

export async function getFeasibilityRunLineage(
  runId: string,
): Promise<FeasibilityLineageResponse> {
  return apiFetch<FeasibilityLineageResponse>(
    `/feasibility/runs/${encodeURIComponent(runId)}/lineage`,
  );
}
