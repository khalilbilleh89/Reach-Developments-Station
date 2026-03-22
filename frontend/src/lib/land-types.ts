/**
 * land-types.ts — TypeScript types for the Land domain.
 *
 * Mirrors the backend LandParcelResponse, LandAssumptionResponse,
 * and LandValuationResponse Pydantic schemas.
 */

export type LandStatus =
  | "draft"
  | "under_review"
  | "approved"
  | "archived";

export type LandScenarioType = "base" | "upside" | "downside" | "investor";

export interface LandParcel {
  id: string;
  project_id: string | null;
  parcel_name: string;
  parcel_code: string;
  country: string | null;
  city: string | null;
  district: string | null;
  address: string | null;
  land_area_sqm: number | null;
  frontage_m: number | null;
  depth_m: number | null;
  buildable_area_sqm: number | null;
  sellable_area_sqm: number | null;
  acquisition_price: number | null;
  transaction_cost: number | null;
  asking_price_per_sqm: number | null;
  supported_price_per_sqm: number | null;
  zoning_category: string | null;
  permitted_far: number | null;
  max_height_m: number | null;
  max_floors: number | null;
  corner_plot: boolean;
  utilities_available: boolean;
  status: LandStatus;
  created_at: string;
  updated_at: string;
  // Computed land basis metrics (server-derived — read-only)
  effective_land_basis: number | null;
  gross_land_price_per_sqm: number | null;
  effective_land_price_per_gross_sqm: number | null;
  effective_land_price_per_buildable_sqm: number | null;
  effective_land_price_per_sellable_sqm: number | null;
  supported_acquisition_price: number | null;
  residual_land_value: number | null;
  margin_impact: number | null;
}

export interface LandParcelList {
  items: LandParcel[];
  total: number;
}

export interface LandParcelCreate {
  project_id?: string | null;
  parcel_name: string;
  parcel_code: string;
  country?: string | null;
  city?: string | null;
  district?: string | null;
  address?: string | null;
  // Physical / dimensional attributes
  land_area_sqm?: number | null;
  frontage_m?: number | null;
  depth_m?: number | null;
  buildable_area_sqm?: number | null;
  sellable_area_sqm?: number | null;
  coverage_ratio?: number | null;
  density_ratio?: number | null;
  zoning_category?: string | null;
  permitted_far?: number | null;
  max_height_m?: number | null;
  max_floors?: number | null;
  corner_plot?: boolean;
  utilities_available?: boolean;
  // Acquisition economics
  acquisition_price?: number | null;
  transaction_cost?: number | null;
  currency?: string | null;
  asking_price_per_sqm?: number | null;
  supported_price_per_sqm?: number | null;
  // Governance / provenance
  assumption_notes?: string | null;
  source_notes?: string | null;
  status?: LandStatus;
}

export interface LandParcelUpdate {
  parcel_name?: string | null;
  country?: string | null;
  city?: string | null;
  district?: string | null;
  address?: string | null;
  // Physical / dimensional attributes
  land_area_sqm?: number | null;
  frontage_m?: number | null;
  depth_m?: number | null;
  buildable_area_sqm?: number | null;
  sellable_area_sqm?: number | null;
  coverage_ratio?: number | null;
  density_ratio?: number | null;
  zoning_category?: string | null;
  permitted_far?: number | null;
  max_height_m?: number | null;
  max_floors?: number | null;
  corner_plot?: boolean | null;
  utilities_available?: boolean | null;
  // Acquisition economics
  acquisition_price?: number | null;
  transaction_cost?: number | null;
  currency?: string | null;
  asking_price_per_sqm?: number | null;
  supported_price_per_sqm?: number | null;
  // Governance / provenance
  assumption_notes?: string | null;
  source_notes?: string | null;
  status?: LandStatus | null;
}

export interface LandAssumption {
  id: string;
  parcel_id: string;
  target_use: string | null;
  expected_sellable_ratio: number | null;
  expected_buildable_area_sqm: number | null;
  expected_sellable_area_sqm: number | null;
  parking_ratio: number | null;
  service_area_ratio: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface LandValuation {
  id: string;
  parcel_id: string;
  scenario_name: string;
  scenario_type: LandScenarioType;
  assumed_sale_price_per_sqm: number | null;
  assumed_cost_per_sqm: number | null;
  expected_gdv: number | null;
  expected_cost: number | null;
  residual_land_value: number | null;
  land_value_per_sqm: number | null;
  valuation_notes: string | null;
  created_at: string;
  updated_at: string;
}
