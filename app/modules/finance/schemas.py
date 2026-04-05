"""
finance.schemas

Pydantic response schemas for the finance summary API.

All fields represent aggregated financial state computed at query time;
no raw financial tables are exposed.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.collections.aging_engine import AgingBucket
from app.modules.finance.constants import (
    ConstructionEquityInjectionMethod,
    ConstructionLoanDrawMethod,
    ConstructionSpreadMethod,
    DEFAULT_DEBT_RATIO,
    DEFAULT_EQUITY_RATIO,
    DEFAULT_FINANCING_PROBABILITY,
    DEFAULT_FINANCING_START_OFFSET,
)
from app.shared.enums.finance import RiskAlertSeverity, RiskAlertType


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

    # Currency denomination of all monetary totals in this summary
    currency: str = Field(
        ...,
        description=(
            "ISO 4217 currency code for all monetary values in this summary "
            "(total_contract_value, total_collected, total_receivable, average_unit_price). "
            "Sourced from the project base_currency."
        ),
    )


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
# Cashflow forecasting schemas  (legacy — v1 simple forecast)
# ---------------------------------------------------------------------------


class MonthlyForecastEntryResponse(BaseModel):
    """Projected cash inflow for a single calendar month (legacy simple format)."""

    month: str = Field(..., description="Calendar month in YYYY-MM format")
    expected_collections: float = Field(..., ge=0)
    installment_count: int = Field(..., ge=0)


class ProjectCashflowForecastResponse(BaseModel):
    """Cashflow forecast for a single project (legacy simple format)."""

    project_id: str
    total_expected: float = Field(..., ge=0)
    monthly_entries: List[MonthlyForecastEntryResponse] = Field(default_factory=list)


class PortfolioCashflowForecastResponse(BaseModel):
    """Portfolio-wide cashflow forecast aggregated across all projects (legacy simple format)."""

    total_expected: float = Field(..., ge=0)
    project_count: int = Field(..., ge=0)
    monthly_entries: List[MonthlyForecastEntryResponse] = Field(default_factory=list)
    project_forecasts: List[ProjectCashflowForecastResponse] = Field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Cashflow forecasting schemas  (PR-33 comprehensive forecast)
# ---------------------------------------------------------------------------


class CashflowForecastAssumptions(BaseModel):
    """Forecast assumption parameters controlling collection probability model.

    Attributes
    ----------
    collection_probability:
        Fraction of outstanding balance expected to be collected (0.0–1.0).
        Default 1.0 = deterministic 100% collection.
    carry_forward_overdue:
        When True, installments overdue before the window start are carried
        into the first period bucket.
    include_paid_in_schedule:
        When True, already-paid installments are counted in scheduled_amount
        so that it reflects the full contractual obligation.
    """

    collection_probability: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Collection probability applied to outstanding installments (0–1).",
    )
    carry_forward_overdue: bool = Field(
        default=True,
        description="Include pre-window overdue installments in the first period bucket.",
    )
    include_paid_in_schedule: bool = Field(
        default=True,
        description="Count paid installments in scheduled_amount for period completeness.",
    )

    @field_validator("collection_probability")
    @classmethod
    def _validate_probability(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("collection_probability must be between 0.0 and 1.0")
        return v


class CashflowPeriodRow(BaseModel):
    """Rich per-period cashflow row in the comprehensive forecast response.

    All monetary amounts are in the project currency (AED by default).
    """

    period_start: date = Field(..., description="First day of the forecast period.")
    period_end: date = Field(..., description="Last day of the forecast period.")
    period_label: str = Field(..., description="Period identifier in YYYY-MM format.")

    scheduled_amount: float = Field(
        ...,
        ge=0,
        description="Total contractual amount due in this period.",
    )
    collected_amount: float = Field(
        ...,
        ge=0,
        description="Amount already settled for installments in this period.",
    )
    expected_amount: float = Field(
        ...,
        ge=0,
        description="Expected future collections: outstanding × collection_probability.",
    )
    variance_to_schedule: float = Field(
        ...,
        description="expected_amount − scheduled_amount (negative = shortfall).",
    )
    cumulative_expected_amount: float = Field(
        ...,
        ge=0,
        description="Running cumulative expected collections from window start.",
    )
    installment_count: int = Field(
        ...,
        ge=0,
        description="Number of installments falling in this period.",
    )


class CashflowForecastSummaryResponse(BaseModel):
    """High-level totals across all periods in the forecast window."""

    scheduled_total: float = Field(..., ge=0)
    collected_total: float = Field(..., ge=0)
    expected_total: float = Field(..., ge=0)
    variance_to_schedule: float = Field(
        ...,
        description="expected_total − scheduled_total (negative = shortfall).",
    )


class ContractCashflowForecastResponse(BaseModel):
    """Comprehensive cashflow forecast for a single contract.

    Returned by GET /finance/contracts/{contract_id}/cashflow-forecast.
    """

    scope_type: str = Field(default="contract")
    contract_id: str
    start_date: date
    end_date: date
    granularity: str = Field(default="monthly")
    assumptions: CashflowForecastAssumptions
    summary: CashflowForecastSummaryResponse
    periods: List[CashflowPeriodRow] = Field(default_factory=list)


class ProjectCashflowForecastV2Response(BaseModel):
    """Comprehensive cashflow forecast for a single project.

    Returned by GET /finance/projects/{project_id}/cashflow-forecast.
    """

    scope_type: str = Field(default="project")
    project_id: str
    start_date: date
    end_date: date
    granularity: str = Field(default="monthly")
    assumptions: CashflowForecastAssumptions
    summary: CashflowForecastSummaryResponse
    periods: List[CashflowPeriodRow] = Field(default_factory=list)


class PortfolioCashflowForecastV2Response(BaseModel):
    """Comprehensive cashflow forecast aggregated across the entire portfolio.

    Returned by GET /finance/portfolio/cashflow-forecast.
    """

    scope_type: str = Field(default="portfolio")
    start_date: date
    end_date: date
    granularity: str = Field(default="monthly")
    assumptions: CashflowForecastAssumptions
    summary: CashflowForecastSummaryResponse
    periods: List[CashflowPeriodRow] = Field(default_factory=list)
    project_forecasts: List[ProjectCashflowForecastV2Response] = Field(
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
    """Aggregated recognized revenue for a single calendar month and currency."""

    month: str
    currency: str
    total_recognized_revenue: float = Field(..., ge=0)


class CollectionsTrendEntry(BaseModel):
    """Aggregated collections amount for a single calendar month and currency."""

    month: str
    currency: str
    total_amount: float = Field(..., ge=0)


class ReceivablesTrendEntry(BaseModel):
    """Total receivables across all projects for a single snapshot date and currency."""

    snapshot_date: str
    currency: str
    total_receivables: float = Field(..., ge=0)


class PortfolioKPI(BaseModel):
    """Top-level portfolio financial KPIs derived from the analytics fact tables.

    ``collection_efficiency`` is ``None`` when the portfolio spans more than one
    currency denomination.  Dividing total collections by total revenue is
    mathematically invalid when the two totals are expressed in different
    currencies.  Consumers should treat ``None`` as "multi-currency portfolio —
    per-currency breakdown required".
    """

    total_revenue: float = Field(..., ge=0)
    total_collections: float = Field(..., ge=0)
    total_receivables: float = Field(..., ge=0)
    collection_efficiency: Optional[float] = Field(None, ge=0)
    currencies: List[str] = Field(
        default_factory=list,
        description="Distinct currency codes present in the analytics facts.",
    )


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
# Financial risk alert schemas
# ---------------------------------------------------------------------------


class ProjectRiskAlert(BaseModel):
    """A single financial risk alert for a project.

    Produced by FinancialRiskAlertEngine when a monitored metric breaches its
    configured threshold.
    """

    project_id: str
    alert_type: RiskAlertType = Field(..., description="Machine-readable alert category key.")
    severity: RiskAlertSeverity = Field(..., description="Alert severity: HIGH, MEDIUM, or LOW.")
    message: str = Field(..., description="Human-readable description of the risk condition.")
    metric_value: float = Field(..., description="Observed metric value that triggered the alert.")
    threshold: float = Field(..., description="Threshold the metric crossed to trigger the alert.")


class PortfolioRiskResponse(BaseModel):
    """Aggregated financial risk alerts across the entire project portfolio."""

    alerts: List[ProjectRiskAlert] = Field(default_factory=list)


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


# ---------------------------------------------------------------------------
# Scenario-based revenue schedule schemas  (PR-FIN-032)
# ---------------------------------------------------------------------------


class RevenueScheduleEntryResponse(BaseModel):
    """Revenue recognized in a single calendar period."""

    period: str = Field(..., description="Calendar month in YYYY-MM format.")
    revenue: float = Field(..., ge=0, description="Revenue recognized in this period.")


class ScenarioRevenueScheduleResponse(BaseModel):
    """Revenue schedule for a development scenario.

    The schedule lists the revenue recognized in each calendar period
    according to the selected recognition strategy.
    """

    scenario_id: str = Field(..., description="Identifier of the originating scenario.")
    strategy: str = Field(
        ...,
        description=(
            "Recognition strategy applied: on_contract_signing, "
            "on_construction_progress, or on_unit_delivery."
        ),
    )
    revenue_schedule: List[RevenueScheduleEntryResponse] = Field(
        default_factory=list,
        description="Chronologically ordered list of period-revenue entries.",
    )
    total_revenue: float = Field(
        ..., ge=0, description="Sum of all period revenues."
    )


# ---------------------------------------------------------------------------
# Construction cashflow forecast schemas  (PR-FIN-034)
# ---------------------------------------------------------------------------


class ConstructionForecastAssumptionsSchema(BaseModel):
    """Assumption parameters for the construction cashflow forecast.

    Attributes
    ----------
    execution_probability:
        Probability (0–1) that planned construction work executes as scheduled.
        Default 1.0 = deterministic full execution.
    spread_method:
        Distribution method for spreading costs across months ("linear" default).
    include_committed:
        When True and committed_amount > 0, committed costs override plan.
    """

    execution_probability: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Probability that planned construction work executes (0–1).",
    )
    spread_method: str = Field(
        default=ConstructionSpreadMethod.LINEAR.value,
        description=(
            "Cost spread method: 'linear' distributes costs uniformly; "
            "'s_curve' is reserved for future use."
        ),
    )
    include_committed: bool = Field(
        default=True,
        description="Use committed costs as the basis for expected_cost when available.",
    )

    @field_validator("execution_probability")
    @classmethod
    def _validate_probability(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("execution_probability must be between 0.0 and 1.0")
        return v

    @field_validator("spread_method")
    @classmethod
    def _validate_spread_method(cls, v: str) -> str:
        allowed = {m.value for m in ConstructionSpreadMethod}
        if v not in allowed:
            raise ValueError(
                f"spread_method '{v}' is not supported. "
                f"Allowed values: {sorted(allowed)}"
            )
        return v


class ConstructionCashflowSummaryResponse(BaseModel):
    """High-level totals across all periods in the construction forecast window."""

    planned_total: float = Field(..., ge=0, description="Total planned construction cost.")
    committed_total: float = Field(..., ge=0, description="Total committed construction cost.")
    expected_total: float = Field(..., ge=0, description="Total expected construction cost.")
    variance_to_plan: float = Field(..., description="expected_total − planned_total.")


class ConstructionCashflowPeriodRow(BaseModel):
    """Per-period construction cashflow row."""

    period_label: str = Field(..., description="Period identifier in YYYY-MM format.")
    planned_cost: float = Field(..., ge=0, description="Planned cost allocated to this period.")
    committed_cost: float = Field(
        ..., ge=0, description="Committed contractor cost allocated to this period."
    )
    expected_cost: float = Field(
        ..., ge=0, description="Expected cost: base_cost × execution_probability."
    )
    variance_to_plan: float = Field(
        ..., description="expected_cost − planned_cost (negative = shortfall)."
    )
    cumulative_cost: float = Field(
        ..., ge=0, description="Running cumulative expected cost from window start."
    )
    cost_item_count: int = Field(
        ..., ge=0, description="Number of cost records contributing to this period."
    )


class ProjectConstructionCashflowResponse(BaseModel):
    """Construction cashflow forecast for a single project.

    Returned by GET /finance/projects/{project_id}/construction-cashflow.
    """

    scope_type: str = Field(default="project")
    project_id: str
    start_date: date
    end_date: date
    granularity: str = Field(default="monthly")
    assumptions: ConstructionForecastAssumptionsSchema
    summary: ConstructionCashflowSummaryResponse
    periods: List[ConstructionCashflowPeriodRow] = Field(default_factory=list)


class PhaseConstructionCashflowResponse(BaseModel):
    """Construction cashflow forecast for a single project phase.

    Returned by GET /finance/phases/{phase_id}/construction-cashflow.
    """

    scope_type: str = Field(default="phase")
    phase_id: str
    start_date: date
    end_date: date
    granularity: str = Field(default="monthly")
    assumptions: ConstructionForecastAssumptionsSchema
    summary: ConstructionCashflowSummaryResponse
    periods: List[ConstructionCashflowPeriodRow] = Field(default_factory=list)


class PortfolioConstructionCashflowResponse(BaseModel):
    """Construction cashflow forecast aggregated across the entire portfolio.

    Returned by GET /finance/portfolio/construction-cashflow.
    """

    scope_type: str = Field(default="portfolio")
    start_date: date
    end_date: date
    granularity: str = Field(default="monthly")
    assumptions: ConstructionForecastAssumptionsSchema
    summary: ConstructionCashflowSummaryResponse
    periods: List[ConstructionCashflowPeriodRow] = Field(default_factory=list)
    project_forecasts: List[ProjectConstructionCashflowResponse] = Field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Construction financing schemas  (PR-FIN-036)
# ---------------------------------------------------------------------------


class ConstructionFinancingAssumptionsSchema(BaseModel):
    """Assumption parameters for the construction financing draw schedule engine.

    Attributes
    ----------
    debt_ratio:
        Proportion of each period's construction cost funded by debt (0–1).
    equity_ratio:
        Proportion of each period's construction cost funded by equity (0–1).
    loan_draw_method:
        Method used to schedule debt drawdowns.  Default "pro_rata".
    equity_injection_method:
        Method used to schedule equity contributions.  Default "pro_rata".
    financing_start_offset:
        Number of periods before financing begins.  Default 0.
    financing_probability:
        Probability (0–1) that financing will be required in each period.
    """

    debt_ratio: float = Field(
        default=DEFAULT_DEBT_RATIO,
        ge=0.0,
        le=1.0,
        description="Proportion of construction cost funded by debt (0–1).",
    )
    equity_ratio: float = Field(
        default=DEFAULT_EQUITY_RATIO,
        ge=0.0,
        le=1.0,
        description="Proportion of construction cost funded by equity (0–1).",
    )
    loan_draw_method: str = Field(
        default=ConstructionLoanDrawMethod.PRO_RATA.value,
        description="Method used to schedule debt drawdowns.",
    )
    equity_injection_method: str = Field(
        default=ConstructionEquityInjectionMethod.PRO_RATA.value,
        description="Method used to schedule equity contributions.",
    )
    financing_start_offset: int = Field(
        default=DEFAULT_FINANCING_START_OFFSET,
        ge=0,
        description="Periods before financing begins (0 = starts immediately).",
    )
    financing_probability: float = Field(
        default=DEFAULT_FINANCING_PROBABILITY,
        ge=0.0,
        le=1.0,
        description="Probability that financing is required in each period (0–1).",
    )

    @field_validator("loan_draw_method")
    @classmethod
    def _validate_loan_draw_method(cls, v: str) -> str:
        allowed = {m.value for m in ConstructionLoanDrawMethod}
        if v not in allowed:
            raise ValueError(
                f"loan_draw_method '{v}' is not supported. "
                f"Allowed values: {sorted(allowed)}"
            )
        pro_rata = ConstructionLoanDrawMethod.PRO_RATA.value
        if v != pro_rata:
            raise ValueError(
                f"loan_draw_method '{v}' is not supported yet. "
                f"Only '{pro_rata}' is currently implemented."
            )
        return v

    @field_validator("equity_injection_method")
    @classmethod
    def _validate_equity_injection_method(cls, v: str) -> str:
        allowed = {m.value for m in ConstructionEquityInjectionMethod}
        if v not in allowed:
            raise ValueError(
                f"equity_injection_method '{v}' is not supported. "
                f"Allowed values: {sorted(allowed)}"
            )
        pro_rata = ConstructionEquityInjectionMethod.PRO_RATA.value
        if v != pro_rata:
            raise ValueError(
                f"equity_injection_method '{v}' is not supported yet. "
                f"Only '{pro_rata}' is currently implemented."
            )
        return v

    @model_validator(mode="after")
    def _validate_ratios_sum_to_one(self) -> "ConstructionFinancingAssumptionsSchema":
        total = self.debt_ratio + self.equity_ratio
        # 1e-6 tolerance accommodates floating-point representation errors
        # (e.g. 0.1 + 0.9 == 0.9999999... in IEEE-754).  Any larger deviation
        # indicates a genuine misconfiguration of the capital stack.
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"debt_ratio ({self.debt_ratio}) + equity_ratio ({self.equity_ratio}) "
                f"must equal 1.0, but got {total:.6f}."
            )
        return self


class ConstructionDrawScheduleSummaryResponse(BaseModel):
    """Aggregated financing totals across all periods in the draw schedule."""

    total_cost: float = Field(..., ge=0, description="Total construction cost financed.")
    total_debt: float = Field(..., ge=0, description="Total debt drawn across all periods.")
    total_equity: float = Field(
        ..., ge=0, description="Total equity contributed across all periods."
    )
    debt_to_cost_ratio: float = Field(
        ..., ge=0, description="Ratio of total debt to total construction cost."
    )
    equity_to_cost_ratio: float = Field(
        ..., ge=0, description="Ratio of total equity to total construction cost."
    )


class ConstructionDrawPeriodRow(BaseModel):
    """Per-period construction financing row."""

    period_label: str = Field(..., description="YYYY-MM label for the period.")
    period_cost: float = Field(..., ge=0, description="Construction cost for this period.")
    debt_draw: float = Field(..., ge=0, description="Debt drawdown allocated to this period.")
    equity_contribution: float = Field(
        ..., ge=0, description="Equity injection allocated to this period."
    )
    cumulative_debt: float = Field(
        ..., ge=0, description="Running cumulative debt drawn up to this period."
    )
    cumulative_equity: float = Field(
        ..., ge=0, description="Running cumulative equity contributed up to this period."
    )


class ProjectConstructionFinancingResponse(BaseModel):
    """Construction financing draw schedule for a single project.

    Returned by GET /finance/projects/{project_id}/construction-financing.
    """

    scope_type: str = Field(default="project")
    project_id: str
    assumptions: ConstructionFinancingAssumptionsSchema
    summary: ConstructionDrawScheduleSummaryResponse
    periods: List[ConstructionDrawPeriodRow] = Field(default_factory=list)


class PhaseConstructionFinancingResponse(BaseModel):
    """Construction financing draw schedule for a single project phase.

    Returned by GET /finance/phases/{phase_id}/construction-financing.
    """

    scope_type: str = Field(default="phase")
    phase_id: str
    assumptions: ConstructionFinancingAssumptionsSchema
    summary: ConstructionDrawScheduleSummaryResponse
    periods: List[ConstructionDrawPeriodRow] = Field(default_factory=list)


class PortfolioConstructionFinancingResponse(BaseModel):
    """Construction financing draw schedule aggregated across the entire portfolio.

    Returned by GET /finance/portfolio/construction-financing.
    """

    scope_type: str = Field(default="portfolio")
    assumptions: ConstructionFinancingAssumptionsSchema
    summary: ConstructionDrawScheduleSummaryResponse
    periods: List[ConstructionDrawPeriodRow] = Field(default_factory=list)
    project_results: List[ProjectConstructionFinancingResponse] = Field(
        default_factory=list
    )
