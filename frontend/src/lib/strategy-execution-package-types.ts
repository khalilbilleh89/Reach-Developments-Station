/**
 * strategy-execution-package-types.ts — TypeScript types for the Strategy
 * Execution Package Generator endpoints (PR-V7-07).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/strategy-execution-package
 *   GET /api/v1/portfolio/execution-packages
 */

// ---------------------------------------------------------------------------
// Classification literals
// ---------------------------------------------------------------------------

export type ExecutionReadiness =
  | "ready_for_review"
  | "blocked_by_dependency"
  | "caution_required"
  | "insufficient_data";

export type ActionType =
  | "baseline_dependency_review"
  | "simulation_review"
  | "pricing_update_preparation"
  | "phase_release_preparation"
  | "holdback_validation"
  | "executive_review";

export type DependencyStatus = "cleared" | "blocked";

export type CautionSeverity = "high" | "medium" | "low";

// ---------------------------------------------------------------------------
// Action item
// ---------------------------------------------------------------------------

export interface StrategyExecutionActionItem {
  step_number: number;
  action_type: ActionType;
  action_title: string;
  action_description: string;
  target_area: string;
  urgency: string;
  depends_on: string | null;
  review_required: boolean;
}

// ---------------------------------------------------------------------------
// Dependency item
// ---------------------------------------------------------------------------

export interface StrategyExecutionDependencyItem {
  dependency_type: string;
  dependency_label: string;
  dependency_status: DependencyStatus;
  blocking_reason: string | null;
}

// ---------------------------------------------------------------------------
// Caution item
// ---------------------------------------------------------------------------

export interface StrategyExecutionCautionItem {
  severity: CautionSeverity;
  caution_title: string;
  caution_description: string;
}

// ---------------------------------------------------------------------------
// Supporting metrics
// ---------------------------------------------------------------------------

export interface StrategyExecutionSupportingMetrics {
  best_irr: number | null;
  risk_score: "low" | "medium" | "high" | null;
  price_adjustment_pct: number | null;
  phase_delay_months: number | null;
  release_strategy: "hold" | "maintain" | "accelerate" | null;
}

// ---------------------------------------------------------------------------
// Project-level execution package
// ---------------------------------------------------------------------------

export interface ProjectStrategyExecutionPackageResponse {
  project_id: string;
  project_name: string;
  has_feasibility_baseline: boolean;
  recommended_strategy: "hold" | "maintain" | "accelerate" | null;
  execution_readiness: ExecutionReadiness;
  summary: string;
  actions: StrategyExecutionActionItem[];
  dependencies: StrategyExecutionDependencyItem[];
  cautions: StrategyExecutionCautionItem[];
  supporting_metrics: StrategyExecutionSupportingMetrics;
  expected_impact: string;
  requires_manual_review: boolean;
}

// ---------------------------------------------------------------------------
// Portfolio packaged intervention card
// ---------------------------------------------------------------------------

export interface PortfolioPackagedInterventionCard {
  project_id: string;
  project_name: string;
  recommended_strategy: "hold" | "maintain" | "accelerate" | null;
  intervention_priority: string;
  intervention_type: string;
  execution_readiness: ExecutionReadiness;
  has_feasibility_baseline: boolean;
  requires_manual_review: boolean;
  next_best_action: string | null;
  blockers: string[];
  urgency_score: number;
  expected_impact: string;
}

// ---------------------------------------------------------------------------
// Portfolio summary KPIs
// ---------------------------------------------------------------------------

export interface PortfolioExecutionPackageSummary {
  total_projects: number;
  ready_for_review_count: number;
  blocked_count: number;
  caution_required_count: number;
  insufficient_data_count: number;
}

// ---------------------------------------------------------------------------
// Portfolio execution packages response
// ---------------------------------------------------------------------------

export interface PortfolioExecutionPackageResponse {
  summary: PortfolioExecutionPackageSummary;
  top_ready_actions: PortfolioPackagedInterventionCard[];
  top_blocked_actions: PortfolioPackagedInterventionCard[];
  top_high_risk_packages: PortfolioPackagedInterventionCard[];
  packages: PortfolioPackagedInterventionCard[];
}
