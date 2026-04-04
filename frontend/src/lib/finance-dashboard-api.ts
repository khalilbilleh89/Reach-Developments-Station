/**
 * finance-dashboard-api.ts — centralized API wrapper for the finance dashboard.
 *
 * Normalizes backend response contracts into the UI-friendly types defined in
 * finance-dashboard-types.ts. No financial calculations are performed here —
 * values are passed through or renamed for clarity.
 */

import { apiFetch } from "./api-client";
import type {
  FinanceKpis,
  CollectionsHealth,
  CashflowHealth,
  CommissionExposure,
  SalesExceptionImpact,
  RegistrationFinanceSignal,
} from "./finance-dashboard-types";

// ---------- Raw backend response types (internal) ------------------------

interface ProjectResponse {
  id: string;
  name: string;
  code: string;
  status: string;
}

interface ProjectListResponse {
  items: ProjectResponse[];
  total: number;
}

/** Raw backend: /finance/projects/{id}/summary */
interface BackendFinanceSummary {
  project_id: string;
  total_units: number;
  units_sold: number;
  units_available: number;
  total_contract_value: number;
  total_collected: number;
  total_receivable: number;
  collection_ratio: number;
  average_unit_price: number;
  /** ISO 4217 currency code for all monetary fields. Sourced from project base_currency. */
  currency?: string;
}

/** Raw backend: /cashflow/projects/{id}/cashflow-summary */
interface BackendCashflowSummary {
  project_id: string;
  total_forecasts: number;
  latest_forecast_id: string | null;
  latest_forecast_name: string | null;
  total_expected_inflows: number;
  total_actual_inflows: number;
  total_expected_outflows: number;
  total_net_cashflow: number;
  closing_balance: number;
}

/** Raw backend: /sales-exceptions/projects/{id}/summary */
interface BackendSalesExceptionsSummary {
  project_id: string;
  total_exceptions: number;
  pending_exceptions: number;
  approved_exceptions: number;
  rejected_exceptions: number;
  total_discount_amount: number;
  total_incentive_value: number;
}

/** Raw backend: /registry/projects/{id}/summary */
interface BackendRegistrationSummary {
  project_id: string;
  total_sold_units: number;
  registration_cases_open: number;
  registration_cases_completed: number;
  sold_not_registered: number;
  registration_completion_ratio: number;
}

/** Raw backend: /commission/projects/{id}/summary */
interface BackendCommissionSummary {
  project_id: string;
  total_payouts: number;
  draft_payouts: number;
  calculated_payouts: number;
  approved_payouts: number;
  cancelled_payouts: number;
  total_gross_value: number;
  total_commission_pool: number;
}

// ---------- Exported project type ----------------------------------------

export interface Project {
  id: string;
  name: string;
  code: string;
  status: string;
}

// ---------- Query functions ----------------------------------------------

/** Fetch project list; unwraps the paginated backend envelope. */
export async function getProjects(): Promise<Project[]> {
  const data = await apiFetch<ProjectListResponse>("/projects");
  return data.items.map((p) => ({
    id: p.id,
    name: p.name,
    code: p.code,
    status: p.status,
  }));
}

/**
 * Fetch project finance summary and return KPI and collections data.
 *
 * Backend endpoint: GET /finance/projects/{projectId}/summary
 * Returns fields used by both FinanceKpiGrid and CollectionsHealthCard.
 */
export async function getProjectFinanceSummary(
  projectId: string,
): Promise<{ kpis: FinanceKpis; collections: CollectionsHealth }> {
  const raw = await apiFetch<BackendFinanceSummary>(
    `/finance/projects/${projectId}/summary`,
  );
  return {
    kpis: {
      total_contract_value: raw.total_contract_value,
      total_collected: raw.total_collected,
      total_receivable: raw.total_receivable,
      collection_ratio: raw.collection_ratio,
      units_sold: raw.units_sold,
      total_units: raw.total_units,
      average_unit_price: raw.average_unit_price,
      currency: raw.currency,
    },
    collections: {
      total_collected: raw.total_collected,
      total_receivable: raw.total_receivable,
      collection_ratio: raw.collection_ratio,
    },
  };
}

/**
 * Fetch project cashflow summary.
 *
 * Backend endpoint: GET /cashflow/projects/{projectId}/cashflow-summary
 *
 * Backend → UI mapping:
 *   total_expected_inflows   → expected_inflows
 *   total_expected_outflows  → expected_outflows
 *   total_net_cashflow       → net_cashflow
 *   closing_balance          → closing_balance
 */
export async function getProjectCashflowSummary(
  projectId: string,
): Promise<CashflowHealth> {
  const raw = await apiFetch<BackendCashflowSummary>(
    `/cashflow/projects/${projectId}/cashflow-summary`,
  );
  return {
    expected_inflows: raw.total_expected_inflows,
    expected_outflows: raw.total_expected_outflows,
    net_cashflow: raw.total_net_cashflow,
    closing_balance: raw.closing_balance,
  };
}

/**
 * Fetch project sales exceptions summary.
 *
 * Backend endpoint: GET /sales-exceptions/projects/{projectId}/summary
 */
export async function getProjectSalesExceptionsSummary(
  projectId: string,
): Promise<SalesExceptionImpact> {
  return apiFetch<BackendSalesExceptionsSummary>(
    `/sales-exceptions/projects/${projectId}/summary`,
  );
}

/**
 * Fetch project registration summary.
 *
 * Backend endpoint: GET /registry/projects/{projectId}/summary
 *
 * Backend → UI mapping:
 *   registration_completion_ratio → completion_ratio
 */
export async function getProjectRegistrationSummary(
  projectId: string,
): Promise<RegistrationFinanceSignal> {
  const raw = await apiFetch<BackendRegistrationSummary>(
    `/registry/projects/${projectId}/summary`,
  );
  return {
    total_sold_units: raw.total_sold_units,
    registration_cases_completed: raw.registration_cases_completed,
    registration_cases_open: raw.registration_cases_open,
    sold_not_registered: raw.sold_not_registered,
    completion_ratio: raw.registration_completion_ratio,
  };
}

/**
 * Fetch project commission summary.
 *
 * Backend endpoint: GET /commission/projects/{projectId}/summary
 *
 * Pending exposure is computed by the display component as:
 *   draft_payouts + calculated_payouts
 * Cancelled payouts are NOT included — they are dead, not pending.
 */
export async function getProjectCommissionSummary(
  projectId: string,
): Promise<CommissionExposure> {
  const raw = await apiFetch<BackendCommissionSummary>(
    `/commission/projects/${projectId}/summary`,
  );
  return {
    total_payouts: raw.total_payouts,
    draft_payouts: raw.draft_payouts,
    calculated_payouts: raw.calculated_payouts,
    approved_payouts: raw.approved_payouts,
    cancelled_payouts: raw.cancelled_payouts,
    total_gross_value: raw.total_gross_value,
    total_commission_pool: raw.total_commission_pool,
  };
}
