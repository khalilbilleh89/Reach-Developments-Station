/**
 * phasing-optimization-types.ts — TypeScript types for the Phasing
 * Optimization Engine endpoints (PR-V7-03).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/phasing-recommendations
 *   GET /api/v1/portfolio/phasing-insights
 */

// ---------------------------------------------------------------------------
// Project-level phasing recommendations
// ---------------------------------------------------------------------------

export type CurrentPhaseRecommendation =
  | "release_more_inventory"
  | "maintain_current_release"
  | "hold_current_inventory"
  | "delay_further_release"
  | "insufficient_data";

export type NextPhaseRecommendation =
  | "prepare_next_phase"
  | "do_not_open_next_phase"
  | "defer_next_phase"
  | "not_applicable"
  | "insufficient_data";

export type ReleaseUrgency = "high" | "medium" | "low" | "none";

export type AbsorptionStatus = "high_demand" | "balanced" | "low_demand" | "no_data";

export interface ProjectPhasingRecommendationResponse {
  project_id: string;
  project_name: string;
  current_phase_id: string | null;
  current_phase_name: string | null;
  current_phase_recommendation: CurrentPhaseRecommendation;
  next_phase_recommendation: NextPhaseRecommendation;
  release_urgency: ReleaseUrgency;
  confidence: "high" | "medium" | "low";
  reason: string;
  sold_units: number;
  available_units: number;
  sell_through_pct: number | null;
  absorption_status: AbsorptionStatus;
  has_next_phase: boolean;
  next_phase_id: string | null;
  next_phase_name: string | null;
}

// ---------------------------------------------------------------------------
// Portfolio phasing insights
// ---------------------------------------------------------------------------

export interface PortfolioPhasingProjectCard {
  project_id: string;
  project_name: string;
  current_phase_recommendation: CurrentPhaseRecommendation;
  next_phase_recommendation: NextPhaseRecommendation;
  release_urgency: ReleaseUrgency;
  confidence: "high" | "medium" | "low";
  sell_through_pct: number | null;
  absorption_status: AbsorptionStatus;
  has_next_phase: boolean;
}

export interface PortfolioPhasingInsightsSummary {
  total_projects: number;
  projects_prepare_next_phase_count: number;
  projects_hold_inventory_count: number;
  projects_delay_release_count: number;
  projects_insufficient_data_count: number;
}

export interface PortfolioPhasingInsightsResponse {
  summary: PortfolioPhasingInsightsSummary;
  projects: PortfolioPhasingProjectCard[];
  top_phase_opportunities: PortfolioPhasingProjectCard[];
  top_release_risks: PortfolioPhasingProjectCard[];
}
