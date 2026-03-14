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
 *   GET /projects                             → project list
 *   GET /units?floor_id=&skip=&limit=         → unit list
 *   GET /units/{unitId}                       → unit detail
 *   GET /pricing/unit/{unitId}                → calculated unit price
 *   GET /pricing/unit/{unitId}/attributes     → pricing attributes
 */

import { apiFetch } from "./api-client";
import type {
  Project,
  UnitDetail,
  UnitFiltersState,
  UnitListItem,
  UnitPrice,
  UnitPricingAttributes,
  UnitPricingDetail,
} from "./units-types";

// ---------- Raw backend response envelopes (internal) --------------------

interface ProjectListResponse {
  items: Project[];
  total: number;
}

interface UnitListResponse {
  items: UnitListItem[];
  total: number;
}

// ---------- Query functions ----------------------------------------------

/** Fetch the list of all projects. */
export async function getProjects(): Promise<Project[]> {
  const data = await apiFetch<ProjectListResponse>("/projects");
  return data.items;
}

/**
 * Fetch units for a given floor, or all units if no floor_id is provided.
 * The backend /units endpoint does not natively filter by project, so the
 * caller is expected to derive the relevant floor IDs and filter client-side,
 * or pass a floor_id if navigating from the hierarchy.
 *
 * When no floor_id filter is available, we load the full first page.
 */
export async function getUnitsByProject(
  _projectId: string,
  filters?: Partial<UnitFiltersState>,
): Promise<UnitListItem[]> {
  // Build query params — backend currently filters by floor_id only.
  // Status and type filtering is applied client-side from the returned list.
  const params = new URLSearchParams({ limit: "500" });
  const data = await apiFetch<UnitListResponse>(`/units?${params.toString()}`);

  let items = data.items;

  // Apply client-side filters for fields not natively supported by backend.
  if (filters?.status) {
    items = items.filter((u) => u.status === filters.status);
  }
  if (filters?.unit_type) {
    items = items.filter((u) => u.unit_type === filters.unit_type);
  }

  return items;
}

/** Fetch a single unit by its ID. */
export async function getUnitById(unitId: string): Promise<UnitDetail> {
  return apiFetch<UnitDetail>(`/units/${unitId}`);
}

/** Fetch the calculated price for a unit. Returns null if not yet priced. */
export async function getUnitPricing(unitId: string): Promise<UnitPrice | null> {
  try {
    return await apiFetch<UnitPrice>(`/pricing/unit/${unitId}`);
  } catch {
    return null;
  }
}

/** Fetch the pricing attributes stored for a unit. Returns null if none set. */
export async function getUnitPricingAttributes(
  unitId: string,
): Promise<UnitPricingAttributes | null> {
  try {
    return await apiFetch<UnitPricingAttributes>(
      `/pricing/unit/${unitId}/attributes`,
    );
  } catch {
    return null;
  }
}

/**
 * Fetch the combined unit detail + pricing data for the detail page.
 *
 * Fetches unit, pricing, and attributes in parallel. Pricing/attribute
 * failures are caught and surfaced as null rather than breaking the page,
 * because units can exist before pricing is configured.
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
