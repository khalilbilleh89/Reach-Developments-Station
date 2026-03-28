/**
 * absorption-types.ts — TypeScript types for the Project Absorption Metrics
 * endpoint (PR-V7-01).
 *
 * All fields are backend-owned and sourced from live sales/feasibility data.
 * No values are recomputed in the frontend.
 */

export interface ProjectAbsorptionMetrics {
  project_id: string;
  project_name: string;
  project_code: string;

  // Inventory counts
  total_units: number;
  sold_units: number;
  reserved_units: number;
  available_units: number;

  // Absorption velocity
  absorption_rate_per_month: number | null;
  planned_absorption_rate_per_month: number | null;
  absorption_vs_plan_pct: number | null;
  avg_selling_time_days: number | null;

  // Revenue
  contracted_revenue: number;
  projected_revenue: number | null;
  revenue_realized_pct: number | null;

  // IRR comparison
  planned_irr: number | null;
  actual_irr_estimate: number | null;
  irr_delta: number | null;

  // Cashflow timing
  cashflow_delay_months: number | null;
  revenue_timing_note: string;
}
