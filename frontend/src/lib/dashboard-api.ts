/**
 * dashboard-api.ts — wrapper functions for all dashboard data queries.
 *
 * Each function maps to one backend summary endpoint. No business logic
 * is performed here — values are passed through from the backend as-is.
 */

import { apiFetch } from "./api-client";

// ---------- Types --------------------------------------------------------

export interface Project {
  id: string;
  name: string;
  status?: string;
}

export interface FinancialSummary {
  total_contract_value: number;
  total_collected: number;
  total_receivable: number;
  collection_ratio: number;
  units_sold: number;
  total_units: number;
  average_unit_price: number;
}

export interface RegistrationSummary {
  total_cases: number;
  registered: number;
  in_progress: number;
  pending: number;
  registration_progress_pct: number;
}

export interface CashflowSummary {
  current_cash_position: number;
  expected_inflows: number;
  expected_outflows: number;
  net_position: number;
}

export interface SalesExceptionsSummary {
  total_exceptions: number;
  total_discount_amount: number;
  average_discount_pct: number;
}

// ---------- Query functions ----------------------------------------------

export async function getProjects(): Promise<Project[]> {
  return apiFetch<Project[]>("/projects");
}

export async function getFinancialSummary(
  projectId: string,
): Promise<FinancialSummary> {
  return apiFetch<FinancialSummary>(
    `/finance/projects/${projectId}/summary`,
  );
}

export async function getRegistrationSummary(
  projectId: string,
): Promise<RegistrationSummary> {
  return apiFetch<RegistrationSummary>(
    `/registration/projects/${projectId}/summary`,
  );
}

export async function getCashflowSummary(
  projectId: string,
): Promise<CashflowSummary> {
  return apiFetch<CashflowSummary>(
    `/cashflow/projects/${projectId}/cashflow-summary`,
  );
}

export async function getSalesExceptionsSummary(
  projectId: string,
): Promise<SalesExceptionsSummary> {
  return apiFetch<SalesExceptionsSummary>(
    `/sales-exceptions/projects/${projectId}/summary`,
  );
}
