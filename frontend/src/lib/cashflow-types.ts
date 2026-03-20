/**
 * cashflow-types.ts — TypeScript types for the Cashflow Forecasting domain.
 *
 * These types mirror the Pydantic schemas defined in
 * app/modules/cashflow/schemas.py and the enumerations in
 * app/shared/enums/cashflow.py.
 *
 * CashflowForecastBasis values:
 *   "scheduled_collections" | "actual_plus_scheduled" | "blended"
 *
 * CashflowForecastStatus values:
 *   "draft" | "generated" | "archived"
 *
 * CashflowPeriodType values:
 *   "monthly" | "quarterly"
 */

// ---------------------------------------------------------------------------
// Enum-like string literals
// ---------------------------------------------------------------------------

/** Mirrors CashflowForecastBasis enum from app/shared/enums/cashflow.py */
export type CashflowForecastBasis =
  | "scheduled_collections"
  | "actual_plus_scheduled"
  | "blended";

/** Mirrors CashflowForecastStatus enum from app/shared/enums/cashflow.py */
export type CashflowForecastStatus = "draft" | "generated" | "archived";

/** Mirrors CashflowPeriodType enum from app/shared/enums/cashflow.py */
export type CashflowPeriodType = "monthly" | "quarterly";

// ---------------------------------------------------------------------------
// CashflowForecast
// ---------------------------------------------------------------------------

/** Mirrors CashflowForecastResponse */
export interface CashflowForecast {
  id: string;
  project_id: string;
  forecast_name: string;
  forecast_basis: CashflowForecastBasis;
  start_date: string;
  end_date: string;
  period_type: CashflowPeriodType;
  status: CashflowForecastStatus;
  opening_balance: number;
  collection_factor: number | null;
  assumptions_json: string | null;
  generated_at: string | null;
  generated_by: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/** Mirrors CashflowForecastListResponse */
export interface CashflowForecastList {
  total: number;
  items: CashflowForecast[];
}

// ---------------------------------------------------------------------------
// CashflowForecastPeriod
// ---------------------------------------------------------------------------

/** Mirrors CashflowForecastPeriodResponse */
export interface CashflowForecastPeriod {
  id: string;
  cashflow_forecast_id: string;
  sequence: number;
  period_start: string;
  period_end: string;
  opening_balance: number;
  expected_inflows: number;
  actual_inflows: number;
  expected_outflows: number;
  net_cashflow: number;
  closing_balance: number;
  receivables_due: number;
  receivables_overdue: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// CashflowSummary
// ---------------------------------------------------------------------------

/** Mirrors CashflowForecastSummaryResponse */
export interface CashflowSummary {
  project_id: string;
  total_forecasts: number;
  latest_forecast_id: string | null;
  latest_forecast_name: string | null;
  latest_generated_at: string | null;
  total_expected_inflows: number;
  total_actual_inflows: number;
  total_expected_outflows: number;
  total_net_cashflow: number;
  closing_balance: number;
}
