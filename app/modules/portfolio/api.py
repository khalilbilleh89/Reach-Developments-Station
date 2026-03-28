"""
portfolio.api

Portfolio Intelligence API router.

Endpoints:
  GET /api/v1/portfolio/dashboard                — read-only portfolio dashboard
  GET /api/v1/portfolio/cost-variance            — read-only portfolio cost variance roll-up
  GET /api/v1/portfolio/construction-scorecards  — construction health scorecards (PR-V6-14)

The endpoints assemble coherent payloads from existing source-of-truth
module data.  No source records are mutated.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.construction_costs.analytics_schemas import (
    ConstructionPortfolioScorecardsResponse,
)
from app.modules.construction_costs.analytics_service import ConstructionAnalyticsService
from app.modules.portfolio.schemas import (
    PortfolioCostVarianceResponse,
    PortfolioDashboardResponse,
)
from app.modules.portfolio.service import PortfolioService

router = APIRouter(
    prefix="/portfolio",
    tags=["Portfolio Intelligence"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> PortfolioService:
    return PortfolioService(db)


def _analytics_service(db: DbDep) -> ConstructionAnalyticsService:
    return ConstructionAnalyticsService(db)


ServiceDep = Annotated[PortfolioService, Depends(_service)]
AnalyticsServiceDep = Annotated[ConstructionAnalyticsService, Depends(_analytics_service)]


@router.get("/dashboard", response_model=PortfolioDashboardResponse)
def get_dashboard(service: ServiceDep) -> PortfolioDashboardResponse:
    """Return the portfolio intelligence dashboard.

    Aggregates project, unit, sales, collections, and pipeline data into a
    single read-only dashboard response.  Suitable for executive views and
    portfolio monitoring.
    """
    return service.get_dashboard()


@router.get("/cost-variance", response_model=PortfolioCostVarianceResponse)
def get_cost_variance(service: ServiceDep) -> PortfolioCostVarianceResponse:
    """Return the portfolio cost variance roll-up.

    Aggregates tender comparison data from all active comparison sets across
    projects into a single read-only response.  Includes portfolio-wide
    summary totals, per-project variance cards, top overrun/saving lists,
    and cost variance flags.

    Source tender comparison records are never mutated.
    """
    return service.get_cost_variance()


@router.get(
    "/construction-scorecards",
    response_model=ConstructionPortfolioScorecardsResponse,
)
def get_construction_scorecards(
    service: AnalyticsServiceDep,
) -> ConstructionPortfolioScorecardsResponse:
    """Return construction health scorecards for all projects.

    Computes baseline-vs-actual construction health for every project and
    aggregates the results into a portfolio-level view.  Includes:
      - Health status counts (healthy / warning / critical / incomplete)
      - Per-project scorecard items ordered by severity
      - Top-risk projects requiring executive attention
      - Projects missing an approved baseline

    All values are computed live from governed source records on every request.
    Source records are never mutated.
    """
    return service.build_portfolio_construction_scorecards()
