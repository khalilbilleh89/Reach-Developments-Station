"""
portfolio_auto_strategy.api

Portfolio Auto-Strategy & Intervention Prioritization API router (PR-V7-06).

Endpoints:
  GET /api/v1/portfolio/auto-strategy
    — Portfolio-level intervention prioritization and action summary.

The endpoint is read-only.  No strategy decisions are persisted and no source
records are mutated.  All values are computed live on every request.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.portfolio_auto_strategy.schemas import PortfolioAutoStrategyResponse
from app.modules.portfolio_auto_strategy.service import PortfolioAutoStrategyService

router = APIRouter(
    prefix="/portfolio",
    tags=["Portfolio Auto-Strategy"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> PortfolioAutoStrategyService:
    return PortfolioAutoStrategyService(db)


ServiceDep = Annotated[PortfolioAutoStrategyService, Depends(_service)]


@router.get(
    "/auto-strategy",
    response_model=PortfolioAutoStrategyResponse,
)
def get_portfolio_auto_strategy(
    service: ServiceDep,
) -> PortfolioAutoStrategyResponse:
    """Return portfolio-level intervention prioritization.

    Aggregates per-project strategy outputs (PR-V7-05) into a ranked
    portfolio intervention view.  Identifies:
      - Projects requiring urgent intervention
      - Projects with recommended intervention
      - Projects to monitor closely
      - Stable projects that can be left alone
      - Projects with insufficient data

    Surfaces:
      - Top 5 portfolio actions by urgency score
      - Top 5 high-risk projects
      - Top 5 upside opportunities by best IRR

    All values are computed live from source records.
    No records are mutated.
    """
    return service.build_portfolio_auto_strategy()
