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
 */

import { apiFetch } from "./api-client";
import type {
  ConstructionMilestone,
  ConstructionMilestoneCreate,
  ConstructionMilestoneListResponse,
  ConstructionMilestoneUpdate,
  ConstructionScope,
  ConstructionScopeCreate,
  ConstructionScopeListResponse,
  ConstructionScopeUpdate,
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
