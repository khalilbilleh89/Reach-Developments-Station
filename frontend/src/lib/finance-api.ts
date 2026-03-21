/**
 * finance-api.ts — API wrappers for the revenue recognition and aging endpoints.
 *
 * Calls:
 *   GET /finance/contracts/{id}/revenue
 *   GET /finance/projects/{id}/revenue-summary
 *   GET /finance/revenue/overview
 *   GET /finance/contracts/{id}/aging
 *   GET /finance/projects/{id}/aging
 *   GET /finance/receivables/aging-overview
 *
 * Backend snake_case fields are mapped to camelCase UI types defined in
 * finance-types.ts. No financial calculations are performed here.
 */

import { apiFetch } from "./api-client";
import type {
  AgingBucketSummary,
  ContractAging,
  PortfolioAging,
  ProjectAging,
  ProjectRevenueSummary,
  ReceivableAgingBucket,
  RevenueOverview,
  RevenueRecognition,
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

interface BackendAgingBucketSummary {
  bucket: ReceivableAgingBucket;
  amount: number;
  installment_count: number;
}

interface BackendContractAging {
  contract_id: string;
  contract_total: number;
  paid_amount: number;
  outstanding_amount: number;
  aging_buckets: BackendAgingBucketSummary[];
}

interface BackendProjectAging {
  project_id: string;
  total_outstanding: number;
  installment_count: number;
  aging_buckets: BackendAgingBucketSummary[];
}

interface BackendPortfolioAging {
  total_outstanding: number;
  installment_count: number;
  project_count: number;
  aging_buckets: BackendAgingBucketSummary[];
}

// ---------- Mapping helpers ----------------------------------------------

function mapRevenueRecognition(raw: BackendRevenueRecognition): RevenueRecognition {
  return {
    contractId: raw.contract_id,
    contractTotal: raw.contract_total,
    recognizedRevenue: raw.recognized_revenue,
    deferredRevenue: raw.deferred_revenue,
    recognitionPercentage: raw.recognition_percentage,
  };
}

function mapAgingBucket(raw: BackendAgingBucketSummary): AgingBucketSummary {
  return {
    bucket: raw.bucket,
    amount: raw.amount,
    installmentCount: raw.installment_count,
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
    projectId: raw.project_id,
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

/**
 * Fetch receivable aging breakdown for a single contract.
 *
 * Backend endpoint: GET /finance/contracts/{contractId}/aging
 */
export async function getContractAging(contractId: string): Promise<ContractAging> {
  const raw = await apiFetch<BackendContractAging>(
    `/finance/contracts/${contractId}/aging`,
  );
  return {
    contractId: raw.contract_id,
    contractTotal: raw.contract_total,
    paidAmount: raw.paid_amount,
    outstandingAmount: raw.outstanding_amount,
    agingBuckets: raw.aging_buckets.map(mapAgingBucket),
  };
}

/**
 * Fetch aggregated receivable aging for all outstanding installments in a project.
 *
 * Backend endpoint: GET /finance/projects/{projectId}/aging
 */
export async function getProjectAging(projectId: string): Promise<ProjectAging> {
  const raw = await apiFetch<BackendProjectAging>(
    `/finance/projects/${projectId}/aging`,
  );
  return {
    projectId: raw.project_id,
    totalOutstanding: raw.total_outstanding,
    installmentCount: raw.installment_count,
    agingBuckets: raw.aging_buckets.map(mapAgingBucket),
  };
}

/**
 * Fetch portfolio-wide receivable aging distribution.
 *
 * Backend endpoint: GET /finance/receivables/aging-overview
 */
export async function getPortfolioAging(): Promise<PortfolioAging> {
  const raw = await apiFetch<BackendPortfolioAging>(
    "/finance/receivables/aging-overview",
  );
  return {
    totalOutstanding: raw.total_outstanding,
    installmentCount: raw.installment_count,
    projectCount: raw.project_count,
    agingBuckets: raw.aging_buckets.map(mapAgingBucket),
  };
}
