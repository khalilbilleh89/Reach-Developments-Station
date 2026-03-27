/**
 * construction-cost-types.ts — TypeScript types for the Construction Cost Records domain.
 *
 * These types mirror the Pydantic schemas in
 * app/modules/construction_costs/schemas.py and the enumerations in
 * app/shared/enums/construction_costs.py.
 *
 * CostCategory values:
 *   "hard_cost" | "soft_cost" | "preliminaries" | "infrastructure" |
 *   "contingency" | "consultant_fee" | "tender_adjustment" | "variation"
 *
 * CostSource values:
 *   "estimate" | "tender" | "contract" | "variation" | "actual"
 *
 * CostStage values:
 *   "pre_design" | "design" | "tender" | "construction" |
 *   "completion" | "post_completion"
 */

// ---------------------------------------------------------------------------
// Enum-like string literals
// ---------------------------------------------------------------------------

/** Classification of the construction cost type. */
export type CostCategory =
  | "hard_cost"
  | "soft_cost"
  | "preliminaries"
  | "infrastructure"
  | "contingency"
  | "consultant_fee"
  | "tender_adjustment"
  | "variation";

/** Origin or evidential source of the cost record. */
export type CostSource = "estimate" | "tender" | "contract" | "variation" | "actual";

/** Project delivery stage at which this cost was captured. */
export type CostStage =
  | "pre_design"
  | "design"
  | "tender"
  | "construction"
  | "completion"
  | "post_completion";

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

export const COST_CATEGORY_LABELS: Record<CostCategory, string> = {
  hard_cost: "Hard Cost",
  soft_cost: "Soft Cost",
  preliminaries: "Preliminaries",
  infrastructure: "Infrastructure",
  contingency: "Contingency",
  consultant_fee: "Consultant Fee",
  tender_adjustment: "Tender Adjustment",
  variation: "Variation",
};

export const COST_SOURCE_LABELS: Record<CostSource, string> = {
  estimate: "Estimate",
  tender: "Tender",
  contract: "Contract",
  variation: "Variation",
  actual: "Actual",
};

export const COST_STAGE_LABELS: Record<CostStage, string> = {
  pre_design: "Pre-Design",
  design: "Design",
  tender: "Tender",
  construction: "Construction",
  completion: "Completion",
  post_completion: "Post-Completion",
};

export const COST_CATEGORY_OPTIONS: { value: CostCategory; label: string }[] =
  (Object.entries(COST_CATEGORY_LABELS) as [CostCategory, string][]).map(
    ([value, label]) => ({ value, label }),
  );

export const COST_SOURCE_OPTIONS: { value: CostSource; label: string }[] = (
  Object.entries(COST_SOURCE_LABELS) as [CostSource, string][]
).map(([value, label]) => ({ value, label }));

export const COST_STAGE_OPTIONS: { value: CostStage; label: string }[] = (
  Object.entries(COST_STAGE_LABELS) as [CostStage, string][]
).map(([value, label]) => ({ value, label }));

// ---------------------------------------------------------------------------
// ConstructionCostRecord
// ---------------------------------------------------------------------------

/** Mirrors ConstructionCostRecordCreate */
export interface ConstructionCostRecordCreate {
  title: string;
  cost_category?: CostCategory;
  cost_source?: CostSource;
  cost_stage?: CostStage;
  amount: number;
  currency?: string;
  effective_date?: string | null;
  reference_number?: string | null;
  notes?: string | null;
  is_active?: boolean;
}

/** Mirrors ConstructionCostRecordUpdate (all fields optional) */
export interface ConstructionCostRecordUpdate {
  title?: string;
  cost_category?: CostCategory;
  cost_source?: CostSource;
  cost_stage?: CostStage;
  amount?: number;
  currency?: string;
  effective_date?: string | null;
  reference_number?: string | null;
  notes?: string | null;
  is_active?: boolean;
}

/** Mirrors ConstructionCostRecordResponse */
export interface ConstructionCostRecord {
  id: string;
  project_id: string;
  title: string;
  cost_category: CostCategory;
  cost_source: CostSource;
  cost_stage: CostStage;
  amount: number;
  currency: string;
  effective_date: string | null;
  reference_number: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Mirrors ConstructionCostRecordList */
export interface ConstructionCostRecordList {
  total: number;
  items: ConstructionCostRecord[];
}

/** Mirrors the summary dict returned by the /summary endpoint */
export interface ConstructionCostSummary {
  project_id: string;
  active_record_count: number;
  grand_total: string;
  by_category: Record<string, string>;
  by_stage: Record<string, string>;
}
