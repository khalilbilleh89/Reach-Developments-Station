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
  CollectionsAlert,
  CollectionsAlertList,
  ContractAging,
  MatchedInstallmentAllocation,
  MonthlyForecastEntry,
  PortfolioAging,
  PortfolioCashflowForecast,
  ProjectAging,
  ProjectCashflowForecast,
  ProjectRevenueSummary,
  ReceiptMatchResult,
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

// ---------- Raw backend shapes for collections alerts ----------------

interface BackendCollectionsAlert {
  alert_id: string;
  contract_id: string;
  installment_id: string;
  alert_type: string;
  severity: string;
  days_overdue: number;
  outstanding_balance: number;
  created_at: string;
  resolved_at: string | null;
  notes: string | null;
}

interface BackendCollectionsAlertList {
  items: BackendCollectionsAlert[];
  total: number;
}

interface BackendMatchedAllocation {
  installment_id: string;
  allocated_amount: number;
}

interface BackendReceiptMatchResult {
  contract_id: string;
  payment_amount: number;
  strategy: string;
  matched_installment_ids: string[];
  allocations: BackendMatchedAllocation[];
  unallocated_amount: number;
}

// ---------- Mapping helpers (collections) -----------------------------

function mapCollectionsAlert(raw: BackendCollectionsAlert): CollectionsAlert {
  return {
    alertId: raw.alert_id,
    contractId: raw.contract_id,
    installmentId: raw.installment_id,
    alertType: raw.alert_type,
    severity: raw.severity as CollectionsAlert["severity"],
    daysOverdue: raw.days_overdue,
    outstandingBalance: raw.outstanding_balance,
    createdAt: raw.created_at,
    resolvedAt: raw.resolved_at,
    notes: raw.notes,
  };
}

// ---------- Exported collections query functions ---------------------

/**
 * Fetch all active (unresolved) collections alerts.
 *
 * Backend endpoint: GET /finance/collections/alerts
 */
export async function getCollectionsAlerts(
  severity?: string,
): Promise<CollectionsAlertList> {
  const params = severity ? `?severity=${encodeURIComponent(severity)}` : "";
  const raw = await apiFetch<BackendCollectionsAlertList>(
    `/finance/collections/alerts${params}`,
  );
  return {
    items: raw.items.map(mapCollectionsAlert),
    total: raw.total,
  };
}

/**
 * Generate collections alerts from overdue installments.
 *
 * Backend endpoint: POST /finance/collections/alerts/generate
 */
export async function generateCollectionsAlerts(): Promise<CollectionsAlertList> {
  const raw = await apiFetch<BackendCollectionsAlertList>(
    "/finance/collections/alerts/generate",
    { method: "POST" },
  );
  return {
    items: raw.items.map(mapCollectionsAlert),
    total: raw.total,
  };
}

/**
 * Resolve a collections alert by ID.
 *
 * Backend endpoint: POST /finance/collections/alerts/{id}/resolve
 */
export async function resolveCollectionsAlert(
  alertId: string,
  notes?: string,
): Promise<CollectionsAlert> {
  const raw = await apiFetch<BackendCollectionsAlert>(
    `/finance/collections/alerts/${alertId}/resolve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: notes ?? null }),
    },
  );
  return mapCollectionsAlert(raw);
}

/**
 * Match an incoming payment amount to outstanding installment obligations.
 *
 * Backend endpoint: POST /finance/payments/match-receipt
 */
export async function matchPaymentReceipt(
  contractId: string,
  paymentAmount: number,
): Promise<ReceiptMatchResult> {
  const raw = await apiFetch<BackendReceiptMatchResult>(
    "/finance/payments/match-receipt",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contract_id: contractId,
        payment_amount: paymentAmount,
      }),
    },
  );
  return {
    contractId: raw.contract_id,
    paymentAmount: raw.payment_amount,
    strategy: raw.strategy as ReceiptMatchResult["strategy"],
    matchedInstallmentIds: raw.matched_installment_ids,
    allocations: raw.allocations.map(
      (a): MatchedInstallmentAllocation => ({
        installmentId: a.installment_id,
        allocatedAmount: a.allocated_amount,
      }),
    ),
    unallocatedAmount: raw.unallocated_amount,
  };
}

// ---------- Raw backend cashflow forecast shapes (internal) ----------

interface BackendMonthlyForecastEntry {
  month: string;
  expected_collections: number;
  installment_count: number;
}

interface BackendProjectCashflowForecast {
  project_id: string;
  total_expected: number;
  monthly_entries: BackendMonthlyForecastEntry[];
}

interface BackendPortfolioCashflowForecast {
  total_expected: number;
  project_count: number;
  monthly_entries: BackendMonthlyForecastEntry[];
  project_forecasts: BackendProjectCashflowForecast[];
}

// ---------- Mapping helpers (internal) --------------------------------

function mapMonthlyForecastEntry(
  raw: BackendMonthlyForecastEntry,
): MonthlyForecastEntry {
  return {
    month: raw.month,
    expectedCollections: raw.expected_collections,
    installmentCount: raw.installment_count,
  };
}

function mapProjectCashflowForecast(
  raw: BackendProjectCashflowForecast,
): ProjectCashflowForecast {
  return {
    projectId: raw.project_id,
    totalExpected: raw.total_expected,
    monthlyEntries: raw.monthly_entries.map(mapMonthlyForecastEntry),
  };
}

// ---------- Exported cashflow forecast query functions ---------------

/**
 * Fetch the portfolio-wide cashflow forecast.
 *
 * Backend endpoint: GET /finance/cashflow/forecast
 */
export async function getPortfolioCashflowForecast(): Promise<PortfolioCashflowForecast> {
  const raw = await apiFetch<BackendPortfolioCashflowForecast>(
    "/finance/cashflow/forecast",
  );
  return {
    totalExpected: raw.total_expected,
    projectCount: raw.project_count,
    monthlyEntries: raw.monthly_entries.map(mapMonthlyForecastEntry),
    projectForecasts: raw.project_forecasts.map(mapProjectCashflowForecast),
  };
}

/**
 * Fetch the cashflow forecast for a single project.
 *
 * Backend endpoint: GET /finance/cashflow/forecast/project/{projectId}
 */
export async function getProjectCashflowForecast(
  projectId: string,
): Promise<ProjectCashflowForecast> {
  const raw = await apiFetch<BackendProjectCashflowForecast>(
    `/finance/cashflow/forecast/project/${encodeURIComponent(projectId)}`,
  );
  return mapProjectCashflowForecast(raw);
}
