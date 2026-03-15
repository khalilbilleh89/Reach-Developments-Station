/**
 * floors-api.ts — API wrapper for the Floors domain.
 *
 * All floor data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   GET    /buildings/{buildingId}/floors   → list floors for building
 *   POST   /buildings/{buildingId}/floors   → create floor in building
 *   GET    /floors/{floorId}                → get floor by id
 *   PATCH  /floors/{floorId}                → update floor
 *   DELETE /floors/{floorId}                → delete floor
 */

import { apiFetch } from "./api-client";
import type {
  Floor,
  FloorCreate,
  FloorListResponse,
  FloorUpdate,
} from "./floors-types";

export async function listFloors(buildingId: string): Promise<FloorListResponse> {
  return apiFetch<FloorListResponse>(
    `/buildings/${encodeURIComponent(buildingId)}/floors`,
  );
}

export async function getFloor(floorId: string): Promise<Floor> {
  return apiFetch<Floor>(`/floors/${encodeURIComponent(floorId)}`);
}

export async function createFloor(
  buildingId: string,
  data: FloorCreate,
): Promise<Floor> {
  return apiFetch<Floor>(
    `/buildings/${encodeURIComponent(buildingId)}/floors`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}

export async function updateFloor(
  floorId: string,
  data: FloorUpdate,
): Promise<Floor> {
  return apiFetch<Floor>(`/floors/${encodeURIComponent(floorId)}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteFloor(floorId: string): Promise<void> {
  await apiFetch<undefined>(`/floors/${encodeURIComponent(floorId)}`, {
    method: "DELETE",
  });
}
