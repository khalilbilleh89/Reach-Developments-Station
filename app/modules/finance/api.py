"""
finance.api

REST endpoints for project-level financial summaries.

Router prefix: /finance
Full path:     /api/v1/finance/...

Endpoints
---------
  GET /finance/projects/{project_id}/summary           — project financial summary
  GET /finance/contracts/{contract_id}/revenue         — contract revenue recognition
  GET /finance/projects/{project_id}/revenue-summary   — project revenue recognition summary
  GET /finance/revenue/overview                        — portfolio revenue overview
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.finance.schemas import (
    PortfolioRevenueOverviewResponse,
    ProjectFinanceSummaryResponse,
    ProjectRevenueSummaryResponse,
    RevenueRecognitionResponse,
)
from app.modules.finance.service import FinanceSummaryService, RevenueRecognitionService

router = APIRouter(prefix="/finance", tags=["Finance"])


def get_service(db: Session = Depends(get_db)) -> FinanceSummaryService:
    return FinanceSummaryService(db)


def get_revenue_service(db: Session = Depends(get_db)) -> RevenueRecognitionService:
    return RevenueRecognitionService(db)


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
