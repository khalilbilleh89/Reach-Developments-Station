"""
strategy_learning.api

Strategy Learning & Confidence Recalibration API router (PR-V7-11).

Endpoints:
  POST /api/v1/projects/{project_id}/strategy-learning/recalibrate
    — Recompute and persist learning metrics for a project.
  GET  /api/v1/projects/{project_id}/strategy-learning
    — Return current stored learning metrics for a project.
  GET  /api/v1/portfolio/strategy-learning
    — Return portfolio-level learning summary.

Forbidden
---------
  Mutating outcome, trigger, approval, or strategy source records.
  Auto-tuning strategy_generator outputs.
  Introducing ML or external scoring services.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.strategy_learning.schemas import (
    PortfolioLearningSummaryResponse,
    StrategyLearningResponse,
)
from app.modules.strategy_learning.service import StrategyLearningService

projects_router = APIRouter(
    prefix="/projects",
    tags=["Strategy Learning"],
    dependencies=[Depends(get_current_user_payload)],
)

portfolio_router = APIRouter(
    prefix="/portfolio",
    tags=["Strategy Learning"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> StrategyLearningService:
    return StrategyLearningService(db)


ServiceDep = Annotated[StrategyLearningService, Depends(_service)]


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------


@projects_router.post(
    "/{project_id}/strategy-learning/recalibrate",
    response_model=StrategyLearningResponse,
    status_code=200,
)
def recalibrate_project_learning(
    project_id: str,
    service: ServiceDep,
) -> StrategyLearningResponse:
    """Recompute and persist strategy learning metrics for a project.

    Reads all recorded execution outcomes for the project, derives deterministic
    accuracy and confidence scores, upserts StrategyLearningMetrics rows, and
    returns the updated learning panel payload.

    Returns HTTP 404 when the project does not exist.
    """
    return service.recalibrate_project(project_id)


@projects_router.get(
    "/{project_id}/strategy-learning",
    response_model=StrategyLearningResponse,
)
def get_project_strategy_learning(
    project_id: str,
    service: ServiceDep,
) -> StrategyLearningResponse:
    """Return the current stored strategy learning metrics for a project.

    Returns the confidence score, accuracy breakdown, and trend indicator.
    Returns an empty payload (has_sufficient_data=False) when no metrics have
    been computed yet.

    Returns HTTP 404 when the project does not exist.
    """
    return service.get_project_learning(project_id)


# ---------------------------------------------------------------------------
# Portfolio endpoint
# ---------------------------------------------------------------------------


@portfolio_router.get(
    "/strategy-learning",
    response_model=PortfolioLearningSummaryResponse,
)
def get_portfolio_strategy_learning(
    service: ServiceDep,
) -> PortfolioLearningSummaryResponse:
    """Return portfolio-level strategy learning summary.

    Provides:
      - Total projects with learning data
      - Average confidence score
      - High / low confidence counts
      - Improving / declining trend counts
      - Top performing strategy patterns (by confidence score)
      - Weak-area projects (lowest confidence)
      - All project learning entries
    """
    return service.get_portfolio_learning()
