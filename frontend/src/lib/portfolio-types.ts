/**
 * portfolio-types.ts — Frontend TypeScript contracts for the Portfolio
 * Intelligence dashboard.
 *
 * These types mirror the backend Pydantic schemas in
 * app/modules/portfolio/schemas.py exactly. All fields use snake_case to
 * match the raw backend JSON — no mapping is performed in the API client
 * because the portfolio endpoint is read-only and the contract is stable.
 *
 * No portfolio calculations are performed using these types — they are
 * display models only.
 */

// ---------- String union types for fixed backend enum values -------------

/** Health indicator derived from project sell-through and collections data. */
export type PortfolioHealthBadge = "on_track" | "needs_attention" | "at_risk";

/** Risk flag severity level. */
export type PortfolioRiskSeverity = "warning" | "critical";

/** Machine-readable risk flag category. */
export type PortfolioRiskFlagType =
  | "overdue_receivables"
  | "low_sell_through"
  | "low_collections";

// ---------- Top-level KPI summary ----------------------------------------

export interface PortfolioSummary {
  total_projects: number;
  active_projects: number;
  total_units: number;
  available_units: number;
  reserved_units: number;
  under_contract_units: number;
  registered_units: number;
  contracted_revenue: number;
  collected_cash: number;
  outstanding_balance: number;
}

// ---------- Per-project snapshot card ------------------------------------

export interface PortfolioProjectCard {
  project_id: string;
  project_name: string;
  project_code: string;
  status: string;
  total_units: number;
  available_units: number;
  reserved_units: number;
  under_contract_units: number;
  registered_units: number;
  contracted_revenue: number;
  collected_cash: number;
  outstanding_balance: number;
  /** Percentage of units sold; null when total_units is zero */
  sell_through_pct: number | null;
  /** Backend-derived health indicator; null when insufficient data */
  health_badge: PortfolioHealthBadge | null;
}

// ---------- Scenario / feasibility pipeline signals ----------------------

export interface PortfolioPipelineSummary {
  total_scenarios: number;
  approved_scenarios: number;
  total_feasibility_runs: number;
  calculated_feasibility_runs: number;
  projects_with_no_feasibility: number;
}

// ---------- Collections health overview ----------------------------------

export interface PortfolioCollectionsSummary {
  total_receivables: number;
  overdue_receivables: number;
  overdue_balance: number;
  /** Collection rate as a percentage; null when no receivables exist */
  collection_rate_pct: number | null;
}

// ---------- Individual risk / alert signal --------------------------------

export interface PortfolioRiskFlag {
  flag_type: PortfolioRiskFlagType;
  severity: PortfolioRiskSeverity;
  description: string;
  affected_project_id: string | null;
  affected_project_name: string | null;
}

// ---------- Top-level dashboard response envelope ------------------------

export interface PortfolioDashboardResponse {
  summary: PortfolioSummary;
  projects: PortfolioProjectCard[];
  pipeline: PortfolioPipelineSummary;
  collections: PortfolioCollectionsSummary;
  risk_flags: PortfolioRiskFlag[];
}
