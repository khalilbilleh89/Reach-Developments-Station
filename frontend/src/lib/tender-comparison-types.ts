/**
 * tender-comparison-types.ts — TypeScript types for the Tender Comparison
 * & Cost Variance domain.
 *
 * These types mirror the Pydantic schemas in
 * app/modules/tender_comparison/schemas.py and the enumerations in
 * app/shared/enums/tender_comparison.py.
 *
 * ComparisonStage values:
 *   "baseline_vs_tender" | "tender_vs_award" | "award_vs_variation" |
 *   "baseline_vs_award" | "baseline_vs_completion"
 *
 * VarianceReason values:
 *   "quantity_change" | "unit_rate_change" | "scope_change" |
 *   "ve_saving" | "contingency_shift" | "other"
 */

// ---------------------------------------------------------------------------
// Enum-like string literals
// ---------------------------------------------------------------------------

/** Stage of the comparison (which two states are being compared). */
export type ComparisonStage =
  | "baseline_vs_tender"
  | "tender_vs_award"
  | "award_vs_variation"
  | "baseline_vs_award"
  | "baseline_vs_completion";

/** Reason explaining why the variance occurred. */
export type VarianceReason =
  | "quantity_change"
  | "unit_rate_change"
  | "scope_change"
  | "ve_saving"
  | "contingency_shift"
  | "other";

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

export const COMPARISON_STAGE_LABELS: Record<ComparisonStage, string> = {
  baseline_vs_tender: "Baseline vs Tender",
  tender_vs_award: "Tender vs Award",
  award_vs_variation: "Award vs Variation",
  baseline_vs_award: "Baseline vs Award",
  baseline_vs_completion: "Baseline vs Completion",
};

export const VARIANCE_REASON_LABELS: Record<VarianceReason, string> = {
  quantity_change: "Quantity Change",
  unit_rate_change: "Unit Rate Change",
  scope_change: "Scope Change",
  ve_saving: "VE Saving",
  contingency_shift: "Contingency Shift",
  other: "Other",
};

export const COMPARISON_STAGE_OPTIONS: {
  value: ComparisonStage;
  label: string;
}[] = (
  Object.entries(COMPARISON_STAGE_LABELS) as [ComparisonStage, string][]
).map(([value, label]) => ({ value, label }));

export const VARIANCE_REASON_OPTIONS: {
  value: VarianceReason;
  label: string;
}[] = (Object.entries(VARIANCE_REASON_LABELS) as [VarianceReason, string][]).map(
  ([value, label]) => ({ value, label }),
);

// ---------------------------------------------------------------------------
// ConstructionCostComparisonLine
// ---------------------------------------------------------------------------

/** Mirrors ConstructionCostComparisonLineCreate */
export interface ConstructionCostComparisonLineCreate {
  cost_category?: import("./construction-cost-types").CostCategory;
  baseline_amount?: number;
  comparison_amount?: number;
  variance_reason?: VarianceReason;
  notes?: string | null;
}

/** Mirrors ConstructionCostComparisonLineUpdate (all optional) */
export interface ConstructionCostComparisonLineUpdate {
  cost_category?: import("./construction-cost-types").CostCategory;
  baseline_amount?: number;
  comparison_amount?: number;
  variance_reason?: VarianceReason;
  notes?: string | null;
}

/** Mirrors ConstructionCostComparisonLineResponse */
export interface ConstructionCostComparisonLine {
  id: string;
  comparison_set_id: string;
  cost_category: import("./construction-cost-types").CostCategory;
  /** Backend Decimal serialised as string. */
  baseline_amount: string;
  /** Backend Decimal serialised as string. */
  comparison_amount: string;
  /** Backend Decimal serialised as string. */
  variance_amount: string;
  /** Backend Decimal serialised as string, or null when baseline is zero. */
  variance_pct: string | null;
  variance_reason: VarianceReason;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// ConstructionCostComparisonSet
// ---------------------------------------------------------------------------

/** Mirrors ConstructionCostComparisonSetCreate */
export interface ConstructionCostComparisonSetCreate {
  title: string;
  comparison_stage?: ComparisonStage;
  baseline_label?: string;
  comparison_label?: string;
  notes?: string | null;
  is_active?: boolean;
}

/** Mirrors ConstructionCostComparisonSetUpdate (all optional) */
export interface ConstructionCostComparisonSetUpdate {
  title?: string;
  comparison_stage?: ComparisonStage;
  baseline_label?: string;
  comparison_label?: string;
  notes?: string | null;
  is_active?: boolean;
}

/** Mirrors ConstructionCostComparisonSetListItem (no lines) */
export interface ConstructionCostComparisonSetListItem {
  id: string;
  project_id: string;
  title: string;
  comparison_stage: ComparisonStage;
  baseline_label: string;
  comparison_label: string;
  notes: string | null;
  is_active: boolean;
  /** PR-V6-13: baseline governance */
  is_approved_baseline: boolean;
  approved_at: string | null;
  approved_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

/** Mirrors ConstructionCostComparisonSetResponse (includes lines) */
export interface ConstructionCostComparisonSet {
  id: string;
  project_id: string;
  title: string;
  comparison_stage: ComparisonStage;
  baseline_label: string;
  comparison_label: string;
  notes: string | null;
  is_active: boolean;
  /** PR-V6-13: baseline governance */
  is_approved_baseline: boolean;
  approved_at: string | null;
  approved_by_user_id: string | null;
  lines: ConstructionCostComparisonLine[];
  created_at: string;
  updated_at: string;
}

/** Mirrors ConstructionCostComparisonSetList */
export interface ConstructionCostComparisonSetList {
  total: number;
  items: ConstructionCostComparisonSetListItem[];
}

/** Mirrors ConstructionCostComparisonSummaryResponse */
export interface ConstructionCostComparisonSummary {
  comparison_set_id: string;
  project_id: string;
  line_count: number;
  /** Backend Decimal serialised as string. */
  total_baseline: string;
  /** Backend Decimal serialised as string. */
  total_comparison: string;
  /** Backend Decimal serialised as string. */
  total_variance: string;
  /** Backend Decimal serialised as string, or null when baseline is zero. */
  total_variance_pct: string | null;
}

/** Mirrors ActiveTenderBaselineResponse (PR-V6-13) */
export interface ActiveTenderBaseline {
  project_id: string;
  has_approved_baseline: boolean;
  baseline: ConstructionCostComparisonSetListItem | null;
}
