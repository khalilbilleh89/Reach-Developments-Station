/**
 * units-types.ts — shared frontend types for the units/pricing UI.
 *
 * Centralised here so that pages, components, and the API wrapper all
 * reference the same shapes. PR-020 can import from this file directly.
 *
 * These types reflect the backend API contracts for:
 *   GET /api/v1/units
 *   GET /api/v1/units/{unitId}
 *   GET /api/v1/pricing/unit/{unitId}
 *   GET /api/v1/pricing/unit/{unitId}/attributes
 *   GET /api/v1/projects
 */

// ---------- Unit types ---------------------------------------------------

/**
 * Possible commercial statuses for a unit.
 * Values mirror the backend UnitStatus enum in app/shared/enums/project.py.
 */
export type UnitStatus =
  | "available"
  | "reserved"
  | "under_contract"
  | "registered";

/**
 * Possible unit types.
 * Values mirror the backend UnitType enum in app/shared/enums/project.py.
 */
export type UnitType =
  | "studio"
  | "one_bedroom"
  | "two_bedroom"
  | "three_bedroom"
  | "four_bedroom"
  | "villa"
  | "townhouse"
  | "retail"
  | "office"
  | "penthouse";

/** Human-readable label for a UnitStatus value. */
export function unitStatusLabel(status: UnitStatus | string): string {
  const labels: Record<string, string> = {
    available: "Available",
    reserved: "Reserved",
    under_contract: "Under Contract",
    registered: "Registered",
  };
  return (
    labels[status] ??
    status
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

/** Human-readable label for a UnitType value. */
export function unitTypeLabel(type: UnitType | string): string {
  const labels: Record<string, string> = {
    studio: "Studio",
    one_bedroom: "1 Bedroom",
    two_bedroom: "2 Bedroom",
    three_bedroom: "3 Bedroom",
    four_bedroom: "4 Bedroom",
    villa: "Villa",
    townhouse: "Townhouse",
    retail: "Retail",
    office: "Office",
    penthouse: "Penthouse",
  };
  return (
    labels[type] ??
    type
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

/** A unit as returned by GET /api/v1/units (list item). */
export interface UnitListItem {
  id: string;
  floor_id: string;
  unit_number: string;
  unit_type: UnitType;
  status: UnitStatus;
  internal_area: number;
  balcony_area: number | null;
  terrace_area: number | null;
  roof_garden_area: number | null;
  front_garden_area: number | null;
  gross_area: number | null;
}

/** Full unit detail as returned by GET /api/v1/units/{unitId}. */
export type UnitDetail = UnitListItem;

// ---------- Pricing types ------------------------------------------------

/**
 * Pricing attributes (premiums/adjustments) stored for a unit.
 * Returned by GET /api/v1/pricing/unit/{unitId}/attributes.
 */
export interface UnitPricingAttributes {
  id: string;
  unit_id: string;
  base_price_per_sqm: number | null;
  floor_premium: number | null;
  view_premium: number | null;
  corner_premium: number | null;
  size_adjustment: number | null;
  custom_adjustment: number | null;
}

/**
 * Calculated price result for a unit.
 * Returned by GET /api/v1/pricing/unit/{unitId}.
 */
export interface UnitPrice {
  unit_id: string;
  unit_area: number;
  base_unit_price: number;
  premium_total: number;
  final_unit_price: number;
}

/**
 * Combined unit pricing detail used by the detail page.
 * Aggregates unit data, pricing attributes, and calculated price.
 */
export interface UnitPricingDetail {
  unit: UnitDetail;
  pricing: UnitPrice | null;
  attributes: UnitPricingAttributes | null;
}

// ---------- Filter state -------------------------------------------------

/** UI filter state for the units listing page. */
export interface UnitFiltersState {
  status: UnitStatus | "";
  unit_type: UnitType | "";
  min_price: string;
  max_price: string;
}

// ---------- Project type (re-exported for convenience) -------------------

export interface Project {
  id: string;
  name: string;
  code: string;
  status: string;
}
