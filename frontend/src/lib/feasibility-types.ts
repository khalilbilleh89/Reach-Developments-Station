/**
 * feasibility-types.ts — TypeScript types for the Feasibility domain.
 *
 * Mirrors the backend FeasibilityRunResponse, FeasibilityAssumptionsResponse,
 * and FeasibilityResultResponse Pydantic schemas.
 */

export type FeasibilityScenarioType = "base" | "upside" | "downside" | "investor";
export type FeasibilityViabilityStatus = "VIABLE" | "MARGINAL" | "NOT_VIABLE";
export type FeasibilityRiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type FeasibilityDecision = "VIABLE" | "MARGINAL" | "NOT_VIABLE";
// Lifecycle state — PR-FEAS-03
export type FeasibilityRunStatus = "draft" | "assumptions_defined" | "calculated";

// ---------------------------------------------------------------------------
// Run types
// ---------------------------------------------------------------------------

export interface FeasibilityRun {
  id: string;
  project_id: string | null;
  project_name: string | null;
  scenario_id: string | null;
  scenario_name: string;
  scenario_type: FeasibilityScenarioType;
  notes: string | null;
  // Lineage / seed-source metadata — PR-CONCEPT-063 / PR-FEAS-01
  source_concept_option_id: string | null;
  seed_source_type: "concept_option" | "manual" | null;
  // Lifecycle state — PR-FEAS-03
  status: FeasibilityRunStatus;
  created_at: string;
  updated_at: string;
}

export interface FeasibilityRunList {
  items: FeasibilityRun[];
  total: number;
}

export interface FeasibilityRunCreate {
  project_id?: string | null;
  scenario_name: string;
  scenario_type?: FeasibilityScenarioType;
  notes?: string | null;
}

export interface FeasibilityRunUpdate {
  project_id?: string | null;
  scenario_name?: string | null;
  scenario_type?: FeasibilityScenarioType | null;
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// Assumptions types
// ---------------------------------------------------------------------------

export interface FeasibilityAssumptions {
  id: string;
  run_id: string;
  sellable_area_sqm: number | null;
  avg_sale_price_per_sqm: number | null;
  construction_cost_per_sqm: number | null;
  soft_cost_ratio: number | null;
  finance_cost_ratio: number | null;
  sales_cost_ratio: number | null;
  development_period_months: number | null;
  /** ISO 4217 currency code for monetary input assumptions. */
  currency: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeasibilityAssumptionsCreate {
  sellable_area_sqm: number;
  avg_sale_price_per_sqm: number;
  construction_cost_per_sqm: number;
  soft_cost_ratio: number;
  finance_cost_ratio: number;
  sales_cost_ratio: number;
  development_period_months: number;
  /** ISO 4217 currency code. Defaults to "AED" when not supplied. */
  currency?: string;
  notes?: string | null;
}

export interface FeasibilityAssumptionsUpdate {
  sellable_area_sqm?: number | null;
  avg_sale_price_per_sqm?: number | null;
  construction_cost_per_sqm?: number | null;
  soft_cost_ratio?: number | null;
  finance_cost_ratio?: number | null;
  sales_cost_ratio?: number | null;
  development_period_months?: number | null;
  currency?: string | null;
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// Result types
// ---------------------------------------------------------------------------

/**
 * Per-scenario output metrics returned by the backend scenario runner.
 * Mirrors the dict produced by `_outputs_to_dict` in scenario_runner.py.
 */
export interface FeasibilityScenarioMetrics {
  gdv: number | null;
  construction_cost: number | null;
  soft_cost: number | null;
  finance_cost: number | null;
  sales_cost: number | null;
  total_cost: number | null;
  developer_profit: number | null;
  profit_margin: number | null;
  irr_estimate: number | null;
}

/**
 * Typed shape of the `scenario_outputs` field on FeasibilityResult.
 * Keys match the scenario names produced by `run_sensitivity_scenarios`:
 * base, upside, downside, investor.
 *
 * A key is present only when that scenario was included in the backend result.
 * When present, the value is always a FeasibilityScenarioMetrics object (never
 * null) — missing or non-numeric metric fields within it are coerced to null by
 * the normalizer.
 */
export interface FeasibilityScenarioOutputs {
  base?: FeasibilityScenarioMetrics;
  upside?: FeasibilityScenarioMetrics;
  downside?: FeasibilityScenarioMetrics;
  investor?: FeasibilityScenarioMetrics;
}

export interface FeasibilityResult {
  id: string;
  run_id: string;
  gdv: number | null;
  construction_cost: number | null;
  soft_cost: number | null;
  finance_cost: number | null;
  sales_cost: number | null;
  total_cost: number | null;
  developer_profit: number | null;
  /** ISO 4217 currency code for all monetary outputs in this result. */
  currency: string;
  profit_margin: number | null;
  irr_estimate: number | null;
  irr: number | null;
  equity_multiple: number | null;
  break_even_price: number | null;
  break_even_units: number | null;
  profit_per_sqm: number | null;
  scenario_outputs: FeasibilityScenarioOutputs | null;
  viability_status: FeasibilityViabilityStatus | null;
  risk_level: FeasibilityRiskLevel | null;
  decision: FeasibilityDecision | null;
  payback_period: number | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Lifecycle Lineage / Traceability types — PR-CONCEPT-065
// ---------------------------------------------------------------------------

export interface FeasibilityLineageResponse {
  record_type: "feasibility_run";
  record_id: string;
  source_concept_option_id: string | null;
  reverse_seeded_concept_options: string[];
  project_id: string | null;
}

// ---------------------------------------------------------------------------
// Construction cost context — PR-V6-10
// ---------------------------------------------------------------------------

/**
 * Read-only construction cost context for a feasibility run.
 *
 * Mirrors the backend FeasibilityConstructionCostContextResponse schema.
 * Decimal fields are serialised as strings by FastAPI.
 *
 * Fields are null-safe — partial data is reflected via nulls and the ``note``
 * field which is always present and explains the comparison state.
 */
export interface FeasibilityConstructionCostContext {
  feasibility_run_id: string;
  project_id: string | null;
  has_cost_records: boolean;
  active_record_count: number;
  /** Decimal → string from backend */
  recorded_construction_cost_total: string | null;
  /** Decimal values per category, serialised as strings */
  by_category: Record<string, string> | null;
  /** Decimal values per stage, serialised as strings */
  by_stage: Record<string, string> | null;
  /** construction_cost_per_sqm × sellable_area_sqm from feasibility assumptions */
  assumed_construction_cost: number | null;
  /** Decimal → string: recorded − assumed */
  variance_amount: string | null;
  /** (recorded − assumed) / assumed, null when assumed is zero or unavailable */
  variance_pct: number | null;
  /** Human-readable explanation of the comparison state */
  note: string;
}
