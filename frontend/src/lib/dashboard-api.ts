/**
 * dashboard-api.ts — wrapper functions for all dashboard data queries.
 *
 * This module acts as the normalization boundary between the backend API
 * contract and the frontend UI model. Raw backend responses are transformed
 * here so that dashboard components can rely on stable, UI-friendly types.
 *
 * No financial calculations are performed here — values are either passed
 * through directly or renamed to match the UI field names.
 */

import { apiFetch } from "./api-client";

// ---------- Raw backend response types (internal) ------------------------

interface ProjectResponse {
  id: string;
  name: string;
  code: string;
  status: string;
  description?: string | null;
  location?: string | null;
}

interface ProjectListResponse {
  items: ProjectResponse[];
  total: number;
}

/** Raw backend: /finance/projects/{id}/summary */
interface BackendFinancialSummary {
  project_id: string;
  total_units: number;
  units_sold: number;
  units_available: number;
  total_contract_value: number;
  total_collected: number;
  total_receivable: number;
  collection_ratio: number;
  average_unit_price: number;
}

/** Raw backend: /registration/projects/{id}/summary */
interface BackendRegistrationSummary {
  project_id: string;
  total_sold_units: number;
  registration_cases_open: number;
  registration_cases_completed: number;
  sold_not_registered: number;
  registration_completion_ratio: number;
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

// ---------- UI-friendly exported types -----------------------------------

export interface Project {
  id: string;
  name: string;
  code: string;
  status: string;
}

export interface FinancialSummary {
  project_id: string;
  total_units: number;
  units_sold: number;
  units_available: number;
  total_contract_value: number;
  total_collected: number;
  total_receivable: number;
  collection_ratio: number;
  average_unit_price: number;
}

/**
 * UI registration summary — field names chosen for clarity in components.
 * Mapped from BackendRegistrationSummary in getRegistrationSummary().
 */
export interface RegistrationSummary {
  total_cases: number;
  registered: number;
  in_progress: number;
  /** Sold units that have no registration case opened yet. */
  pending: number;
  /** Progress percentage (0–100), derived from registration_completion_ratio. */
  registration_progress_pct: number;
}

/**
 * UI cashflow summary — field names chosen for clarity in components.
 * Mapped from BackendCashflowSummary in getCashflowSummary().
 */
export interface CashflowSummary {
  /** Latest forecast closing balance. */
  current_cash_position: number;
  expected_inflows: number;
  expected_outflows: number;
  net_position: number;
}

export interface SalesExceptionsSummary {
  total_exceptions: number;
  pending_exceptions: number;
  approved_exceptions: number;
  rejected_exceptions: number;
  total_discount_amount: number;
  total_incentive_value: number;
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

/** Fetch project financial summary. Fields match the backend response exactly. */
export async function getFinancialSummary(
  projectId: string,
): Promise<FinancialSummary> {
  return apiFetch<BackendFinancialSummary>(
    `/finance/projects/${projectId}/summary`,
  );
}

/**
 * Fetch project registration summary and normalize field names for the UI.
 *
 * Backend → UI mapping:
 *   registration_cases_completed     → registered
 *   registration_cases_open          → in_progress
 *   sold_not_registered              → pending
 *   registration_cases_open + completed → total_cases
 *   registration_completion_ratio × 100 → registration_progress_pct
 */
export async function getRegistrationSummary(
  projectId: string,
): Promise<RegistrationSummary> {
  const raw = await apiFetch<BackendRegistrationSummary>(
    `/registration/projects/${projectId}/summary`,
  );
  return {
    total_cases: raw.registration_cases_open + raw.registration_cases_completed,
    registered: raw.registration_cases_completed,
    in_progress: raw.registration_cases_open,
    pending: raw.sold_not_registered,
    registration_progress_pct: raw.registration_completion_ratio * 100,
  };
}

/**
 * Fetch project cashflow summary and normalize field names for the UI.
 *
 * Backend → UI mapping:
 *   closing_balance          → current_cash_position
 *   total_expected_inflows   → expected_inflows
 *   total_expected_outflows  → expected_outflows
 *   total_net_cashflow       → net_position
 */
export async function getCashflowSummary(
  projectId: string,
): Promise<CashflowSummary> {
  const raw = await apiFetch<BackendCashflowSummary>(
    `/cashflow/projects/${projectId}/cashflow-summary`,
  );
  return {
    current_cash_position: raw.closing_balance,
    expected_inflows: raw.total_expected_inflows,
    expected_outflows: raw.total_expected_outflows,
    net_position: raw.total_net_cashflow,
  };
}

/** Fetch sales exceptions summary. Fields match the backend response exactly. */
export async function getSalesExceptionsSummary(
  projectId: string,
): Promise<SalesExceptionsSummary> {
  return apiFetch<BackendSalesExceptionsSummary>(
    `/sales-exceptions/projects/${projectId}/summary`,
  );
}

