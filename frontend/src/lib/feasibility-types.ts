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
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// Result types
// ---------------------------------------------------------------------------

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
  profit_margin: number | null;
  irr_estimate: number | null;
  irr: number | null;
  equity_multiple: number | null;
  break_even_price: number | null;
  break_even_units: number | null;
  scenario_outputs: Record<string, unknown> | null;
  viability_status: FeasibilityViabilityStatus | null;
  risk_level: FeasibilityRiskLevel | null;
  decision: FeasibilityDecision | null;
  payback_period: number | null;
  created_at: string;
  updated_at: string;
}
