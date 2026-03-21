/**
 * finance-api.ts — API wrappers for the revenue recognition endpoints.
 *
 * Calls:
 *   GET /finance/contracts/{id}/revenue
 *   GET /finance/projects/{id}/revenue-summary
 *   GET /finance/revenue/overview
 *
 * Backend snake_case fields are mapped to camelCase UI types defined in
 * finance-types.ts. No financial calculations are performed here.
 */

import { apiFetch } from "./api-client";
import type {
  RevenueRecognition,
  ProjectRevenueSummary,
  RevenueOverview,
} from "./finance-types";

// ---------- Raw backend response shapes (internal) ----------------------

interface BackendRevenueRecognition {
  contract_id: string;
  contract_total: number;
  recognized_revenue: number;
  deferred_revenue: number;
  recognition_percentage: number;
}

interface BackendProjectRevenueSummary {
  project_id: string;
  total_contract_value: number;
  total_recognized_revenue: number;
  total_deferred_revenue: number;
  overall_recognition_percentage: number;
  contract_count: number;
  contracts: BackendRevenueRecognition[];
}

interface BackendRevenueOverview {
  total_contract_value: number;
  total_recognized_revenue: number;
  total_deferred_revenue: number;
  overall_recognition_percentage: number;
  project_count: number;
  contract_count: number;
}

// ---------- Mapping helpers ----------------------------------------------

function mapRevenueRecognition(raw: BackendRevenueRecognition): RevenueRecognition {
  return {
    contract_id: raw.contract_id,
    contractTotal: raw.contract_total,
    recognizedRevenue: raw.recognized_revenue,
    deferredRevenue: raw.deferred_revenue,
    recognitionPercentage: raw.recognition_percentage,
  };
}

// ---------- Exported query functions ------------------------------------

/**
 * Fetch revenue recognition data for a single contract.
 *
 * Backend endpoint: GET /finance/contracts/{contractId}/revenue
 */
export async function getContractRevenue(
  contractId: string,
): Promise<RevenueRecognition> {
  const raw = await apiFetch<BackendRevenueRecognition>(
    `/finance/contracts/${contractId}/revenue`,
  );
  return mapRevenueRecognition(raw);
}

/**
 * Fetch aggregated revenue recognition for all contracts in a project.
 *
 * Backend endpoint: GET /finance/projects/{projectId}/revenue-summary
 */
export async function getProjectRevenueSummary(
  projectId: string,
): Promise<ProjectRevenueSummary> {
  const raw = await apiFetch<BackendProjectRevenueSummary>(
    `/finance/projects/${projectId}/revenue-summary`,
  );
  return {
    project_id: raw.project_id,
    totalContractValue: raw.total_contract_value,
    totalRecognizedRevenue: raw.total_recognized_revenue,
    totalDeferredRevenue: raw.total_deferred_revenue,
    overallRecognitionPercentage: raw.overall_recognition_percentage,
    contractCount: raw.contract_count,
    contracts: raw.contracts.map(mapRevenueRecognition),
  };
}

/**
 * Fetch portfolio-wide revenue recognition overview.
 *
 * Backend endpoint: GET /finance/revenue/overview
 */
export async function getRevenueOverview(): Promise<RevenueOverview> {
  const raw = await apiFetch<BackendRevenueOverview>("/finance/revenue/overview");
  return {
    totalContractValue: raw.total_contract_value,
    totalRecognizedRevenue: raw.total_recognized_revenue,
    totalDeferredRevenue: raw.total_deferred_revenue,
    overallRecognitionPercentage: raw.overall_recognition_percentage,
    projectCount: raw.project_count,
    contractCount: raw.contract_count,
  };
}
