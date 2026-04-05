"""
adaptive_strategy.api

Adaptive Strategy Influence Layer API router (PR-V7-12).

Endpoints:
  GET /api/v1/projects/{project_id}/adaptive-strategy
    — Return confidence-adjusted strategy recommendation for a project.
  GET /api/v1/portfolio/adaptive-strategy
    — Return portfolio-level adaptive strategy summary.

Forbidden
---------
  Write / mutation endpoints.
  Execution triggers.
  Ranking logic in the router layer.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.adaptive_strategy.schemas import (
    AdaptiveStrategyResponse,
    PortfolioAdaptiveStrategySummaryResponse,
)
from app.modules.adaptive_strategy.service import AdaptiveStrategyService

projects_router = APIRouter(
    prefix="/projects",
    tags=["Adaptive Strategy"],
    dependencies=[Depends(get_current_user_payload)],
)

portfolio_router = APIRouter(
    prefix="/portfolio",
    tags=["Adaptive Strategy"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> AdaptiveStrategyService:
    return AdaptiveStrategyService(db)


ServiceDep = Annotated[AdaptiveStrategyService, Depends(_service)]


# ---------------------------------------------------------------------------
# Project endpoint
# ---------------------------------------------------------------------------


@projects_router.get(
    "/{project_id}/adaptive-strategy",
    response_model=AdaptiveStrategyResponse,
)
def get_project_adaptive_strategy(
    project_id: str,
    service: ServiceDep,
) -> AdaptiveStrategyResponse:
    """Return the confidence-adjusted strategy recommendation for a project.

    Reads raw simulation output and stored learning metrics, applies bounded
    confidence influence to re-rank candidate strategies, and returns both
    the raw best and the adaptive best so leadership can compare both.

    Returns HTTP 404 when the project does not exist.
    """
    return service.get_project_adaptive_strategy(project_id)


# ---------------------------------------------------------------------------
# Portfolio endpoint
# ---------------------------------------------------------------------------


@portfolio_router.get(
    "/adaptive-strategy",
    response_model=PortfolioAdaptiveStrategySummaryResponse,
)
def get_portfolio_adaptive_strategy(
    service: ServiceDep,
) -> PortfolioAdaptiveStrategySummaryResponse:
    """Return portfolio-level adaptive strategy summary.

    Provides:
      - Total projects evaluated
      - High / low confidence project counts
      - Projects where confidence shifted the recommendation
      - Top confident recommendations
      - Top low-confidence projects requiring attention
      - Full project card list ordered by confidence descending
    """
    return service.build_portfolio_adaptive_strategy_summary()
