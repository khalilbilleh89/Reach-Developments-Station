/**
 * release-simulation-types.ts — TypeScript types for the Release Strategy
 * Simulation Engine endpoints (PR-V7-04).
 *
 * Backend endpoints:
 *   POST /api/v1/projects/{id}/simulate-strategy
 *   POST /api/v1/projects/{id}/simulate-strategies
 */

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

export type ReleaseStrategy = "hold" | "accelerate" | "maintain";

export type RiskScore = "low" | "medium" | "high";

export interface SimulationScenarioInput {
  price_adjustment_pct: number;
  phase_delay_months: number;
  release_strategy: ReleaseStrategy;
  label?: string | null;
}

// ---------------------------------------------------------------------------
// Single-scenario request / response
// ---------------------------------------------------------------------------

export interface SimulateStrategyRequest {
  scenario: SimulationScenarioInput;
}

export interface SimulationResult {
  label: string | null;
  price_adjustment_pct: number;
  phase_delay_months: number;
  release_strategy: ReleaseStrategy;
  simulated_gdv: number;
  simulated_dev_period_months: number;
  irr: number;
  irr_delta: number | null;
  npv: number;
  cashflow_delay_months: number;
  risk_score: RiskScore;
  baseline_gdv: number | null;
  baseline_irr: number | null;
  baseline_dev_period_months: number | null;
  baseline_total_cost: number | null;
}

export interface SimulateStrategyResponse {
  project_id: string;
  project_name: string;
  has_feasibility_baseline: boolean;
  result: SimulationResult;
}

// ---------------------------------------------------------------------------
// Multi-scenario request / response
// ---------------------------------------------------------------------------

export interface SimulateStrategiesRequest {
  scenarios: SimulationScenarioInput[];
}

export interface SimulateStrategiesResponse {
  project_id: string;
  project_name: string;
  has_feasibility_baseline: boolean;
  results: SimulationResult[];
  best_scenario_label: string | null;
}
