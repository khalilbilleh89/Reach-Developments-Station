/**
 * portfolio-absorption-types.ts — TypeScript types for the Portfolio
 * Absorption endpoint (PR-V7-01).
 */

export interface PortfolioAbsorptionProjectCard {
  project_id: string;
  project_name: string;
  project_code: string;
  total_units: number;
  sold_units: number;
  sell_through_pct: number | null;
  absorption_rate_per_month: number | null;
  planned_absorption_rate_per_month: number | null;
  absorption_vs_plan_pct: number | null;
  contracted_revenue: number;
  absorption_status: "ahead_of_plan" | "on_plan" | "behind_plan" | "no_data" | null;
}

export interface PortfolioAbsorptionSummary {
  total_projects: number;
  projects_with_absorption_data: number;
  portfolio_avg_sell_through_pct: number | null;
  portfolio_avg_absorption_rate: number | null;
  projects_ahead_of_plan: number;
  projects_on_plan: number;
  projects_behind_plan: number;
  projects_no_absorption_data: number;
}

export interface PortfolioAbsorptionResponse {
  summary: PortfolioAbsorptionSummary;
  projects: PortfolioAbsorptionProjectCard[];
  fastest_projects: PortfolioAbsorptionProjectCard[];
  slowest_projects: PortfolioAbsorptionProjectCard[];
  below_plan_projects: PortfolioAbsorptionProjectCard[];
}
