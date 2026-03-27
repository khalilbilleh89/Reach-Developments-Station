/**
 * scenario-api.ts — API wrapper for the Scenario Engine module.
 *
 * All scenario data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   POST   /scenarios                              → create scenario
 *   GET    /scenarios                              → list scenarios
 *   GET    /scenarios/{id}                         → get scenario by id
 *   PATCH  /scenarios/{id}                         → update scenario
 *   POST   /scenarios/{id}/duplicate               → duplicate scenario
 *   POST   /scenarios/{id}/approve                 → approve scenario
 *   POST   /scenarios/{id}/archive                 → archive scenario
 *   POST   /scenarios/compare                      → compare scenarios
 *   GET    /scenarios/{id}/versions                → list versions
 *   GET    /scenarios/{id}/versions/latest         → get latest version
 */

import { apiFetch } from "./api-client";
import type {
  Scenario,
  ScenarioCompareRequest,
  ScenarioCompareResponse,
  ScenarioCreate,
  ScenarioDuplicateRequest,
  ScenarioList,
  ScenarioStatus,
  ScenarioUpdate,
  ScenarioVersion,
  ScenarioVersionList,
} from "./scenario-types";

// ---------------------------------------------------------------------------
// Scenario CRUD
// ---------------------------------------------------------------------------

export async function listScenarios(params?: {
  source_type?: string;
  project_id?: string;
  land_id?: string;
  status?: ScenarioStatus;
  skip?: number;
  limit?: number;
}): Promise<ScenarioList> {
  const query = new URLSearchParams();
  if (params?.source_type) query.set("source_type", params.source_type);
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.land_id) query.set("land_id", params.land_id);
  if (params?.status) query.set("status", params.status);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<ScenarioList>(`/scenarios${qs ? `?${qs}` : ""}`);
}

export async function getScenario(scenarioId: string): Promise<Scenario> {
  return apiFetch<Scenario>(`/scenarios/${encodeURIComponent(scenarioId)}`);
}

export async function createScenario(data: ScenarioCreate): Promise<Scenario> {
  return apiFetch<Scenario>("/scenarios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateScenario(
  scenarioId: string,
  data: ScenarioUpdate,
): Promise<Scenario> {
  return apiFetch<Scenario>(`/scenarios/${encodeURIComponent(scenarioId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Duplication
// ---------------------------------------------------------------------------

export async function duplicateScenario(
  scenarioId: string,
  data: ScenarioDuplicateRequest,
): Promise<Scenario> {
  return apiFetch<Scenario>(
    `/scenarios/${encodeURIComponent(scenarioId)}/duplicate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

export async function approveScenario(scenarioId: string): Promise<Scenario> {
  return apiFetch<Scenario>(
    `/scenarios/${encodeURIComponent(scenarioId)}/approve`,
    { method: "POST" },
  );
}

export async function archiveScenario(scenarioId: string): Promise<Scenario> {
  return apiFetch<Scenario>(
    `/scenarios/${encodeURIComponent(scenarioId)}/archive`,
    { method: "POST" },
  );
}

// ---------------------------------------------------------------------------
// Comparison
// ---------------------------------------------------------------------------

export async function compareScenarios(
  data: ScenarioCompareRequest,
): Promise<ScenarioCompareResponse> {
  return apiFetch<ScenarioCompareResponse>("/scenarios/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Versions
// ---------------------------------------------------------------------------

export async function listScenarioVersions(
  scenarioId: string,
): Promise<ScenarioVersionList> {
  return apiFetch<ScenarioVersionList>(
    `/scenarios/${encodeURIComponent(scenarioId)}/versions`,
  );
}

export async function getLatestScenarioVersion(
  scenarioId: string,
): Promise<ScenarioVersion> {
  return apiFetch<ScenarioVersion>(
    `/scenarios/${encodeURIComponent(scenarioId)}/versions/latest`,
  );
}
