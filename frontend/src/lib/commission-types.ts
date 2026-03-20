/**
 * commission-types.ts — TypeScript types for the Commission domain.
 *
 * These types mirror the Pydantic schemas defined in
 * app/modules/commission/schemas.py and the enumerations in
 * app/shared/enums/commission.py.
 *
 * CalculationMode values:
 *   "marginal" | "cumulative"
 *
 * CommissionPayoutStatus values:
 *   "draft" | "calculated" | "approved" | "cancelled"
 *
 * CommissionPartyType values:
 *   "sales_rep" | "team_lead" | "manager" | "broker" | "platform"
 */

// ---------------------------------------------------------------------------
// Enum-like string literals
// ---------------------------------------------------------------------------

/** Mirrors CalculationMode enum from app/shared/enums/commission.py */
export type CalculationMode = "marginal" | "cumulative";

/** Mirrors CommissionPayoutStatus enum from app/shared/enums/commission.py */
export type CommissionPayoutStatus =
  | "draft"
  | "calculated"
  | "approved"
  | "cancelled";

/** Mirrors CommissionPartyType enum from app/shared/enums/commission.py */
export type CommissionPartyType =
  | "sales_rep"
  | "team_lead"
  | "manager"
  | "broker"
  | "platform";

// ---------------------------------------------------------------------------
// CommissionPlan
// ---------------------------------------------------------------------------

/** Mirrors CommissionPlanResponse */
export interface CommissionPlan {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  pool_percentage: number;
  calculation_mode: CalculationMode;
  is_active: boolean;
  effective_from: string | null;
  effective_to: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// CommissionSlab
// ---------------------------------------------------------------------------

/** Mirrors CommissionSlabResponse */
export interface CommissionSlab {
  id: string;
  commission_plan_id: string;
  range_from: number;
  range_to: number | null;
  sales_rep_pct: number;
  team_lead_pct: number;
  manager_pct: number;
  broker_pct: number;
  platform_pct: number;
  sequence: number;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// CommissionPayoutLine
// ---------------------------------------------------------------------------

/** Mirrors CommissionPayoutLineResponse */
export interface CommissionPayoutLine {
  id: string;
  commission_payout_id: string;
  party_type: CommissionPartyType;
  party_reference: string | null;
  slab_id: string | null;
  amount: number;
  percentage: number;
  value_covered: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// CommissionPayout
// ---------------------------------------------------------------------------

/** Mirrors CommissionPayoutResponse (with per-line detail) */
export interface CommissionPayout {
  id: string;
  project_id: string;
  sale_contract_id: string;
  commission_plan_id: string;
  gross_sale_value: number;
  commission_pool_value: number;
  calculation_mode: CalculationMode;
  status: CommissionPayoutStatus;
  calculated_at: string | null;
  approved_at: string | null;
  notes: string | null;
  lines: CommissionPayoutLine[];
  created_at: string;
  updated_at: string;
}

/** Mirrors CommissionPayoutListItem (lightweight, no per-line detail) */
export interface CommissionPayoutListItem {
  id: string;
  project_id: string;
  sale_contract_id: string;
  commission_plan_id: string;
  gross_sale_value: number;
  commission_pool_value: number;
  calculation_mode: CalculationMode;
  status: CommissionPayoutStatus;
  calculated_at: string | null;
  approved_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/** Mirrors CommissionPayoutListResponse */
export interface CommissionPayoutList {
  total: number;
  items: CommissionPayoutListItem[];
}

// ---------------------------------------------------------------------------
// CommissionSummary
// ---------------------------------------------------------------------------

/** Mirrors CommissionSummaryResponse */
export interface CommissionSummary {
  project_id: string;
  total_payouts: number;
  draft_payouts: number;
  calculated_payouts: number;
  approved_payouts: number;
  cancelled_payouts: number;
  total_gross_value: number;
  total_commission_pool: number;
}
