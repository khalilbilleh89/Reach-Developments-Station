/**
 * buildings-api.ts — API wrapper for the Buildings domain.
 *
 * All building data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   GET    /phases/{phaseId}/buildings        → list buildings for phase
 *   POST   /phases/{phaseId}/buildings        → create building in phase
 *   GET    /buildings/{buildingId}            → get building by id
 *   PATCH  /buildings/{buildingId}            → update building
 *   DELETE /buildings/{buildingId}            → delete building
 */

import { apiFetch } from "./api-client";
import type {
  Building,
  BuildingCreate,
  BuildingListResponse,
  BuildingUpdate,
} from "./buildings-types";

export async function listBuildings(
  phaseId: string,
): Promise<BuildingListResponse> {
  return apiFetch<BuildingListResponse>(
    `/phases/${encodeURIComponent(phaseId)}/buildings`,
  );
}

export async function getBuilding(buildingId: string): Promise<Building> {
  return apiFetch<Building>(`/buildings/${encodeURIComponent(buildingId)}`);
}

export async function createBuilding(
  phaseId: string,
  data: BuildingCreate,
): Promise<Building> {
  return apiFetch<Building>(
    `/phases/${encodeURIComponent(phaseId)}/buildings`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}

export async function updateBuilding(
  buildingId: string,
  data: BuildingUpdate,
): Promise<Building> {
  return apiFetch<Building>(`/buildings/${encodeURIComponent(buildingId)}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteBuilding(buildingId: string): Promise<void> {
  return apiFetch<void>(`/buildings/${encodeURIComponent(buildingId)}`, {
    method: "DELETE",
  });
}
