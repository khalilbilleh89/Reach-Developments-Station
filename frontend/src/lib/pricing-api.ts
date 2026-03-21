/**
 * pricing-api.ts — typed API wrappers for the Pricing lifecycle domain.
 *
 * Provides functions for creating, updating, approving, and retrieving
 * formal per-unit pricing records under the governed lifecycle.
 *
 * No pricing calculations are performed here — all computation lives in
 * the backend pricing engine.
 *
 * Backend endpoints used:
 *   POST  /units/{unitId}/pricing              → create new pricing record (hardened)
 *   PUT   /units/{unitId}/pricing              → upsert pricing record (legacy)
 *   GET   /units/{unitId}/pricing              → get active pricing record
 *   GET   /units/{unitId}/pricing/history      → get full pricing history
 *   PUT   /pricing/{pricingId}                 → update specific pricing record
 *   POST  /pricing/{pricingId}/approve         → approve pricing record
 */

import { apiFetch } from "./api-client";
import type {
  PremiumBreakdownResponse,
  PricingApprovalRequest,
  PricingHistoryResponse,
  PricingOverrideRequest,
  UnitPricing,
  UnitPricingCreateRequest,
  UnitPricingUpdateRequest,
} from "./pricing-types";

/**
 * Create a new pricing record for *unitId* under the hardened lifecycle.
 *
 * The backend enforces unit readiness (unit must be 'available') and archives
 * any existing active pricing record before creating the new one.
 * The record always starts as 'draft'.
 *
 * @throws ApiError 422 when the unit is not ready for pricing.
 * @throws ApiError 404 when the unit does not exist.
 */
export async function createUnitPricing(
  unitId: string,
  data: UnitPricingCreateRequest,
): Promise<UnitPricing> {
  return apiFetch<UnitPricing>(`/units/${unitId}/pricing`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Partially update a specific pricing record by ID.
 *
 * Rejected when the record is in an immutable state (approved or archived).
 *
 * @throws ApiError 422 when the record is immutable or the update is invalid.
 * @throws ApiError 404 when the record does not exist.
 */
export async function updateUnitPricing(
  pricingId: string,
  data: UnitPricingUpdateRequest,
): Promise<UnitPricing> {
  return apiFetch<UnitPricing>(`/pricing/${pricingId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/**
 * Approve a pricing record, locking it against further edits.
 *
 * Sets pricing_status to 'approved', records the approver identifier and
 * the UTC approval timestamp.  Once approved, the record can only be
 * superseded by creating a new pricing record.
 *
 * @throws ApiError 422 when the record is already approved or archived.
 * @throws ApiError 404 when the record does not exist.
 */
export async function approvePricing(
  pricingId: string,
  data: PricingApprovalRequest,
): Promise<UnitPricing> {
  return apiFetch<UnitPricing>(`/pricing/${pricingId}/approve`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Return the active (non-archived) pricing record for *unitId*.
 *
 * @throws ApiError 404 when the unit does not exist or has no active pricing.
 */
export async function getUnitPricing(unitId: string): Promise<UnitPricing> {
  return apiFetch<UnitPricing>(`/units/${unitId}/pricing`);
}

/**
 * Return the full pricing history for *unitId*, newest first.
 *
 * Includes the active record and all archived (superseded) records.
 *
 * @throws ApiError 404 when the unit does not exist.
 */
export async function getPricingHistory(
  unitId: string,
): Promise<PricingHistoryResponse> {
  return apiFetch<PricingHistoryResponse>(`/units/${unitId}/pricing/history`);
}

/**
 * Return the detailed premium breakdown for a pricing record.
 *
 * Shows how the price is composed from base price per sqm and each premium
 * component (floor, view, corner, size, custom).  When no pricing attributes
 * exist for the unit, ``has_engine_breakdown`` is false.
 *
 * No premium calculation logic is performed here — all computation lives in
 * the backend pricing engine.
 *
 * @throws ApiError 404 when the pricing record does not exist.
 */
export async function getPremiumBreakdown(
  pricingId: string,
): Promise<PremiumBreakdownResponse> {
  return apiFetch<PremiumBreakdownResponse>(
    `/pricing/${pricingId}/premium-breakdown`,
  );
}

/**
 * Apply a governed price override to a pricing record.
 *
 * The ``override_amount`` replaces the current ``manual_adjustment``.
 * The backend validates the override percentage against the authority
 * threshold for the caller's ``role`` before applying it.
 *
 * Authority thresholds (percentage of base_price):
 * - ≤ 2%: Sales Manager
 * - ≤ 5%: Development Director
 * - > 5%: CEO
 *
 * @throws ApiError 422 when the override exceeds the caller's role authority.
 * @throws ApiError 422 when the record is approved or archived (immutable).
 * @throws ApiError 404 when the pricing record does not exist.
 */
export async function requestPricingOverride(
  pricingId: string,
  data: PricingOverrideRequest,
): Promise<UnitPricing> {
  return apiFetch<UnitPricing>(`/pricing/${pricingId}/override`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}
