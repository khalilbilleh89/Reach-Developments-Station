/**
 * land-api.ts — API wrapper for the Land domain.
 *
 * All land data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   POST   /land/parcels                                      → create parcel
 *   GET    /land/parcels                                      → list parcels
 *   GET    /land/parcels/{id}                                 → get parcel by id
 *   PATCH  /land/parcels/{id}                                 → update parcel
 *   DELETE /land/parcels/{id}                                 → delete parcel
 *   POST   /land/parcels/{id}/assign-project/{project_id}    → assign to project
 *   POST   /land/parcels/{id}/assumptions                     → create assumptions
 *   GET    /land/parcels/{id}/assumptions                     → list assumptions
 *   POST   /land/parcels/{id}/valuations                      → create valuation
 *   GET    /land/parcels/{id}/valuations                      → list valuations
 */

import { apiFetch } from "./api-client";
import type {
  LandAssumption,
  LandParcel,
  LandParcelCreate,
  LandParcelList,
  LandParcelUpdate,
  LandScenarioType,
  LandValuation,
} from "./land-types";

// ── Parcel API ────────────────────────────────────────────────────────────────

export async function listLandParcels(params?: {
  project_id?: string;
  skip?: number;
  limit?: number;
}): Promise<LandParcelList> {
  const query = new URLSearchParams();
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<LandParcelList>(`/land/parcels${qs ? `?${qs}` : ""}`);
}

export async function getLandParcel(id: string): Promise<LandParcel> {
  return apiFetch<LandParcel>(`/land/parcels/${encodeURIComponent(id)}`);
}

export async function createLandParcel(
  data: LandParcelCreate,
): Promise<LandParcel> {
  return apiFetch<LandParcel>("/land/parcels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateLandParcel(
  id: string,
  data: LandParcelUpdate,
): Promise<LandParcel> {
  return apiFetch<LandParcel>(`/land/parcels/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteLandParcel(id: string): Promise<void> {
  return apiFetch<void>(`/land/parcels/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function assignLandToProject(
  parcelId: string,
  projectId: string,
): Promise<LandParcel> {
  return apiFetch<LandParcel>(
    `/land/parcels/${encodeURIComponent(parcelId)}/assign-project/${encodeURIComponent(projectId)}`,
    { method: "POST" },
  );
}

// ── Assumptions API ───────────────────────────────────────────────────────────

export async function listLandAssumptions(
  parcelId: string,
): Promise<LandAssumption[]> {
  return apiFetch<LandAssumption[]>(
    `/land/parcels/${encodeURIComponent(parcelId)}/assumptions`,
  );
}

export async function createLandAssumption(
  parcelId: string,
  data: {
    target_use?: string | null;
    expected_sellable_ratio?: number | null;
    parking_ratio?: number | null;
    service_area_ratio?: number | null;
    notes?: string | null;
  },
): Promise<LandAssumption> {
  return apiFetch<LandAssumption>(
    `/land/parcels/${encodeURIComponent(parcelId)}/assumptions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

// ── Valuation API ─────────────────────────────────────────────────────────────

export async function listLandValuations(
  parcelId: string,
): Promise<LandValuation[]> {
  return apiFetch<LandValuation[]>(
    `/land/parcels/${encodeURIComponent(parcelId)}/valuations`,
  );
}

export async function createLandValuation(
  parcelId: string,
  data: {
    scenario_name: string;
    scenario_type?: LandScenarioType;
    assumed_sale_price_per_sqm?: number | null;
    assumed_cost_per_sqm?: number | null;
    valuation_notes?: string | null;
  },
): Promise<LandValuation> {
  return apiFetch<LandValuation>(
    `/land/parcels/${encodeURIComponent(parcelId)}/valuations`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}
