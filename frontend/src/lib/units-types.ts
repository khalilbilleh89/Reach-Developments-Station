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
 * Possible lifecycle states for a unit reservation.
 * Values mirror the backend ReservationStatus enum.
 */
export type ReservationStatus = "draft" | "active" | "expired" | "cancelled" | "converted";

/** Human-readable label for a ReservationStatus value. */
export function reservationStatusLabel(status: ReservationStatus | string): string {
  const labels: Record<string, string> = {
    draft: "Draft",
    active: "Reserved",
    expired: "Expired",
    cancelled: "Cancelled",
    converted: "Converted",
  };
  return (
    labels[status] ??
    status
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

/**
 * A unit reservation record returned by the API.
 * Reflects the backend ReservationResponse schema.
 */
export interface Reservation {
  id: string;
  unit_id: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string | null;
  reservation_price: number;
  reservation_fee: number | null;
  currency: string;
  status: ReservationStatus;
  expires_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Payload for creating a new unit reservation.
 * Sent to POST /api/v1/reservations.
 */
export interface ReservationCreate {
  unit_id: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string | null;
  reservation_price: number;
  reservation_fee?: number | null;
  currency?: string;
  expires_at?: string | null;
  notes?: string | null;
}

/** Paginated list response for reservations. */
export interface ReservationListResponse {
  total: number;
  items: Reservation[];
}
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
 * Readiness state for the unit pricing detail page.
 *
 * - READY: pricing engine returned a valid calculation result.
 * - MISSING_ATTRIBUTES: backend returned HTTP 422 — engine inputs are
 *   not configured yet.  Show a setup prompt, not an error banner.
 * - MISSING_PRICING_RECORD: no pricing record exists for the unit (404).
 *
 * Unexpected backend or network failures are thrown as errors, not captured
 * here, so the calling component can show a true error banner.
 */
export type PricingDetailState =
  | "READY"
  | "MISSING_ATTRIBUTES"
  | "MISSING_PRICING_RECORD";

/**
 * Explicit pricing readiness for a unit's numerical engine inputs.
 * Returned by GET /api/v1/pricing/unit/{unitId}/readiness.
 *
 * Separates the readiness of the pricing ENGINE inputs (base_price_per_sqm,
 * floor_premium, etc.) from the qualitative attributes managed by the
 * EditAttributesModal (view_type, corner_unit, etc.).  Only the engine inputs
 * block price calculation — qualitative attributes are informational.
 */
export interface PricingReadiness {
  unit_id: string;
  is_ready_for_pricing: boolean;
  /** List of engine-input field names that are not yet set. Empty when ready. */
  missing_required_fields: string[];
  /** Human-readable explanation when not ready; null when ready. */
  readiness_reason: string | null;
}

/**
 * Combined unit pricing detail used by the detail page.
 * Aggregates unit data, pricing attributes, and calculated price.
 */
export interface UnitPricingDetail {
  unit: UnitDetail;
  pricing: UnitPrice | null;
  attributes: UnitPricingAttributes | null;
  pricingState: PricingDetailState;
  /** Explicit readiness from the backend inspection endpoint. */
  readiness: PricingReadiness | null;
}

// ---------- Inventory create/update types --------------------------------

/** Payload for creating a new unit (floor_id provided in body). */
export interface UnitCreate {
  floor_id: string;
  unit_number: string;
  unit_type: UnitType;
  internal_area: number;
  status?: UnitStatus;
  balcony_area?: number | null;
  terrace_area?: number | null;
  roof_garden_area?: number | null;
  front_garden_area?: number | null;
  gross_area?: number | null;
}

/** Payload for creating a new unit via floor-scoped route (floor_id from URL). */
export interface UnitCreateForFloor {
  unit_number: string;
  unit_type: UnitType;
  internal_area: number;
  status?: UnitStatus;
  balcony_area?: number | null;
  terrace_area?: number | null;
  roof_garden_area?: number | null;
  front_garden_area?: number | null;
  gross_area?: number | null;
}

/** Payload for partially updating a unit. */
export interface UnitUpdate {
  unit_type?: UnitType;
  status?: UnitStatus;
  internal_area?: number;
  balcony_area?: number | null;
  terrace_area?: number | null;
  roof_garden_area?: number | null;
  front_garden_area?: number | null;
  gross_area?: number | null;
}

/** Response envelope for list endpoints. */
export interface UnitListResponse {
  items: UnitListItem[];
  total: number;
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

// ---------- Unit pricing record types ------------------------------------

/**
 * Formal pricing status for a unit pricing record.
 * Values mirror the backend pricing_status constraint in the unit_pricing table.
 */
export type PricingStatus = "draft" | "reviewed" | "approved";

/** Human-readable label for a PricingStatus value. */
export function pricingStatusLabel(status: PricingStatus | string): string {
  const labels: Record<string, string> = {
    draft: "Draft",
    reviewed: "Reviewed",
    approved: "Approved",
  };
  return labels[status] ?? status;
}

/**
 * Formal per-unit pricing record.
 * Returned by GET /api/v1/units/{unitId}/pricing.
 */
export interface UnitPricingRecord {
  id: string;
  unit_id: string;
  base_price: number;
  manual_adjustment: number;
  final_price: number;
  currency: string;
  pricing_status: PricingStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Payload for creating or updating a formal per-unit pricing record.
 * Sent to PUT /api/v1/units/{unitId}/pricing.
 * final_price is NOT sent — it is computed server-side.
 */
export interface UnitPricingRecordSave {
  base_price: number;
  manual_adjustment?: number;
  currency?: string;
  pricing_status?: PricingStatus;
  notes?: string | null;
}

// ---------- Qualitative pricing attributes types -------------------------

/**
 * Qualitative view type classification.
 */
export type ViewType = "city" | "sea" | "park" | "interior";

/**
 * Floor premium category classification.
 */
export type FloorPremiumCategory = "standard" | "premium" | "penthouse";

/**
 * Cardinal orientation.
 */
export type Orientation = "N" | "S" | "E" | "W" | "NE" | "NW" | "SE" | "SW";

/**
 * Outdoor area premium treatment.
 */
export type OutdoorAreaPremium = "none" | "balcony" | "terrace" | "roof_garden";

/**
 * Qualitative pricing attributes for a unit.
 * Returned by GET /api/v1/units/{unitId}/pricing-attributes.
 *
 * Captures qualitative characteristics that influence pricing decisions:
 * view type, corner unit flag, floor category, orientation, outdoor premium,
 * upgrade flag, and analyst notes.
 */
export interface UnitQualitativeAttributes {
  id: string;
  unit_id: string;
  view_type: ViewType | null;
  corner_unit: boolean | null;
  floor_premium_category: FloorPremiumCategory | null;
  orientation: Orientation | null;
  outdoor_area_premium: OutdoorAreaPremium | null;
  upgrade_flag: boolean | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Payload for creating or updating qualitative pricing attributes.
 * Sent to PUT /api/v1/units/{unitId}/pricing-attributes.
 */
export interface UnitQualitativeAttributesSave {
  view_type?: ViewType | null;
  corner_unit?: boolean | null;
  floor_premium_category?: FloorPremiumCategory | null;
  orientation?: Orientation | null;
  outdoor_area_premium?: OutdoorAreaPremium | null;
  upgrade_flag?: boolean | null;
  notes?: string | null;
}
