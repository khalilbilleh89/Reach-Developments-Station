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
