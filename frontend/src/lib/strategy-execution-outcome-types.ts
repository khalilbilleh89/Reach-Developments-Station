/**
 * strategy-execution-outcome-types.ts — TypeScript types for the Strategy
 * Execution Outcome module endpoints (PR-V7-10).
 *
 * Backend endpoints:
 *   POST /api/v1/execution-triggers/{id}/outcome
 *   GET  /api/v1/projects/{id}/strategy-execution-outcome
 *   GET  /api/v1/portfolio/execution-outcomes
 */

// ---------------------------------------------------------------------------
// Classification literals
// ---------------------------------------------------------------------------

export type OutcomeResult =
  | "matched_strategy"
  | "partially_matched"
  | "diverged"
  | "cancelled_execution"
  | "insufficient_data";

export type OutcomeStatus = "recorded" | "superseded";

export type MatchStatus =
  | "exact_match"
  | "minor_variance"
  | "major_variance"
  | "no_comparable_strategy";

export type ExecutionQuality = "high" | "medium" | "low" | "unknown";

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface RecordExecutionOutcomeRequest {
  actual_price_adjustment_pct?: number | null;
  actual_phase_delay_months?: number | null;
  actual_release_strategy?: string | null;
  execution_summary?: string | null;
  outcome_result: OutcomeResult;
  outcome_notes?: string | null;
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface ExecutionOutcomeComparisonBlock {
  intended_price_adjustment_pct: number | null;
  actual_price_adjustment_pct: number | null;
  intended_phase_delay_months: number | null;
  actual_phase_delay_months: number | null;
  intended_release_strategy: string | null;
  actual_release_strategy: string | null;
  match_status: MatchStatus;
  divergence_summary: string;
  execution_quality: ExecutionQuality;
  has_material_divergence: boolean;
}

export interface StrategyExecutionOutcomeResponse {
  id: string;
  project_id: string;
  execution_trigger_id: string | null;
  approval_id: string | null;
  status: OutcomeStatus;
  outcome_result: OutcomeResult;
  actual_price_adjustment_pct: number | null;
  actual_phase_delay_months: number | null;
  actual_release_strategy: string | null;
  execution_summary: string | null;
  outcome_notes: string | null;
  recorded_by_user_id: string;
  recorded_at: string;
  created_at: string;
  updated_at: string;
  comparison: ExecutionOutcomeComparisonBlock;
  has_material_divergence: boolean;
}

export interface ProjectExecutionOutcomeResponse {
  project_id: string;
  execution_trigger_id: string | null;
  trigger_status: string | null;
  outcome_eligible: boolean;
  latest_outcome: StrategyExecutionOutcomeResponse | null;
}

export interface PortfolioOutcomeEntry {
  project_id: string;
  project_name: string;
  outcome: StrategyExecutionOutcomeResponse;
}

export interface PortfolioOutcomeProjectEntry {
  project_id: string;
  project_name: string;
  trigger_id: string;
}

export interface PortfolioExecutionOutcomeSummaryResponse {
  matched_strategy_count: number;
  partially_matched_count: number;
  diverged_count: number;
  cancelled_execution_count: number;
  insufficient_data_count: number;
  awaiting_outcome_count: number;
  recent_outcomes: PortfolioOutcomeEntry[];
  awaiting_outcome_projects: PortfolioOutcomeProjectEntry[];
}
