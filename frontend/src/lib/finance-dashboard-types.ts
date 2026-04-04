/**
 * finance-dashboard-types.ts — shared types for the finance dashboard UI.
 *
 * These types model the data as consumed by finance dashboard components.
 * They are the normalized frontend representation of backend summary responses.
 * No financial calculations are performed using these types — they are
 * display models only.
 */

// ---------- Finance KPIs --------------------------------------------------

export interface FinanceKpis {
  total_contract_value: number;
  total_collected: number;
  total_receivable: number;
  collection_ratio: number;
  units_sold: number;
  total_units: number;
  average_unit_price: number;
  /**
   * ISO 4217 currency code for all monetary KPI values in this summary.
   * Sourced from the project base_currency.  Optional for backward
   * compatibility; callers should fall back to DEFAULT_CURRENCY when absent.
   */
  currency?: string;
}

// ---------- Collections health -------------------------------------------

export interface CollectionsHealth {
  total_collected: number;
  total_receivable: number;
  collection_ratio: number;
}

// ---------- Cashflow health -----------------------------------------------

export interface CashflowHealth {
  expected_inflows: number;
  expected_outflows: number;
  net_cashflow: number;
  closing_balance: number;
}

// ---------- Commission exposure ------------------------------------------

export interface CommissionExposure {
  total_payouts: number;
  /** Payouts in draft state (not yet submitted for calculation). */
  draft_payouts: number;
  /** Payouts calculated but not yet approved. */
  calculated_payouts: number;
  /** Payouts that have been approved and released. */
  approved_payouts: number;
  /** Payouts that have been cancelled — excluded from pending exposure. */
  cancelled_payouts: number;
  total_gross_value: number;
  total_commission_pool: number;
}

// ---------- Sales exception impact ---------------------------------------

export interface SalesExceptionImpact {
  total_exceptions: number;
  approved_exceptions: number;
  pending_exceptions: number;
  rejected_exceptions: number;
  total_discount_amount: number;
  total_incentive_value: number;
}

// ---------- Registration finance signal ----------------------------------

export interface RegistrationFinanceSignal {
  total_sold_units: number;
  registration_cases_completed: number;
  registration_cases_open: number;
  sold_not_registered: number;
  completion_ratio: number;
}

// ---------- Finance health state (presentational) -----------------------

export type FinanceHealthStatus = "healthy" | "watch" | "critical";

export interface FinanceHealthState {
  collections: FinanceHealthStatus;
  cashflow: FinanceHealthStatus;
  registration: FinanceHealthStatus;
  exceptions: FinanceHealthStatus;
}

// ---------- Aggregate dashboard data ------------------------------------

export interface FinanceDashboardData {
  kpis: FinanceKpis;
  collections: CollectionsHealth;
  cashflow: CashflowHealth;
  commission: CommissionExposure;
  exceptions: SalesExceptionImpact;
  registration: RegistrationFinanceSignal;
}
