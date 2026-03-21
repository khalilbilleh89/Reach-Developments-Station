/**
 * pricing-types.ts
 *
 * TypeScript contracts for the Pricing domain lifecycle.
 *
 * These types mirror the backend pricing schemas in:
 *   app/modules/pricing/schemas.py
 *   app/modules/pricing/status_rules.py
 */

/**
 * Canonical pricing lifecycle statuses.
 * Transitions: draft → submitted → approved → archived.
 * The ``reviewed`` value is retained for backward compatibility.
 */
export type PricingStatus =
  | "draft"
  | "submitted"
  | "reviewed"
  | "approved"
  | "archived";

/** Human-readable labels for each pricing status. */
export const PRICING_STATUS_LABELS: Record<PricingStatus, string> = {
  draft: "Draft",
  submitted: "Submitted",
  reviewed: "Reviewed",
  approved: "Approved",
  archived: "Archived",
};

/**
 * Returns true when a pricing record in *status* is immutable
 * (cannot be edited via PUT /pricing/{id}).
 */
export function isPricingImmutable(status: PricingStatus | string): boolean {
  return status === "approved" || status === "archived";
}

/**
 * Formal per-unit pricing record returned by the backend.
 * Mirrors UnitPricingResponse in app/modules/pricing/schemas.py.
 */
export interface UnitPricing {
  id: string;
  unit_id: string;
  base_price: number;
  manual_adjustment: number;
  final_price: number;
  currency: string;
  pricing_status: PricingStatus;
  notes: string | null;
  approved_by: string | null;
  approval_date: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Payload for creating a new pricing record under the hardened lifecycle.
 * Sent to POST /api/v1/units/{unitId}/pricing.
 * The backend always creates the record as 'draft' regardless of any
 * pricing_status field in this payload.
 */
export interface UnitPricingCreateRequest {
  base_price: number;
  manual_adjustment?: number;
  currency?: string;
  notes?: string | null;
}

/**
 * Payload for partially updating a pricing record.
 * Sent to PUT /api/v1/pricing/{pricingId}.
 * Rejected when the record is approved or archived.
 */
export interface UnitPricingUpdateRequest {
  base_price?: number;
  manual_adjustment?: number;
  currency?: string;
  pricing_status?: PricingStatus;
  notes?: string | null;
}

/**
 * Payload for approving a pricing record.
 * Sent to POST /api/v1/pricing/{pricingId}/approve.
 */
export interface PricingApprovalRequest {
  approved_by: string;
}

/**
 * Pricing history response — all records for a unit including archived ones.
 * Returned by GET /api/v1/units/{unitId}/pricing/history.
 */
export interface PricingHistoryResponse {
  unit_id: string;
  total: number;
  items: UnitPricing[];
}

/**
 * Detailed premium breakdown for a pricing record.
 * Returned by GET /api/v1/pricing/{pricingId}/premium-breakdown.
 *
 * Shows how the engine-calculated price is composed from the base price per
 * sqm and each individual premium component.  When ``has_engine_breakdown``
 * is false, all engine-derived fields are null and only the formal pricing
 * record values are available.
 */
export interface PremiumBreakdownResponse {
  pricing_id: string;
  unit_id: string;
  // Formal pricing record values — always present.
  base_price: number;
  manual_adjustment: number;
  final_price: number;
  currency: string;
  // Engine-based breakdown — present only when pricing attributes exist.
  has_engine_breakdown: boolean;
  base_price_per_sqm: number | null;
  unit_area: number | null;
  engine_base_unit_price: number | null;
  floor_premium: number | null;
  view_premium: number | null;
  corner_premium: number | null;
  size_adjustment: number | null;
  custom_adjustment: number | null;
  premium_total: number | null;
  engine_final_unit_price: number | null;
}

/**
 * Request payload for applying a governed price override.
 * Sent to POST /api/v1/pricing/{pricingId}/override.
 *
 * The ``override_amount`` replaces the current ``manual_adjustment``.
 * The override percentage (abs(override_amount) / base_price × 100) must be
 * within the authority threshold for the caller's ``role``.
 */
export interface PricingOverrideRequest {
  override_amount: number;
  override_reason: string;
  requested_by: string;
  /** Role key: 'sales_manager' | 'development_director' | 'ceo' */
  role: string;
}

/**
 * Override authority roles supported by the backend override rule engine.
 * Thresholds: sales_manager ≤ 2%, development_director ≤ 5%, ceo = unlimited.
 */
export type OverrideRole = "sales_manager" | "development_director" | "ceo";

/** Human-readable labels for each override role. */
export const OVERRIDE_ROLE_LABELS: Record<OverrideRole, string> = {
  sales_manager: "Sales Manager",
  development_director: "Development Director",
  ceo: "CEO",
};
