/**
 * finance-types.ts — TypeScript types for the revenue recognition API.
 *
 * These types mirror the backend Pydantic schemas in
 * app/modules/finance/schemas.py (RevenueRecognitionResponse,
 * ProjectRevenueSummaryResponse, PortfolioRevenueOverviewResponse,
 * ContractAgingResponse, ProjectAgingResponse, PortfolioAgingResponse).
 *
 * All fields use camelCase. Backend snake_case fields are mapped in
 * finance-api.ts before these types are populated.
 *
 * No financial calculations are performed using these types — they are
 * display models only.
 */

// ---------- Single-contract revenue recognition --------------------------

export interface RevenueRecognition {
  /** UUID of the contract. */
  contractId: string;
  /** Total contract value. */
  contractTotal: number;
  /** Sum of all paid installments. */
  recognizedRevenue: number;
  /** contractTotal − recognizedRevenue (≥ 0). */
  deferredRevenue: number;
  /** recognizedRevenue / contractTotal × 100, clamped to [0, 100]. */
  recognitionPercentage: number;
}

// ---------- Project-level revenue summary --------------------------------

export interface ProjectRevenueSummary {
  projectId: string;
  totalContractValue: number;
  totalRecognizedRevenue: number;
  totalDeferredRevenue: number;
  overallRecognitionPercentage: number;
  contractCount: number;
  /** Per-contract breakdown. */
  contracts: RevenueRecognition[];
}

// ---------- Portfolio-wide revenue overview ------------------------------

export interface RevenueOverview {
  totalContractValue: number;
  totalRecognizedRevenue: number;
  totalDeferredRevenue: number;
  overallRecognitionPercentage: number;
  projectCount: number;
  contractCount: number;
}

// ---------- Receivable aging types ---------------------------------------

/** One of the five canonical aging bucket labels. */
export type ReceivableAgingBucket = "current" | "1-30" | "31-60" | "61-90" | "90+";

/** Aggregated receivable totals for a single aging bucket. */
export interface AgingBucketSummary {
  bucket: ReceivableAgingBucket;
  amount: number;
  installmentCount: number;
}

/** Receivable aging breakdown for a single contract. */
export interface ContractAging {
  contractId: string;
  contractTotal: number;
  paidAmount: number;
  outstandingAmount: number;
  agingBuckets: AgingBucketSummary[];
}

/** Aggregated receivable aging for all outstanding installments in a project. */
export interface ProjectAging {
  projectId: string;
  totalOutstanding: number;
  installmentCount: number;
  agingBuckets: AgingBucketSummary[];
}

/** Portfolio-wide receivable aging distribution. */
export interface PortfolioAging {
  totalOutstanding: number;
  installmentCount: number;
  projectCount: number;
  agingBuckets: AgingBucketSummary[];
}

// ---------- Collections alert types ------------------------------------

/** Severity tier of a collections alert. */
export type AlertSeverity = "warning" | "critical" | "high_risk";

/** Response model for a single collections alert. */
export interface CollectionsAlert {
  alertId: string;
  contractId: string;
  installmentId: string;
  alertType: string;
  severity: AlertSeverity;
  daysOverdue: number;
  outstandingBalance: number;
  createdAt: string;
  resolvedAt: string | null;
  notes: string | null;
}

/** Paginated list of active collections alerts. */
export interface CollectionsAlertList {
  items: CollectionsAlert[];
  total: number;
}

// ---------- Receipt matching types ------------------------------------

/** Strategy used when matching a payment to installments. */
export type MatchStrategy = "exact" | "partial" | "multi_installment" | "unmatched";

/** Allocation of a payment amount to a single installment. */
export interface MatchedInstallmentAllocation {
  installmentId: string;
  allocatedAmount: number;
}

/** Result of matching a payment to outstanding installment obligations. */
export interface ReceiptMatchResult {
  contractId: string;
  paymentAmount: number;
  strategy: MatchStrategy;
  matchedInstallmentIds: string[];
  allocations: MatchedInstallmentAllocation[];
  unallocatedAmount: number;
}
