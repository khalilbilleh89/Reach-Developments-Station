/**
 * construction-api.ts — API wrapper for the Construction domain.
 *
 * All construction data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   POST   /construction/scopes               → create scope
 *   GET    /construction/scopes               → list scopes
 *   GET    /construction/scopes/{id}          → get scope by id
 *   PATCH  /construction/scopes/{id}          → update scope
 *   DELETE /construction/scopes/{id}          → delete scope
 *
 *   POST   /construction/milestones           → create milestone
 *   GET    /construction/milestones           → list milestones
 *   GET    /construction/milestones/{id}      → get milestone by id
 *   PATCH  /construction/milestones/{id}      → update milestone
 *   DELETE /construction/milestones/{id}      → delete milestone
 *
 *   POST   /construction/scopes/{id}/engineering-items  → create engineering item
 *   GET    /construction/scopes/{id}/engineering-items  → list engineering items
 *   PATCH  /construction/engineering-items/{id}         → update engineering item
 *   DELETE /construction/engineering-items/{id}         → delete engineering item
 *
 *   POST   /construction/scopes/{id}/cost-items         → create cost item
 *   GET    /construction/scopes/{id}/cost-items         → list cost items
 *   GET    /construction/scopes/{id}/cost-summary       → get scope cost summary
 *   GET    /construction/cost-items/{id}                → get cost item by id
 *   PATCH  /construction/cost-items/{id}                → update cost item
 *   DELETE /construction/cost-items/{id}                → delete cost item
 */

import { apiFetch } from "./api-client";
import type {
  ConstructionCostItem,
  ConstructionCostItemCreate,
  ConstructionCostItemListResponse,
  ConstructionCostItemUpdate,
  ConstructionCostSummary,
  ConstructionDashboardResponse,
  ConstructionEngineeringItem,
  ConstructionMilestone,
  ConstructionMilestoneCreate,
  ConstructionMilestoneListResponse,
  ConstructionMilestoneUpdate,
  ConstructionScope,
  ConstructionScopeCreate,
  ConstructionScopeListResponse,
  ConstructionScopeUpdate,
  EngineeringItemCreate,
  EngineeringItemListResponse,
  EngineeringItemUpdate,
} from "./construction-types";

// ── Scope API ────────────────────────────────────────────────────────────────

export async function listScopes(params?: {
  project_id?: string;
  phase_id?: string;
  building_id?: string;
  skip?: number;
  limit?: number;
}): Promise<ConstructionScopeListResponse> {
  const query = new URLSearchParams();
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.phase_id) query.set("phase_id", params.phase_id);
  if (params?.building_id) query.set("building_id", params.building_id);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<ConstructionScopeListResponse>(
    `/construction/scopes${qs ? `?${qs}` : ""}`,
  );
}

export async function getScope(id: string): Promise<ConstructionScope> {
  return apiFetch<ConstructionScope>(
    `/construction/scopes/${encodeURIComponent(id)}`,
  );
}

export async function createScope(
  data: ConstructionScopeCreate,
): Promise<ConstructionScope> {
  return apiFetch<ConstructionScope>("/construction/scopes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateScope(
  id: string,
  data: ConstructionScopeUpdate,
): Promise<ConstructionScope> {
  return apiFetch<ConstructionScope>(
    `/construction/scopes/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function deleteScope(id: string): Promise<void> {
  return apiFetch<void>(`/construction/scopes/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// ── Milestone API ────────────────────────────────────────────────────────────

export async function listMilestones(params?: {
  scope_id?: string;
  skip?: number;
  limit?: number;
}): Promise<ConstructionMilestoneListResponse> {
  const query = new URLSearchParams();
  if (params?.scope_id) query.set("scope_id", params.scope_id);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<ConstructionMilestoneListResponse>(
    `/construction/milestones${qs ? `?${qs}` : ""}`,
  );
}

export async function getMilestone(
  id: string,
): Promise<ConstructionMilestone> {
  return apiFetch<ConstructionMilestone>(
    `/construction/milestones/${encodeURIComponent(id)}`,
  );
}

export async function createMilestone(
  data: ConstructionMilestoneCreate,
): Promise<ConstructionMilestone> {
  return apiFetch<ConstructionMilestone>("/construction/milestones", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateMilestone(
  id: string,
  data: ConstructionMilestoneUpdate,
): Promise<ConstructionMilestone> {
  return apiFetch<ConstructionMilestone>(
    `/construction/milestones/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function deleteMilestone(id: string): Promise<void> {
  return apiFetch<void>(
    `/construction/milestones/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}

// ── Engineering item API ─────────────────────────────────────────────────────

export async function listEngineeringItems(
  scopeId: string,
  params?: { skip?: number; limit?: number },
): Promise<EngineeringItemListResponse> {
  const query = new URLSearchParams();
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<EngineeringItemListResponse>(
    `/construction/scopes/${encodeURIComponent(scopeId)}/engineering-items${qs ? `?${qs}` : ""}`,
  );
}

export async function createEngineeringItem(
  scopeId: string,
  data: EngineeringItemCreate,
): Promise<ConstructionEngineeringItem> {
  return apiFetch<ConstructionEngineeringItem>(
    `/construction/scopes/${encodeURIComponent(scopeId)}/engineering-items`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function updateEngineeringItem(
  id: string,
  data: EngineeringItemUpdate,
): Promise<ConstructionEngineeringItem> {
  return apiFetch<ConstructionEngineeringItem>(
    `/construction/engineering-items/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function deleteEngineeringItem(id: string): Promise<void> {
  return apiFetch<void>(
    `/construction/engineering-items/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}

// ── Cost item API ────────────────────────────────────────────────────────────

export async function listCostItems(
  scopeId: string,
  params?: { skip?: number; limit?: number; category?: string },
): Promise<ConstructionCostItemListResponse> {
  const query = new URLSearchParams();
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.category) query.set("category", params.category);
  const qs = query.toString();
  return apiFetch<ConstructionCostItemListResponse>(
    `/construction/scopes/${encodeURIComponent(scopeId)}/cost-items${qs ? `?${qs}` : ""}`,
  );
}

export async function createCostItem(
  scopeId: string,
  data: ConstructionCostItemCreate,
): Promise<ConstructionCostItem> {
  return apiFetch<ConstructionCostItem>(
    `/construction/scopes/${encodeURIComponent(scopeId)}/cost-items`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function getCostItem(id: string): Promise<ConstructionCostItem> {
  return apiFetch<ConstructionCostItem>(
    `/construction/cost-items/${encodeURIComponent(id)}`,
  );
}

export async function updateCostItem(
  id: string,
  data: ConstructionCostItemUpdate,
): Promise<ConstructionCostItem> {
  return apiFetch<ConstructionCostItem>(
    `/construction/cost-items/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function deleteCostItem(id: string): Promise<void> {
  return apiFetch<void>(
    `/construction/cost-items/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}

export async function getScopeCostSummary(
  scopeId: string,
): Promise<ConstructionCostSummary> {
  return apiFetch<ConstructionCostSummary>(
    `/construction/scopes/${encodeURIComponent(scopeId)}/cost-summary`,
  );
}

// ── Dashboard API ─────────────────────────────────────────────────────────────

export async function getProjectConstructionDashboard(
  projectId: string,
): Promise<ConstructionDashboardResponse> {
  return apiFetch<ConstructionDashboardResponse>(
    `/construction/projects/${encodeURIComponent(projectId)}/dashboard`,
  );
}
