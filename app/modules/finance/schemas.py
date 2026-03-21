"""
finance.schemas

Pydantic response schemas for the finance summary API.

All fields represent aggregated financial state computed at query time;
no raw financial tables are exposed.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.modules.collections.aging_engine import AgingBucket

from datetime import datetime


class ProjectFinanceSummaryResponse(BaseModel):
    """Aggregated financial summary for a single project."""

    project_id: str

    # Unit inventory counts
    total_units: int = Field(..., ge=0)
    units_sold: int = Field(..., ge=0)
    units_available: int = Field(..., ge=0)

    # Revenue aggregates (monetary amounts in the project currency)
    total_contract_value: float = Field(..., ge=0)
    total_collected: float = Field(..., ge=0)
    total_receivable: float = Field(..., ge=0)

    # Ratio metrics
    collection_ratio: float = Field(..., ge=0, le=1)

    # Pricing metrics
    average_unit_price: float = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Revenue recognition schemas
# ---------------------------------------------------------------------------


class RevenueRecognitionResponse(BaseModel):
    """Revenue recognition breakdown for a single contract.

    recognized_revenue + deferred_revenue always equals contract_total.
    """

    contract_id: str
    contract_total: float = Field(..., ge=0)
    recognized_revenue: float = Field(..., ge=0)
    deferred_revenue: float = Field(..., ge=0)
    recognition_percentage: float = Field(..., ge=0, le=100)


class ProjectRevenueSummaryResponse(BaseModel):
    """Aggregated revenue recognition summary for a project."""

    project_id: str
    total_contract_value: float = Field(..., ge=0)
    total_recognized_revenue: float = Field(..., ge=0)
    total_deferred_revenue: float = Field(..., ge=0)
    overall_recognition_percentage: float = Field(..., ge=0, le=100)
    contract_count: int = Field(..., ge=0)
    contracts: List[RevenueRecognitionResponse] = Field(default_factory=list)


class PortfolioRevenueOverviewResponse(BaseModel):
    """Portfolio-wide revenue recognition overview across all projects."""

    total_contract_value: float = Field(..., ge=0)
    total_recognized_revenue: float = Field(..., ge=0)
    total_deferred_revenue: float = Field(..., ge=0)
    overall_recognition_percentage: float = Field(..., ge=0, le=100)
    project_count: int = Field(..., ge=0)
    contract_count: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Collections aging schemas
# ---------------------------------------------------------------------------


class AgingBucketSummary(BaseModel):
    """Aggregated receivable totals for a single aging bucket."""

    bucket: AgingBucket
    amount: float = Field(..., ge=0)
    installment_count: int = Field(..., ge=0)


class ContractAgingResponse(BaseModel):
    """Receivable aging breakdown for a single contract."""

    contract_id: str
    contract_total: float = Field(..., ge=0)
    paid_amount: float = Field(..., ge=0)
    outstanding_amount: float = Field(..., ge=0)
    aging_buckets: List[AgingBucketSummary] = Field(default_factory=list)


class ProjectAgingResponse(BaseModel):
    """Aggregated receivable aging for all outstanding installments in a project."""

    project_id: str
    total_outstanding: float = Field(..., ge=0)
    installment_count: int = Field(..., ge=0)
    aging_buckets: List[AgingBucketSummary] = Field(default_factory=list)


class PortfolioAgingResponse(BaseModel):
    """Portfolio-wide receivable aging distribution across all projects."""

    total_outstanding: float = Field(..., ge=0)
    installment_count: int = Field(..., ge=0)
    project_count: int = Field(..., ge=0)
    aging_buckets: List[AgingBucketSummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Collections alert schemas
# ---------------------------------------------------------------------------


class CollectionsAlertResponse(BaseModel):
    """Response model for a single collections alert."""

    alert_id: str
    contract_id: str
    installment_id: str
    alert_type: str
    severity: str
    days_overdue: int = Field(..., ge=0)
    outstanding_balance: float = Field(..., ge=0)
    created_at: datetime
    resolved_at: Optional[datetime] = None
    notes: Optional[str] = None


class CollectionsAlertListResponse(BaseModel):
    """Response model for a list of active collections alerts."""

    items: List[CollectionsAlertResponse] = Field(default_factory=list)
    total: int = Field(..., ge=0)


class ResolveAlertRequest(BaseModel):
    """Payload for resolving a collections alert."""

    notes: Optional[str] = Field(None, max_length=1000)


# ---------------------------------------------------------------------------
# Receipt matching schemas
# ---------------------------------------------------------------------------


class MatchReceiptRequest(BaseModel):
    """Payload for matching an incoming payment to installment obligations."""

    contract_id: str = Field(..., min_length=1)
    payment_amount: float = Field(..., gt=0)


class MatchedInstallmentAllocation(BaseModel):
    """Amount allocated to a single installment during matching."""

    installment_id: str
    allocated_amount: float = Field(..., ge=0)


class ReceiptMatchResult(BaseModel):
    """Result of matching a payment to outstanding installment obligations."""

    contract_id: str
    payment_amount: float = Field(..., ge=0)
    strategy: str
    matched_installment_ids: List[str] = Field(default_factory=list)
    allocations: List[MatchedInstallmentAllocation] = Field(default_factory=list)
    unallocated_amount: float = Field(..., ge=0)


class UnmatchedReceiptResponse(BaseModel):
    """Response model when a payment cannot be matched to any obligation."""

    contract_id: str
    payment_amount: float = Field(..., ge=0)
    reason: str


# ---------------------------------------------------------------------------
# Cashflow forecasting schemas
# ---------------------------------------------------------------------------


class MonthlyForecastEntryResponse(BaseModel):
    """Projected cash inflow for a single calendar month."""

    month: str = Field(..., description="Calendar month in YYYY-MM format")
    expected_collections: float = Field(..., ge=0)
    installment_count: int = Field(..., ge=0)


class ProjectCashflowForecastResponse(BaseModel):
    """Cashflow forecast for a single project."""

    project_id: str
    total_expected: float = Field(..., ge=0)
    monthly_entries: List[MonthlyForecastEntryResponse] = Field(default_factory=list)


class PortfolioCashflowForecastResponse(BaseModel):
    """Portfolio-wide cashflow forecast aggregated across all projects."""

    total_expected: float = Field(..., ge=0)
    project_count: int = Field(..., ge=0)
    monthly_entries: List[MonthlyForecastEntryResponse] = Field(default_factory=list)
    project_forecasts: List[ProjectCashflowForecastResponse] = Field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Portfolio financial summary schemas
# ---------------------------------------------------------------------------


class ProjectFinancialSummaryEntry(BaseModel):
    """Per-project metrics within the portfolio financial summary."""

    project_id: str
    recognized_revenue: float = Field(..., ge=0)
    receivables_exposure: float = Field(..., ge=0)
    collection_rate: float = Field(..., ge=0, le=1)


class PortfolioFinancialSummaryResponse(BaseModel):
    """Consolidated financial summary for the entire portfolio.

    Aggregates recognized revenue, receivables exposure, overdue exposure,
    and next-month cashflow forecast across all projects.
    """

    total_revenue_recognized: float = Field(..., ge=0)
    total_deferred_revenue: float = Field(..., ge=0)
    total_receivables: float = Field(..., ge=0)
    overdue_receivables: float = Field(..., ge=0)
    overdue_receivables_pct: float = Field(..., ge=0, le=100)
    forecast_next_month: float = Field(..., ge=0)
    project_count: int = Field(..., ge=0)
    project_summaries: List[ProjectFinancialSummaryEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Treasury monitoring schemas
# ---------------------------------------------------------------------------


class ProjectExposureEntry(BaseModel):
    """Receivable exposure metrics for a single project within the treasury view."""

    project_id: str
    receivable_exposure: float = Field(..., ge=0)
    exposure_percentage: float = Field(..., ge=0, le=100)
    forecast_inflow: float = Field(..., ge=0)


class TreasuryMonitoringResponse(BaseModel):
    """Portfolio-level treasury monitoring snapshot.

    Provides liquidity and exposure indicators derived from the existing
    financial engines.  No financial calculations are performed here —
    values are aggregated from revenue recognition, aging, and cashflow
    forecast outputs.
    """

    cash_position: float = Field(..., ge=0)
    receivables_exposure: float = Field(..., ge=0)
    overdue_receivables: float = Field(..., ge=0)
    liquidity_ratio: float = Field(..., ge=0, le=1)
    forecast_next_month: float = Field(..., ge=0)
    project_count: int = Field(..., ge=0)
    project_exposures: List[ProjectExposureEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Analytics dashboard schemas
# ---------------------------------------------------------------------------


class RevenueTrendEntry(BaseModel):
    """Aggregated recognized revenue for a single calendar month."""

    month: str
    total_recognized_revenue: float = Field(..., ge=0)


class CollectionsTrendEntry(BaseModel):
    """Aggregated collections amount for a single calendar month."""

    month: str
    total_amount: float = Field(..., ge=0)


class ReceivablesTrendEntry(BaseModel):
    """Total receivables across all projects for a single snapshot date."""

    snapshot_date: str
    total_receivables: float = Field(..., ge=0)


class PortfolioKPI(BaseModel):
    """Top-level portfolio financial KPIs derived from the analytics fact tables."""

    total_revenue: float = Field(..., ge=0)
    total_collections: float = Field(..., ge=0)
    total_receivables: float = Field(..., ge=0)
    collection_efficiency: float = Field(..., ge=0)


class PortfolioAnalyticsResponse(BaseModel):
    """Portfolio analytics dashboard response.

    Contains revenue trends, collections trends, receivable exposure trends,
    and top-level portfolio KPIs — all derived from the analytics fact tables.
    """

    revenue_trend: List[RevenueTrendEntry] = Field(default_factory=list)
    collections_trend: List[CollectionsTrendEntry] = Field(default_factory=list)
    receivables_trend: List[ReceivablesTrendEntry] = Field(default_factory=list)
    kpis: PortfolioKPI


# ---------------------------------------------------------------------------
# Project financial dashboard schemas
# ---------------------------------------------------------------------------


class ProjectFinancialKPIResponse(BaseModel):
    """Top-level financial KPIs for a single project."""

    recognized_revenue: float = Field(..., ge=0)
    deferred_revenue: float = Field(..., ge=0)
    receivables_exposure: float = Field(..., ge=0)
    overdue_receivables: float = Field(..., ge=0)
    overdue_percentage: float = Field(..., ge=0, le=100)
    forecast_next_month: float = Field(..., ge=0)
    collection_efficiency: float = Field(..., ge=0)


class ProjectFinancialTrendEntry(BaseModel):
    """A single period-value pair for a project financial trend."""

    period: str = Field(..., description="Calendar month (YYYY-MM) or snapshot date (YYYY-MM-DD)")
    value: float = Field(..., ge=0)


class ProjectFinancialDashboardResponse(BaseModel):
    """Full project-level financial dashboard payload.

    Composes KPIs and trend series for a single project from the existing
    finance services and analytics fact tables.
    """

    project_id: str
    kpis: ProjectFinancialKPIResponse
    revenue_trend: List[ProjectFinancialTrendEntry] = Field(default_factory=list)
    collections_trend: List[ProjectFinancialTrendEntry] = Field(default_factory=list)
    receivables_trend: List[ProjectFinancialTrendEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Analytics fact layer schemas
# ---------------------------------------------------------------------------


class AnalyticsRebuildResponse(BaseModel):
    """Response model for the analytics rebuild endpoint.

    Returns a summary of how many rows were inserted into each analytics
    fact table during the rebuild run.
    """

    revenue_facts_created: int = Field(..., ge=0)
    collections_facts_created: int = Field(..., ge=0)
    receivable_snapshots_created: int = Field(..., ge=0)
