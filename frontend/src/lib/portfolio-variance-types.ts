/**
 * portfolio-variance-types.ts — Frontend TypeScript contracts for the
 * Portfolio Cost Variance roll-up (PR-V6-12).
 *
 * These types mirror the backend Pydantic schemas in
 * app/modules/portfolio/schemas.py exactly (PortfolioCostVariance* family).
 * All fields use snake_case to match the raw backend JSON — no mapping is
 * performed in the API client.
 *
 * No variance calculations are performed using these types — they are
 * display models only.
 */

// ---------- String union types for fixed backend enum values -------------

/**
 * Transparent variance status derived from variance_amount sign.
 *   'overrun'  → variance_amount > 0
 *   'saving'   → variance_amount < 0
 *   'neutral'  → variance_amount == 0
 */
export type PortfolioVarianceStatus = "overrun" | "saving" | "neutral";

/**
 * Machine-readable cost variance flag type.
 *   'major_overrun'          → project variance_pct exceeds overrun threshold
 *   'major_saving'           → project variance_pct exceeds saving threshold
 *   'missing_comparison_data' → project has no active tender comparison sets
 */
export type PortfolioCostVarianceFlagType =
  | "major_overrun"
  | "major_saving"
  | "missing_comparison_data";

// ---------- Portfolio-wide cost variance summary -------------------------

export interface PortfolioCostVarianceSummary {
  /** Number of projects with at least one active comparison set */
  projects_with_comparison_sets: number;
  /** Sum of all baseline amounts across active comparison lines (AED) */
  total_baseline_amount: number;
  /** Sum of all comparison amounts across active comparison lines (AED) */
  total_comparison_amount: number;
  /**
   * Total variance (comparison - baseline) across active lines (AED).
   * Positive → net overrun; negative → net saving.
   */
  total_variance_amount: number;
  /** Total variance as percentage of total baseline; null when baseline is zero */
  total_variance_pct: number | null;
}

// ---------- Per-project cost variance card --------------------------------

export interface PortfolioCostVarianceProjectCard {
  project_id: string;
  project_name: string;
  /** Number of active comparison sets for this project */
  comparison_set_count: number;
  /** Stage of the most recently created active comparison set; null if none */
  latest_comparison_stage: string | null;
  /** Sum of baseline amounts across all active comparison lines (AED) */
  baseline_total: number;
  /** Sum of comparison amounts across all active comparison lines (AED) */
  comparison_total: number;
  /**
   * Net variance (comparison - baseline) across all active lines (AED).
   * Positive → overrun; negative → saving.
   */
  variance_amount: number;
  /** Variance as percentage of baseline; null when baseline is zero */
  variance_pct: number | null;
  /** Backend-derived status label: 'overrun' | 'saving' | 'neutral' */
  variance_status: PortfolioVarianceStatus;
}

// ---------- Portfolio-level cost variance flag ----------------------------

export interface PortfolioCostVarianceFlag {
  flag_type: PortfolioCostVarianceFlagType;
  description: string;
  /** Project ID if project-scoped; null for portfolio-wide flags */
  affected_project_id: string | null;
  /** Project name if project-scoped; null for portfolio-wide flags */
  affected_project_name: string | null;
}

// ---------- Top-level cost variance response envelope --------------------

export interface PortfolioCostVarianceResponse {
  summary: PortfolioCostVarianceSummary;
  /** All projects with active comparison sets, ordered by variance_amount descending */
  projects: PortfolioCostVarianceProjectCard[];
  /** Projects with the largest positive variance (overruns), top-N */
  top_overruns: PortfolioCostVarianceProjectCard[];
  /** Projects with the largest negative variance (savings), top-N */
  top_savings: PortfolioCostVarianceProjectCard[];
  /** Portfolio-level cost variance signals */
  flags: PortfolioCostVarianceFlag[];
}
