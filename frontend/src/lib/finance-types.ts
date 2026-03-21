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

// ---------- Cashflow forecasting types --------------------------------

/** Monthly expected cash inflow entry in a cashflow forecast. */
export interface MonthlyForecastEntry {
  month: string;
  expectedCollections: number;
  installmentCount: number;
}

/** Cashflow forecast for a single project. */
export interface ProjectCashflowForecast {
  projectId: string;
  totalExpected: number;
  monthlyEntries: MonthlyForecastEntry[];
}

/** Portfolio-wide cashflow forecast aggregated across all projects. */
export interface PortfolioCashflowForecast {
  totalExpected: number;
  projectCount: number;
  monthlyEntries: MonthlyForecastEntry[];
  projectForecasts: ProjectCashflowForecast[];
}

// ---------- Portfolio financial summary types -------------------------

/** Per-project metrics within the portfolio financial summary. */
export interface ProjectFinancialSummary {
  projectId: string;
  recognizedRevenue: number;
  receivablesExposure: number;
  collectionRate: number;
}

/** Consolidated financial summary for the entire portfolio. */
export interface PortfolioFinancialSummary {
  totalRevenueRecognized: number;
  totalDeferredRevenue: number;
  totalReceivables: number;
  overdueReceivables: number;
  overdueReceivablesPct: number;
  forecastNextMonth: number;
  projectCount: number;
  projectSummaries: ProjectFinancialSummary[];
}

// ---------- Treasury monitoring types --------------------------------

/** Receivable exposure metrics for a single project within the treasury view. */
export interface ProjectExposure {
  projectId: string;
  receivableExposure: number;
  exposurePercentage: number;
  forecastInflow: number;
}

/** Portfolio-level treasury monitoring snapshot. */
export interface TreasuryMonitoring {
  cashPosition: number;
  receivablesExposure: number;
  overdueReceivables: number;
  liquidityRatio: number;
  forecastNextMonth: number;
  projectCount: number;
  projectExposures: ProjectExposure[];
}

// ---------- Analytics fact layer types --------------------------------

/** Monthly recognized revenue entry from the analytics fact layer. */
export interface RevenueTrend {
  projectId: string;
  unitId: string;
  month: string;
  recognizedRevenue: number;
  contractValue: number;
}

/** Monthly payment collections entry from the analytics fact layer. */
export interface CollectionsTrend {
  projectId: string;
  paymentDate: string;
  month: string;
  amount: number;
  paymentMethod: string;
}

/** Receivable aging snapshot entry from the analytics fact layer. */
export interface ReceivablesTrend {
  projectId: string;
  snapshotDate: string;
  totalReceivables: number;
  bucket0To30: number;
  bucket31To60: number;
  bucket61To90: number;
  bucket90Plus: number;
}

// ---------- Portfolio analytics dashboard types -----------------------

/** Aggregated recognized revenue for a single calendar month. */
export interface RevenueTrendEntry {
  month: string;
  totalRecognizedRevenue: number;
}

/** Aggregated collections amount for a single calendar month. */
export interface CollectionsTrendEntry {
  month: string;
  totalAmount: number;
}

/** Total receivables across all projects for a single snapshot date. */
export interface ReceivablesTrendEntry {
  snapshotDate: string;
  totalReceivables: number;
}

/** Top-level portfolio financial KPIs from the analytics fact tables. */
export interface PortfolioKPI {
  totalRevenue: number;
  totalCollections: number;
  totalReceivables: number;
  collectionEfficiency: number;
}

/** Portfolio analytics dashboard response. */
export interface PortfolioAnalytics {
  revenueTrend: RevenueTrendEntry[];
  collectionsTrend: CollectionsTrendEntry[];
  receivablesTrend: ReceivablesTrendEntry[];
  kpis: PortfolioKPI;
}

// ---------- Project financial dashboard types -------------------------

/** Top-level financial KPIs for a single project. */
export interface ProjectFinancialKPI {
  recognizedRevenue: number;
  deferredRevenue: number;
  receivablesExposure: number;
  overdueReceivables: number;
  overduePercentage: number;
  forecastNextMonth: number;
  collectionEfficiency: number;
}

/** A single period-value pair for a project financial trend. */
export interface ProjectFinancialTrendEntry {
  period: string;
  value: number;
}

/** Full project-level financial dashboard payload. */
export interface ProjectFinancialDashboard {
  projectId: string;
  kpis: ProjectFinancialKPI;
  revenueTrend: ProjectFinancialTrendEntry[];
  collectionsTrend: ProjectFinancialTrendEntry[];
  receivablesTrend: ProjectFinancialTrendEntry[];
}

// ---------- Financial risk alert types -----------------------------------

/** Severity level of a financial risk alert produced by the alert engine. */
export type RiskAlertSeverity = "HIGH" | "MEDIUM" | "LOW";

/** A single structured financial risk alert for a project. */
export interface ProjectRiskAlert {
  projectId: string;
  alertType: string;
  severity: RiskAlertSeverity;
  message: string;
  metricValue: number;
  threshold: number;
}

/** Aggregated financial risk alerts across the entire portfolio. */
export interface PortfolioRiskResponse {
  alerts: ProjectRiskAlert[];
}
