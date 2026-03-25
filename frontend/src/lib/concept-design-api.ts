/**
 * concept-design-api.ts — API client for the Concept Design domain.
 *
 * Typed wrappers around the existing backend endpoints at
 * /api/v1/concept-options (registered in app/modules/concept_design/api.py).
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints:
 *   POST   /concept-options                                → create option
 *   GET    /concept-options                                → list options
 *   GET    /concept-options/compare                        → compare options
 *   GET    /concept-options/{id}                           → get option
 *   PATCH  /concept-options/{id}                           → update option
 *   DELETE /concept-options/{id}                           → delete option
 *   POST   /concept-options/{id}/duplicate                 → duplicate option
 *   POST   /concept-options/{id}/unit-mix                  → add mix line
 *   GET    /concept-options/{id}/summary                   → get summary
 *   POST   /concept-options/{id}/promote                   → promote option
 *
 * PR-CONCEPT-055, PR-CONCEPT-057, PR-CONCEPT-058
 */

import { apiFetch } from "./api-client";
import type {
  ConceptOption,
  ConceptOptionComparisonResponse,
  ConceptOptionCreate,
  ConceptOptionListResponse,
  ConceptOptionSummary,
  ConceptOptionUpdate,
  ConceptPromotionRequest,
  ConceptPromotionResponse,
  ConceptUnitMixLine,
  ConceptUnitMixLineCreate,
} from "./concept-design-types";

// ---------------------------------------------------------------------------
// ConceptOption endpoints
// ---------------------------------------------------------------------------

export async function listConceptOptions(params?: {
  project_id?: string;
  scenario_id?: string;
  skip?: number;
  limit?: number;
}): Promise<ConceptOptionListResponse> {
  const query = new URLSearchParams();
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.scenario_id) query.set("scenario_id", params.scenario_id);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<ConceptOptionListResponse>(
    `/concept-options${qs ? `?${qs}` : ""}`,
  );
}

export async function getConceptOption(id: string): Promise<ConceptOption> {
  return apiFetch<ConceptOption>(
    `/concept-options/${encodeURIComponent(id)}`,
  );
}

export async function createConceptOption(
  data: ConceptOptionCreate,
): Promise<ConceptOption> {
  return apiFetch<ConceptOption>("/concept-options", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateConceptOption(
  id: string,
  data: ConceptOptionUpdate,
): Promise<ConceptOption> {
  return apiFetch<ConceptOption>(
    `/concept-options/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

// ---------------------------------------------------------------------------
// Unit-mix endpoint
// ---------------------------------------------------------------------------

export async function addConceptUnitMixLine(
  id: string,
  data: ConceptUnitMixLineCreate,
): Promise<ConceptUnitMixLine> {
  return apiFetch<ConceptUnitMixLine>(
    `/concept-options/${encodeURIComponent(id)}/unit-mix`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

// ---------------------------------------------------------------------------
// Summary endpoint
// ---------------------------------------------------------------------------

export async function getConceptOptionSummary(
  id: string,
): Promise<ConceptOptionSummary> {
  return apiFetch<ConceptOptionSummary>(
    `/concept-options/${encodeURIComponent(id)}/summary`,
  );
}

// ---------------------------------------------------------------------------
// Comparison endpoint
// ---------------------------------------------------------------------------

export async function compareConceptOptions(params: {
  project_id?: string;
  scenario_id?: string;
}): Promise<ConceptOptionComparisonResponse> {
  const hasProject = Boolean(params.project_id);
  const hasScenario = Boolean(params.scenario_id);
  if (!hasProject && !hasScenario) {
    return Promise.reject(
      new Error("compareConceptOptions requires exactly one of project_id or scenario_id."),
    );
  }
  if (hasProject && hasScenario) {
    return Promise.reject(
      new Error("compareConceptOptions accepts only one of project_id or scenario_id, not both."),
    );
  }
  const query = new URLSearchParams();
  if (params.project_id) query.set("project_id", params.project_id);
  if (params.scenario_id) query.set("scenario_id", params.scenario_id);
  const qs = query.toString();
  return apiFetch<ConceptOptionComparisonResponse>(
    `/concept-options/compare${qs ? `?${qs}` : ""}`,
  );
}

// ---------------------------------------------------------------------------
// Promotion endpoint
// ---------------------------------------------------------------------------

export async function promoteConceptOption(
  id: string,
  data?: ConceptPromotionRequest,
): Promise<ConceptPromotionResponse> {
  return apiFetch<ConceptPromotionResponse>(
    `/concept-options/${encodeURIComponent(id)}/promote`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data ?? {}),
    },
  );
}

// ---------------------------------------------------------------------------
// Delete endpoint — PR-CONCEPT-057
// ---------------------------------------------------------------------------

export async function deleteConceptOption(id: string): Promise<void> {
  await apiFetch<void>(
    `/concept-options/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}

// ---------------------------------------------------------------------------
// Duplicate endpoint — PR-CONCEPT-058
// ---------------------------------------------------------------------------

export async function duplicateConceptOption(id: string): Promise<ConceptOption> {
  return apiFetch<ConceptOption>(
    `/concept-options/${encodeURIComponent(id)}/duplicate`,
    { method: "POST" },
  );
}
