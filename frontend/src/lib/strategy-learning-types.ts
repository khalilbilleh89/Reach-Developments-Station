/**
 * strategy-learning-types.ts — TypeScript types for the Strategy Learning
 * & Confidence Recalibration Engine endpoints (PR-V7-11).
 *
 * Backend endpoints:
 *   POST /api/v1/projects/{id}/strategy-learning/recalibrate
 *   GET  /api/v1/projects/{id}/strategy-learning
 *   GET  /api/v1/portfolio/strategy-learning
 */

// ---------------------------------------------------------------------------
// Classification literals
// ---------------------------------------------------------------------------

export type TrendDirection =
  | "improving"
  | "declining"
  | "stable"
  | "insufficient_data";

// ---------------------------------------------------------------------------
// Sub-types
// ---------------------------------------------------------------------------

export interface AccuracyBreakdown {
  /** Fraction of outcomes where price adjustment matched. Null if no data. */
  pricing_accuracy_score: number | null;
  /** Fraction of outcomes where phase delay matched. Null if no data. */
  phasing_accuracy_score: number | null;
  /** Fraction of outcomes classified as 'matched_strategy'. */
  overall_strategy_accuracy: number;
}

export interface StrategyLearningMetricsResponse {
  id: string;
  project_id: string;
  /** Strategy type label, e.g. 'maintain', 'accelerate', 'hold', '_all_'. */
  strategy_type: string;
  sample_size: number;
  match_rate: number;
  partial_rate: number;
  divergence_rate: number;
  /** Composite confidence score in [0, 1]. Capped at 0.5 when sample_size < 5. */
  confidence_score: number;
  accuracy_breakdown: AccuracyBreakdown;
  trend_direction: TrendDirection;
  last_updated: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Project-level response
// ---------------------------------------------------------------------------

export interface StrategyLearningResponse {
  project_id: string;
  /** True when at least one recorded outcome exists for this project. */
  has_sufficient_data: boolean;
  /** Project-wide aggregate metrics (strategy_type='_all_'). Null when no data. */
  overall_metrics: StrategyLearningMetricsResponse | null;
  /** Per-strategy-type metrics rows (excluding the '_all_' aggregate). */
  strategy_breakdowns: StrategyLearningMetricsResponse[];
}

// ---------------------------------------------------------------------------
// Portfolio-level response
// ---------------------------------------------------------------------------

export interface PortfolioLearningProjectEntry {
  project_id: string;
  project_name: string;
  confidence_score: number;
  sample_size: number;
  trend_direction: TrendDirection;
  overall_strategy_accuracy: number;
}

export interface PortfolioLearningSummaryResponse {
  /** Number of projects with at least one recorded outcome. */
  total_projects_with_data: number;
  /** Mean confidence across all projects with data. Null when no data. */
  average_confidence_score: number | null;
  /** Projects with confidence_score >= 0.7. */
  high_confidence_count: number;
  /** Projects with confidence_score < 0.4. */
  low_confidence_count: number;
  /** Projects with trend_direction='improving'. */
  improving_count: number;
  /** Projects with trend_direction='declining'. */
  declining_count: number;
  /** Top 5 projects by confidence score (sample_size >= 2 only). */
  top_performing_projects: PortfolioLearningProjectEntry[];
  /** Up to 5 weakest projects (confidence < 0.5, sample_size >= 2). */
  weak_area_projects: PortfolioLearningProjectEntry[];
  /** All projects with learning data, ordered by confidence descending. */
  all_project_entries: PortfolioLearningProjectEntry[];
}
