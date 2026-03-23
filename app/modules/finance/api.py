"""
finance.api

REST endpoints for project-level financial summaries.

Router prefix: /finance
Full path:     /api/v1/finance/...

Endpoints
---------
  GET /finance/portfolio/summary                       — portfolio financial summary
  GET /finance/treasury/monitoring                     — portfolio treasury monitoring
  GET /finance/projects/{project_id}/summary           — project financial summary
  GET /finance/contracts/{contract_id}/revenue         — contract revenue recognition
  GET /finance/projects/{project_id}/revenue-summary   — project revenue recognition summary
  GET /finance/revenue/overview                        — portfolio revenue overview
  GET /finance/contracts/{contract_id}/aging           — contract receivable aging
  GET /finance/projects/{project_id}/aging             — project receivable aging
  GET /finance/receivables/aging-overview              — portfolio receivable aging
  GET /finance/collections/alerts                      — active collections alerts
  POST /finance/collections/alerts/generate            — generate alerts from overdue installments
  POST /finance/collections/alerts/{id}/resolve        — resolve a collections alert
  POST /finance/payments/match-receipt                 — match a payment to installment obligations
  GET /finance/cashflow/forecast                       — portfolio cashflow forecast (legacy)
  GET /finance/cashflow/forecast/project/{project_id} — project cashflow forecast (legacy)
  GET /finance/contracts/{contract_id}/cashflow-forecast — contract cashflow forecast (PR-33)
  GET /finance/projects/{project_id}/cashflow-forecast   — project cashflow forecast (PR-33)
  GET /finance/portfolio/cashflow-forecast               — portfolio cashflow forecast (PR-33)
  POST /finance/analytics/rebuild                      — rebuild analytics fact tables
  GET /finance/analytics/portfolio                     — portfolio analytics dashboard
  GET /finance/projects/{project_id}/dashboard         — project financial dashboard
  GET /finance/alerts/portfolio                        — portfolio risk alerts
  GET /finance/projects/{project_id}/alerts            — project risk alerts
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.finance.schemas import (
    AnalyticsRebuildResponse,
    CashflowForecastAssumptions,
    CollectionsAlertListResponse,
    CollectionsAlertResponse,
    ContractAgingResponse,
    ContractCashflowForecastResponse,
    MatchReceiptRequest,
    PortfolioAgingResponse,
    PortfolioAnalyticsResponse,
    PortfolioCashflowForecastResponse,
    PortfolioCashflowForecastV2Response,
    PortfolioFinancialSummaryResponse,
    PortfolioRevenueOverviewResponse,
    PortfolioRiskResponse,
    ProjectAgingResponse,
    ProjectCashflowForecastResponse,
    ProjectCashflowForecastV2Response,
    ProjectFinanceSummaryResponse,
    ProjectFinancialDashboardResponse,
    ProjectRevenueSummaryResponse,
    ProjectRiskAlert,
    ReceiptMatchResult,
    ResolveAlertRequest,
    RevenueRecognitionResponse,
    TreasuryMonitoringResponse,
)
from app.modules.finance.service import (
    CollectionsAgingService,
    CollectionsAlertService,
    FinanceSummaryService,
    ReceiptMatchingService,
    RevenueRecognitionService,
)
from app.modules.finance.analytics_service import AnalyticsService
from app.modules.finance.analytics_dashboard_service import AnalyticsDashboardService
from app.modules.finance.cashflow_service import CashflowForecastService
from app.modules.auth.security import get_current_user_payload, require_roles
from app.modules.finance.portfolio_summary_service import PortfolioSummaryService
from app.modules.finance.project_financial_dashboard_service import ProjectFinancialDashboardService
from app.modules.finance.risk_alert_engine import FinancialRiskAlertEngine
from app.modules.finance.treasury_monitoring_service import TreasuryMonitoringService
from app.shared.enums.finance import AlertSeverity

router = APIRouter(prefix="/finance", tags=["Finance"], dependencies=[Depends(get_current_user_payload)])


def get_service(db: Session = Depends(get_db)) -> FinanceSummaryService:
    return FinanceSummaryService(db)


def get_revenue_service(db: Session = Depends(get_db)) -> RevenueRecognitionService:
    return RevenueRecognitionService(db)


def get_aging_service(db: Session = Depends(get_db)) -> CollectionsAgingService:
    return CollectionsAgingService(db)


def get_alert_service(db: Session = Depends(get_db)) -> CollectionsAlertService:
    return CollectionsAlertService(db)


def get_matching_service(db: Session = Depends(get_db)) -> ReceiptMatchingService:
    return ReceiptMatchingService(db)


def get_forecast_service(db: Session = Depends(get_db)) -> CashflowForecastService:
    return CashflowForecastService(db)


def get_portfolio_summary_service(
    db: Session = Depends(get_db),
) -> PortfolioSummaryService:
    return PortfolioSummaryService(db)


def get_treasury_monitoring_service(
    db: Session = Depends(get_db),
) -> TreasuryMonitoringService:
    return TreasuryMonitoringService(db)


@router.get(
    "/portfolio/summary",
    response_model=PortfolioFinancialSummaryResponse,
)
def get_portfolio_financial_summary(
    service: Annotated[PortfolioSummaryService, Depends(get_portfolio_summary_service)],
) -> PortfolioFinancialSummaryResponse:
    """Return the consolidated financial summary for the entire portfolio.

    Aggregates recognized revenue, deferred revenue, total receivables,
    overdue receivables, next-month cashflow forecast, and per-project
    financial metrics from the existing financial engines.
    """
    return service.get_portfolio_summary()


@router.get(
    "/treasury/monitoring",
    response_model=TreasuryMonitoringResponse,
)
def get_treasury_monitoring(
    service: Annotated[
        TreasuryMonitoringService, Depends(get_treasury_monitoring_service)
    ],
) -> TreasuryMonitoringResponse:
    """Return the portfolio treasury monitoring snapshot.

    Provides liquidity and exposure indicators derived from the existing
    financial engines (revenue recognition, receivables aging, and cashflow
    forecasting).  Project exposures are ranked by receivable exposure
    descending so the highest-risk projects appear first.
    """
    return service.get_treasury_monitoring()


@router.get(
    "/projects/{project_id}/summary",
    response_model=ProjectFinanceSummaryResponse,
)
def get_project_finance_summary(
    project_id: str,
    service: Annotated[FinanceSummaryService, Depends(get_service)],
) -> ProjectFinanceSummaryResponse:
    """Return the aggregated financial summary for a project."""
    return service.get_project_summary(project_id)


@router.get(
    "/contracts/{contract_id}/revenue",
    response_model=RevenueRecognitionResponse,
)
def get_contract_revenue(
    contract_id: str,
    service: Annotated[RevenueRecognitionService, Depends(get_revenue_service)],
) -> RevenueRecognitionResponse:
    """Return revenue recognition data for a single contract.

    recognized_revenue = sum of all paid installments
    deferred_revenue   = contract_total − recognized_revenue
    """
    return service.get_contract_revenue(contract_id)


@router.get(
    "/projects/{project_id}/revenue-summary",
    response_model=ProjectRevenueSummaryResponse,
)
def get_project_revenue_summary(
    project_id: str,
    service: Annotated[RevenueRecognitionService, Depends(get_revenue_service)],
) -> ProjectRevenueSummaryResponse:
    """Return aggregated revenue recognition for all contracts in a project."""
    return service.get_project_revenue(project_id)


@router.get(
    "/revenue/overview",
    response_model=PortfolioRevenueOverviewResponse,
)
def get_revenue_overview(
    service: Annotated[RevenueRecognitionService, Depends(get_revenue_service)],
) -> PortfolioRevenueOverviewResponse:
    """Return portfolio-wide revenue recognition overview across all projects."""
    return service.get_total_recognized_revenue()


@router.get(
    "/contracts/{contract_id}/aging",
    response_model=ContractAgingResponse,
)
def get_contract_aging(
    contract_id: str,
    service: Annotated[CollectionsAgingService, Depends(get_aging_service)],
) -> ContractAgingResponse:
    """Return receivable aging breakdown for a single contract.

    Outstanding installments are classified into aging buckets based on how
    many days past due they are relative to today.
    """
    return service.get_contract_aging(contract_id)


@router.get(
    "/projects/{project_id}/aging",
    response_model=ProjectAgingResponse,
)
def get_project_aging(
    project_id: str,
    service: Annotated[CollectionsAgingService, Depends(get_aging_service)],
) -> ProjectAgingResponse:
    """Return aggregated receivable aging for all outstanding installments in a project."""
    return service.get_project_aging(project_id)


@router.get(
    "/receivables/aging-overview",
    response_model=PortfolioAgingResponse,
)
def get_receivables_aging_overview(
    service: Annotated[CollectionsAgingService, Depends(get_aging_service)],
) -> PortfolioAgingResponse:
    """Return portfolio-wide receivable aging distribution across all projects."""
    return service.get_portfolio_aging()


# ---------------------------------------------------------------------------
# Collections alerts endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/collections/alerts",
    response_model=CollectionsAlertListResponse,
)
def get_collections_alerts(
    severity: AlertSeverity | None = None,
    service: Annotated[CollectionsAlertService, Depends(get_alert_service)] = ...,
) -> CollectionsAlertListResponse:
    """Return all active (unresolved) collections alerts.

    Optional query parameter:
      - ``severity``: filter by severity (warning | critical | high_risk).
    """
    return service.get_overdue_alerts(severity=severity.value if severity else None)


@router.post(
    "/collections/alerts/generate",
    response_model=CollectionsAlertListResponse,
    status_code=201,
)
def generate_collections_alerts(
    service: Annotated[CollectionsAlertService, Depends(get_alert_service)],
) -> CollectionsAlertListResponse:
    """Scan all outstanding installments and generate collections alerts.

    Existing active alerts are not duplicated.
    Returns the full active alert list after generation.
    """
    return service.generate_alerts()


@router.post(
    "/collections/alerts/{alert_id}/resolve",
    response_model=CollectionsAlertResponse,
)
def resolve_collections_alert(
    alert_id: str,
    data: ResolveAlertRequest,
    service: Annotated[CollectionsAlertService, Depends(get_alert_service)],
) -> CollectionsAlertResponse:
    """Resolve a single collections alert by ID."""
    return service.resolve_alert(alert_id, notes=data.notes)


# ---------------------------------------------------------------------------
# Receipt matching endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/payments/match-receipt",
    response_model=ReceiptMatchResult,
)
def match_payment_receipt(
    request: MatchReceiptRequest,
    service: Annotated[ReceiptMatchingService, Depends(get_matching_service)],
) -> ReceiptMatchResult:
    """Match an incoming payment amount to outstanding installment obligations.

    Returns the matching strategy and per-installment allocation breakdown.
    """
    return service.match_payment(request)


# ---------------------------------------------------------------------------
# Cashflow forecasting endpoints — legacy simple forecast
# ---------------------------------------------------------------------------


@router.get(
    "/cashflow/forecast",
    response_model=PortfolioCashflowForecastResponse,
)
def get_portfolio_cashflow_forecast(
    service: Annotated[CashflowForecastService, Depends(get_forecast_service)],
) -> PortfolioCashflowForecastResponse:
    """Return the portfolio-wide cashflow forecast.

    Aggregates all PENDING and OVERDUE installments across all projects
    and groups expected collections by calendar month.
    """
    return service.get_portfolio_forecast()


@router.get(
    "/cashflow/forecast/project/{project_id}",
    response_model=ProjectCashflowForecastResponse,
)
def get_project_cashflow_forecast(
    project_id: str,
    service: Annotated[CashflowForecastService, Depends(get_forecast_service)],
) -> ProjectCashflowForecastResponse:
    """Return the cashflow forecast for a single project.

    Aggregates all PENDING and OVERDUE installments for the project
    and groups expected collections by calendar month.

    Returns 404 if the project does not exist.
    """
    return service.get_project_forecast(project_id)


# ---------------------------------------------------------------------------
# Cashflow forecasting endpoints — PR-33 comprehensive forecast
# ---------------------------------------------------------------------------


@router.get(
    "/contracts/{contract_id}/cashflow-forecast",
    response_model=ContractCashflowForecastResponse,
    summary="Contract cashflow forecast",
)
def get_contract_cashflow_forecast(
    contract_id: str,
    service: Annotated[CashflowForecastService, Depends(get_forecast_service)],
    start_date: date = Query(..., description="Forecast window start date (YYYY-MM-DD)."),
    end_date: date = Query(..., description="Forecast window end date (YYYY-MM-DD)."),
    collection_probability: float = Query(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Collection probability applied to outstanding installments (0–1).",
    ),
    carry_forward_overdue: bool = Query(
        default=True,
        description="Include pre-window overdue installments in the first period bucket.",
    ),
    include_paid_in_schedule: bool = Query(
        default=True,
        description="Count paid installments in scheduled_amount for completeness.",
    ),
) -> ContractCashflowForecastResponse:
    """Return the comprehensive cashflow forecast for a single contract.

    The forecast separates contractual scheduled amounts from expected
    collections and already-collected amounts, producing a per-period
    breakdown for the requested date window.

    Returns 404 if the contract does not exist.
    Returns 422 if start_date is after end_date.
    """
    assumptions = CashflowForecastAssumptions(
        collection_probability=collection_probability,
        carry_forward_overdue=carry_forward_overdue,
        include_paid_in_schedule=include_paid_in_schedule,
    )
    return service.get_contract_forecast_v2(contract_id, start_date, end_date, assumptions)


@router.get(
    "/projects/{project_id}/cashflow-forecast",
    response_model=ProjectCashflowForecastV2Response,
    summary="Project cashflow forecast",
)
def get_project_cashflow_forecast_v2(
    project_id: str,
    service: Annotated[CashflowForecastService, Depends(get_forecast_service)],
    start_date: date = Query(..., description="Forecast window start date (YYYY-MM-DD)."),
    end_date: date = Query(..., description="Forecast window end date (YYYY-MM-DD)."),
    collection_probability: float = Query(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Collection probability applied to outstanding installments (0–1).",
    ),
    carry_forward_overdue: bool = Query(
        default=True,
        description="Include pre-window overdue installments in the first period bucket.",
    ),
    include_paid_in_schedule: bool = Query(
        default=True,
        description="Count paid installments in scheduled_amount for completeness.",
    ),
) -> ProjectCashflowForecastV2Response:
    """Return the comprehensive cashflow forecast for a single project.

    Aggregates all non-cancelled installments across all contracts in the
    project and produces a monthly scheduled / collected / expected breakdown
    for the requested date window.

    Returns 404 if the project does not exist.
    Returns 422 if start_date is after end_date.
    """
    assumptions = CashflowForecastAssumptions(
        collection_probability=collection_probability,
        carry_forward_overdue=carry_forward_overdue,
        include_paid_in_schedule=include_paid_in_schedule,
    )
    return service.get_project_forecast_v2(project_id, start_date, end_date, assumptions)


@router.get(
    "/portfolio/cashflow-forecast",
    response_model=PortfolioCashflowForecastV2Response,
    summary="Portfolio cashflow forecast",
)
def get_portfolio_cashflow_forecast_v2(
    service: Annotated[CashflowForecastService, Depends(get_forecast_service)],
    start_date: date = Query(..., description="Forecast window start date (YYYY-MM-DD)."),
    end_date: date = Query(..., description="Forecast window end date (YYYY-MM-DD)."),
    collection_probability: float = Query(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Collection probability applied to outstanding installments (0–1).",
    ),
    carry_forward_overdue: bool = Query(
        default=True,
        description="Include pre-window overdue installments in the first period bucket.",
    ),
    include_paid_in_schedule: bool = Query(
        default=True,
        description="Count paid installments in scheduled_amount for completeness.",
    ),
) -> PortfolioCashflowForecastV2Response:
    """Return the comprehensive cashflow forecast across the entire portfolio.

    Aggregates all non-cancelled installments for every project in the portfolio
    and produces monthly scheduled / collected / expected breakdowns alongside
    per-project sub-forecasts for the requested date window.

    Returns 422 if start_date is after end_date.
    """
    assumptions = CashflowForecastAssumptions(
        collection_probability=collection_probability,
        carry_forward_overdue=carry_forward_overdue,
        include_paid_in_schedule=include_paid_in_schedule,
    )
    return service.get_portfolio_forecast_v2(start_date, end_date, assumptions)


# ---------------------------------------------------------------------------
# Analytics fact layer endpoint
# ---------------------------------------------------------------------------


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


@router.post(
    "/analytics/rebuild",
    response_model=AnalyticsRebuildResponse,
    status_code=200,
)
def rebuild_analytics_facts(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    _: Annotated[dict, Depends(require_roles("admin"))],
) -> AnalyticsRebuildResponse:
    """Rebuild all analytics fact tables from the current operational data.

    Rebuilds:
      - fact_revenue        — monthly recognized revenue per project / unit.
      - fact_collections    — payment collections by project / month.
      - fact_receivables_snapshot — receivable aging snapshot per project.

    Admin-only endpoint.  Performs an atomic rebuild of the analytics
    layer and returns a summary of rows inserted into each fact table.
    """
    return service.rebuild_financial_analytics()


# ---------------------------------------------------------------------------
# Analytics dashboard endpoint
# ---------------------------------------------------------------------------


def get_analytics_dashboard_service(
    db: Session = Depends(get_db),
) -> AnalyticsDashboardService:
    return AnalyticsDashboardService(db)


@router.get(
    "/analytics/portfolio",
    response_model=PortfolioAnalyticsResponse,
)
def get_portfolio_analytics(
    service: Annotated[AnalyticsDashboardService, Depends(get_analytics_dashboard_service)],
) -> PortfolioAnalyticsResponse:
    """Return the portfolio analytics dashboard.

    Provides revenue trends, collections trends, receivable exposure trends,
    and portfolio-level KPIs derived from the analytics fact tables.

    Data is sourced exclusively from:
      - fact_revenue              — monthly recognized revenue.
      - fact_collections          — payments received by month.
      - fact_receivables_snapshot — receivable aging snapshots.

    Run POST /finance/analytics/rebuild (admin-only) to refresh the fact tables
    before reading this endpoint.
    """
    return service.get_portfolio_analytics()


# ---------------------------------------------------------------------------
# Project financial dashboard endpoint
# ---------------------------------------------------------------------------


def get_project_financial_dashboard_service(
    db: Session = Depends(get_db),
) -> ProjectFinancialDashboardService:
    return ProjectFinancialDashboardService(db)


@router.get(
    "/projects/{project_id}/dashboard",
    response_model=ProjectFinancialDashboardResponse,
)
def get_project_financial_dashboard(
    project_id: str,
    service: Annotated[
        ProjectFinancialDashboardService,
        Depends(get_project_financial_dashboard_service),
    ],
) -> ProjectFinancialDashboardResponse:
    """Return the full financial dashboard for a single project.

    Composes project-level KPIs and trend series from the existing financial
    engines and analytics fact tables:

      - Recognized revenue and deferred revenue — revenue recognition engine
      - Receivables exposure and overdue breakdown — collections aging engine
      - Next-month cashflow forecast — cashflow forecast engine
      - Collection efficiency, revenue trend, collections trend,
        receivables trend — analytics fact tables

    Returns 404 if the project does not exist.
    Auth required.
    """
    return service.get_project_financial_dashboard(project_id)


# ---------------------------------------------------------------------------
# Financial risk alert endpoints
# ---------------------------------------------------------------------------


def get_risk_alert_engine(
    db: Session = Depends(get_db),
) -> FinancialRiskAlertEngine:
    return FinancialRiskAlertEngine(db)


@router.get(
    "/alerts/portfolio",
    response_model=PortfolioRiskResponse,
)
def get_portfolio_risk_alerts(
    service: Annotated[FinancialRiskAlertEngine, Depends(get_risk_alert_engine)],
) -> PortfolioRiskResponse:
    """Return financial risk alerts for the entire portfolio.

    Scans all projects and produces structured risk alerts for conditions such
    as:

      - High overdue exposure (overdue_percentage > 20 %)
      - Collection efficiency collapse (collection_efficiency < 60 %)
      - Receivables surge (growth > 30 % from prior snapshot)
      - Liquidity stress (forecast < 25 % of receivables exposure)

    Auth required.
    """
    return service.scan_portfolio_risks()


@router.get(
    "/projects/{project_id}/alerts",
    response_model=list[ProjectRiskAlert],
)
def get_project_risk_alerts(
    project_id: str,
    service: Annotated[FinancialRiskAlertEngine, Depends(get_risk_alert_engine)],
) -> list[ProjectRiskAlert]:
    """Return financial risk alerts for a single project.

    Returns 404 if the project does not exist.
    Auth required.
    """
    return service.scan_project_risks(project_id)
