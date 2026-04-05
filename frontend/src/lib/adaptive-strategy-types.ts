/**
 * adaptive-strategy-types.ts — TypeScript types for the Adaptive Strategy
 * Influence Layer endpoints (PR-V7-12).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/adaptive-strategy
 *   GET /api/v1/portfolio/adaptive-strategy
 */

// ---------------------------------------------------------------------------
// Classification literals
// ---------------------------------------------------------------------------

export type ConfidenceBand = "high" | "medium" | "low" | "insufficient";

// ---------------------------------------------------------------------------
// Comparison block
// ---------------------------------------------------------------------------

export interface AdaptiveStrategyComparisonBlock {
  /** IRR of the raw simulation-best strategy. */
  raw_irr: number | null;
  /** IRR of the confidence-adjusted best strategy. */
  adaptive_irr: number | null;
  /** Risk score of the raw best strategy: 'low' | 'medium' | 'high'. */
  raw_risk_score: string | null;
  /** Risk score of the confidence-adjusted best strategy. */
  adaptive_risk_score: string | null;
  /** Release strategy of the raw best: 'hold' | 'maintain' | 'accelerate'. */
  raw_release_strategy: string | null;
  /** Release strategy of the confidence-adjusted best. */
  adaptive_release_strategy: string | null;
  /** Price adjustment % of the raw best strategy. */
  raw_price_adjustment_pct: number | null;
  /** Price adjustment % of the confidence-adjusted best strategy. */
  adaptive_price_adjustment_pct: number | null;
  /** Phase delay months of the raw best strategy. */
  raw_phase_delay_months: number | null;
  /** Phase delay months of the confidence-adjusted best strategy. */
  adaptive_phase_delay_months: number | null;
  /** True when the confidence-adjusted best differs from the raw best. */
  changed_by_confidence: boolean;
}

// ---------------------------------------------------------------------------
// Project-level response
// ---------------------------------------------------------------------------

export interface AdaptiveStrategyResponse {
  project_id: string;
  project_name: string;

  /** Release strategy label of the raw simulation-best scenario. */
  raw_best_strategy: string | null;
  raw_best_irr: number | null;
  raw_best_risk_score: string | null;
  raw_best_price_adjustment_pct: number | null;
  raw_best_phase_delay_months: number | null;

  /** Release strategy label of the confidence-adjusted best scenario. */
  adaptive_best_strategy: string | null;
  adaptive_best_irr: number | null;
  adaptive_best_risk_score: string | null;
  adaptive_best_price_adjustment_pct: number | null;
  adaptive_best_phase_delay_months: number | null;

  /** Project-wide learning confidence score in [0, 1]. Null when no metrics exist. */
  confidence_score: number | null;
  /** Confidence band: 'high' | 'medium' | 'low' | 'insufficient'. */
  confidence_band: ConfidenceBand;
  /** True when a non-neutral confidence signal was applied to influence ranking. */
  confidence_influence_applied: boolean;
  /** True when confidence band is 'low' or 'insufficient'. */
  low_confidence_flag: boolean;
  /** Number of recorded outcomes contributing to the confidence score. */
  sample_size: number;
  /** Direction of confidence change. */
  trend_direction: string;
  /** Human-readable explanation of how confidence influenced the selection. */
  adjusted_reason: string;

  /** Side-by-side raw vs adaptive comparison block. */
  comparison: AdaptiveStrategyComparisonBlock;
}

// ---------------------------------------------------------------------------
// Portfolio-level response
// ---------------------------------------------------------------------------

export interface PortfolioAdaptiveStrategyProjectCard {
  project_id: string;
  project_name: string;
  raw_best_strategy: string | null;
  adaptive_best_strategy: string | null;
  confidence_score: number | null;
  confidence_band: ConfidenceBand;
  confidence_influence_applied: boolean;
  low_confidence_flag: boolean;
  sample_size: number;
  trend_direction: string;
  adjusted_reason: string;
}

export interface PortfolioAdaptiveStrategySummaryResponse {
  /** Total number of projects evaluated. */
  total_projects: number;
  /** Projects with confidence_band == 'high'. */
  high_confidence_projects: number;
  /** Projects with confidence_band == 'low' or 'insufficient'. */
  low_confidence_projects: number;
  /** Projects where confidence influence changed the recommendation. */
  confidence_adjusted_projects: number;
  /** Projects where confidence was neutral (no shift). */
  neutral_projects: number;
  /** Top 5 projects by confidence_score descending. */
  top_confident_recommendations: PortfolioAdaptiveStrategyProjectCard[];
  /** Up to 5 low-confidence projects requiring attention. */
  top_low_confidence_projects: PortfolioAdaptiveStrategyProjectCard[];
  /** All project cards ordered by confidence_score descending. */
  project_cards: PortfolioAdaptiveStrategyProjectCard[];
}
