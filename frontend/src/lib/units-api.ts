/**
 * units-api.ts — centralized API wrapper for units and pricing endpoints.
 *
 * This module is the normalization boundary between the backend API contract
 * and the frontend UI model. Raw backend responses are passed through here
 * so that components can rely on stable, UI-friendly types.
 *
 * No pricing calculations are performed here — values are sourced directly
 * from the backend pricing engine.
 *
 * Backend endpoints used:
 *   GET    /projects                             → project list
 *   GET    /phases?project_id=                   → phases for a project
 *   GET    /buildings?phase_id=                  → buildings for a phase
 *   GET    /buildings/{building_id}/floors        → floors for a building
 *   GET    /floors/{floor_id}/units              → units for a floor (floor-scoped)
 *   POST   /floors/{floor_id}/units              → create unit in floor
 *   GET    /units?floor_id=                      → units for a floor (flat with filter)
 *   POST   /units                                → create unit (body includes floor_id)
 *   GET    /units/{unitId}                       → unit detail
 *   PATCH  /units/{unitId}                       → update unit
 *   DELETE /units/{unitId}                       → delete unit
 *   GET    /pricing/unit/{unitId}                → calculated unit price
 *   GET    /pricing/unit/{unitId}/attributes     → pricing attributes
 */

import { apiFetch, ApiError } from "./api-client";
import type {
  Project,
  UnitCreate,
  UnitCreateForFloor,
  UnitDetail,
  UnitListItem,
  UnitListResponse,
  UnitPrice,
  UnitPricingAttributes,
  UnitPricingDetail,
  UnitUpdate,
} from "./units-types";

// Note: UnitListResponse is imported from "./units-types" above.

// ---------- Raw backend response envelopes (internal) --------------------

interface ProjectListResponse {
  items: Project[];
  total: number;
}

interface PhaseItem {
  id: string;
}

interface PhaseListResponse {
  items: PhaseItem[];
  total: number;
}

interface BuildingItem {
  id: string;
}

interface BuildingListResponse {
  items: BuildingItem[];
  total: number;
}

interface FloorItem {
  id: string;
}

interface FloorListResponse {
  items: FloorItem[];
  total: number;
}

// ---------- Error discrimination ------------------------------------------

/**
 * Returns true if the error represents a "not found / not configured" state
 * — i.e. an HTTP 404 from the backend.
 * All other errors (5xx, network, auth) are considered unexpected and should
 * be propagated to the caller.
 */
function isNotFoundError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404;
}

// ---------- Query functions ----------------------------------------------

/** Fetch the list of all projects. */
export async function getProjects(): Promise<Project[]> {
  const data = await apiFetch<ProjectListResponse>("/projects");
  return data.items;
}

/**
 * Fetch all units belonging to a given project.
 *
 * The backend /units endpoint does not support direct project-level
 * filtering. We walk the hierarchy:
 *   Project → Phases → Buildings → Floors → Units
 *
 * All hierarchy traversals are parallelised where possible. An empty
 * project (no phases) returns an empty array gracefully.
 */
export async function getUnitsByProject(
  projectId: string,
): Promise<UnitListItem[]> {
  // 1. Phases for this project
  const phasesData = await apiFetch<PhaseListResponse>(
    `/phases?project_id=${projectId}&limit=500`,
  );
  if (phasesData.items.length === 0) return [];

  // 2. Buildings for all phases — in parallel
  const buildingResponses = await Promise.all(
    phasesData.items.map((phase) =>
      apiFetch<BuildingListResponse>(`/buildings?phase_id=${phase.id}&limit=500`),
    ),
  );
  const buildings = buildingResponses.flatMap((r) => r.items);
  if (buildings.length === 0) return [];

  // 3. Floors for all buildings — in parallel
  const floorResponses = await Promise.all(
    buildings.map((building) =>
      apiFetch<FloorListResponse>(
        `/buildings/${building.id}/floors?limit=500`,
      ),
    ),
  );
  const floors = floorResponses.flatMap((r) => r.items);
  if (floors.length === 0) return [];

  // 4. Units for all floors — in parallel
  const unitResponses = await Promise.all(
    floors.map((floor) =>
      apiFetch<UnitListResponse>(`/units?floor_id=${floor.id}&limit=500`),
    ),
  );
  return unitResponses.flatMap((r) => r.items);
}

/** Fetch a single unit by its ID. */
export async function getUnitById(unitId: string): Promise<UnitDetail> {
  return apiFetch<UnitDetail>(`/units/${unitId}`);
}

/**
 * Fetch the calculated price for a unit.
 *
 * Returns null when the unit has not been priced yet (404 / not-found).
 * Unexpected errors (5xx, network failures, auth errors) are propagated
 * so that the calling component can show a proper error state.
 */
export async function getUnitPricing(unitId: string): Promise<UnitPrice | null> {
  try {
    return await apiFetch<UnitPrice>(`/pricing/unit/${unitId}`);
  } catch (err: unknown) {
    if (isNotFoundError(err)) return null;
    throw err;
  }
}

/**
 * Fetch the pricing attributes stored for a unit.
 *
 * Returns null when no attributes have been configured yet (404 / not-found).
 * Unexpected errors are propagated so the caller can show an error state.
 */
export async function getUnitPricingAttributes(
  unitId: string,
): Promise<UnitPricingAttributes | null> {
  try {
    return await apiFetch<UnitPricingAttributes>(
      `/pricing/unit/${unitId}/attributes`,
    );
  } catch (err: unknown) {
    if (isNotFoundError(err)) return null;
    throw err;
  }
}

/**
 * Fetch the combined unit detail + pricing data for the detail page.
 *
 * Fetches unit, pricing, and attributes in parallel. Pricing/attribute
 * "not found" states are surfaced as null; unexpected errors are propagated.
 */
export async function getUnitPricingDetail(
  unitId: string,
): Promise<UnitPricingDetail> {
  const [unit, pricing, attributes] = await Promise.all([
    getUnitById(unitId),
    getUnitPricing(unitId),
    getUnitPricingAttributes(unitId),
  ]);
  return { unit, pricing, attributes };
}

// ---------- Inventory CRUD functions -------------------------------------

/**
 * Fetch units for a specific floor (floor-scoped endpoint).
 */
export async function listUnitsByFloor(
  floorId: string,
  limit = 500,
): Promise<UnitListResponse> {
  return apiFetch<UnitListResponse>(
    `/floors/${encodeURIComponent(floorId)}/units?limit=${limit}`,
  );
}

/**
 * Create a unit in a specific floor using the floor-scoped endpoint.
 */
export async function createUnit(
  floorId: string,
  data: UnitCreateForFloor,
): Promise<UnitDetail> {
  return apiFetch<UnitDetail>(
    `/floors/${encodeURIComponent(floorId)}/units`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}

/**
 * Update an existing unit by ID.
 */
export async function updateUnit(
  unitId: string,
  data: UnitUpdate,
): Promise<UnitDetail> {
  return apiFetch<UnitDetail>(`/units/${encodeURIComponent(unitId)}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/**
 * Delete a unit by ID. Returns undefined on success (204 No Content).
 */
export async function deleteUnit(unitId: string): Promise<void> {
  await apiFetch<undefined>(`/units/${encodeURIComponent(unitId)}`, {
    method: "DELETE",
  });
}
