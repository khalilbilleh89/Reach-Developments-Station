/**
 * construction-scorecard-types.ts — TypeScript contracts for the
 * Construction Analytics & Project Scorecard layer (PR-V6-14).
 *
 * These types mirror the backend Pydantic schemas in
 * app/modules/construction_costs/analytics_schemas.py.
 * All fields use snake_case to match the raw backend JSON.
 *
 * Health status values (backend-owned, never re-derived on the client):
 *   "healthy"    — all metrics within acceptable thresholds
 *   "warning"    — one or more metrics exceed warning thresholds
 *   "critical"   — one or more metrics exceed critical thresholds
 *   "incomplete" — no approved baseline exists
 *
 * Monetary Decimal fields are returned as strings by FastAPI.
 */

// ---------------------------------------------------------------------------
// Health status type
// ---------------------------------------------------------------------------

export type ConstructionHealthStatus =
  | "healthy"
  | "warning"
  | "critical"
  | "incomplete";

// ---------------------------------------------------------------------------
// Project-level scorecard
// ---------------------------------------------------------------------------

export interface ConstructionProjectScorecard {
  project_id: string;
  project_name: string;

  /** True when an approved tender baseline exists for this project */
  has_approved_baseline: boolean;
  /** ID of the approved baseline comparison set; null when none */
  approved_baseline_set_id: string | null;
  /**
   * Total comparison amount from the approved baseline set lines (AED).
   * Decimal serialised as string. Null when has_approved_baseline is false.
   */
  approved_baseline_amount: string | null;
  /** ISO 8601 timestamp when the baseline was approved; null when none */
  approved_at: string | null;

  /**
   * Sum of all active construction cost records for this project (AED).
   * Decimal serialised as string.
   */
  current_forecast_amount: string;

  /**
   * Absolute cost variance (current_forecast - approved_baseline) (AED).
   * Decimal serialised as string. Positive → overrun; negative → saving.
   * Null when has_approved_baseline is false.
   */
  cost_variance_amount: string | null;
  /**
   * Cost variance as percentage of approved_baseline_amount.
   * Decimal serialised as string. Null when baseline is zero or missing.
   */
  cost_variance_pct: string | null;
  cost_status: ConstructionHealthStatus;

  /**
   * Sum of active construction cost records with category 'contingency' (AED).
   * Decimal serialised as string.
   */
  contingency_amount: string;
  /**
   * Contingency amount as percentage of approved_baseline_amount.
   * Decimal serialised as string. Null when baseline is zero or missing.
   */
  contingency_pressure_pct: string | null;
  contingency_status: ConstructionHealthStatus;

  overall_health_status: ConstructionHealthStatus;

  /** ISO 8601 timestamp of the most recent update from records or baseline */
  last_updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Portfolio-level scorecard item
// ---------------------------------------------------------------------------

export interface ConstructionPortfolioScorecardItem {
  project_id: string;
  project_name: string;
  has_approved_baseline: boolean;
  /** Decimal serialised as string; null when no approved baseline */
  approved_baseline_amount: string | null;
  /** Decimal serialised as string */
  current_forecast_amount: string;
  /** Decimal serialised as string; null when no approved baseline */
  cost_variance_amount: string | null;
  /** Decimal serialised as string; null when no approved baseline or zero baseline */
  cost_variance_pct: string | null;
  /** Decimal serialised as string */
  contingency_amount: string;
  /** Decimal serialised as string; null when no approved baseline or zero baseline */
  contingency_pressure_pct: string | null;
  overall_health_status: ConstructionHealthStatus;
}

// ---------------------------------------------------------------------------
// Portfolio construction scorecard summary
// ---------------------------------------------------------------------------

export interface ConstructionPortfolioScorecardSummary {
  total_projects_scored: number;
  healthy_count: number;
  warning_count: number;
  critical_count: number;
  incomplete_count: number;
  projects_missing_baseline: number;
}

// ---------------------------------------------------------------------------
// Top-level portfolio response
// ---------------------------------------------------------------------------

export interface ConstructionPortfolioScorecardsResponse {
  summary: ConstructionPortfolioScorecardSummary;
  /** All project scorecards ordered by severity then cost_variance_pct descending */
  projects: ConstructionPortfolioScorecardItem[];
  /** Critical + warning projects requiring executive attention */
  top_risk_projects: ConstructionPortfolioScorecardItem[];
  /** Projects that have no approved baseline */
  missing_baseline_projects: ConstructionPortfolioScorecardItem[];
}
