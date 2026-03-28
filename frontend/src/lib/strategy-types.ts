/**
 * strategy-types.ts — TypeScript types for the Automated Strategy Generator
 * endpoints (PR-V7-05).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/recommended-strategy
 *   GET /api/v1/portfolio/strategy-insights
 */

import type { SimulationResult } from "./release-simulation-types";

// ---------------------------------------------------------------------------
// Project-level recommended strategy
// ---------------------------------------------------------------------------

export interface RecommendedStrategyResponse {
  project_id: string;
  project_name: string;
  has_feasibility_baseline: boolean;
  best_strategy: SimulationResult | null;
  top_strategies: SimulationResult[];
  reason: string;
  generated_scenario_count: number;
}

// ---------------------------------------------------------------------------
// Portfolio strategy insights
// ---------------------------------------------------------------------------

export interface PortfolioStrategyProjectCard {
  project_id: string;
  project_name: string;
  has_feasibility_baseline: boolean;
  best_irr: number | null;
  best_risk_score: "low" | "medium" | "high" | null;
  best_release_strategy: "hold" | "maintain" | "accelerate" | null;
  best_price_adjustment_pct: number | null;
  best_phase_delay_months: number | null;
  reason: string;
}

export interface PortfolioStrategyInsightsSummary {
  total_projects: number;
  projects_with_baseline: number;
  projects_high_risk: number;
  projects_low_risk: number;
}

export interface PortfolioStrategyInsightsResponse {
  summary: PortfolioStrategyInsightsSummary;
  projects: PortfolioStrategyProjectCard[];
  top_strategies: PortfolioStrategyProjectCard[];
  intervention_required: PortfolioStrategyProjectCard[];
}
