"""
phasing_optimization.api

Phasing Optimization Engine API router (PR-V7-03).

Endpoints:
  GET /api/v1/projects/{project_id}/phasing-recommendations
    — Per-project phasing and inventory-release recommendations.
  GET /api/v1/portfolio/phasing-insights
    — Portfolio-wide phasing intelligence.

Both endpoints are read-only.  No phase or inventory records are mutated.
Recommendations are deterministic and explainable from source data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.phasing_optimization.schemas import (
    PortfolioPhasingInsightsResponse,
    ProjectPhasingRecommendationResponse,
)
from app.modules.phasing_optimization.service import PhasingOptimizationService

# Project-scoped router (registered under /api/v1/projects)
projects_router = APIRouter(
    prefix="/projects",
    tags=["Phasing Optimization"],
    dependencies=[Depends(get_current_user_payload)],
)

# Portfolio-scoped router (registered under /api/v1/portfolio)
portfolio_router = APIRouter(
    prefix="/portfolio",
    tags=["Phasing Optimization"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> PhasingOptimizationService:
    return PhasingOptimizationService(db)


ServiceDep = Annotated[PhasingOptimizationService, Depends(_service)]


@projects_router.get(
    "/{project_id}/phasing-recommendations",
    response_model=ProjectPhasingRecommendationResponse,
)
def get_project_phasing_recommendations(
    project_id: str,
    service: ServiceDep,
) -> ProjectPhasingRecommendationResponse:
    """Return deterministic phasing recommendations for a project.

    Derives demand classification from absorption velocity vs feasibility plan,
    identifies the current active phase, and applies deterministic phasing rules.
    Recommendations account for:
      - Sales demand (actual vs planned absorption rate)
      - Current phase inventory availability
      - Next phase readiness
      - Project baseline governance state

    All outputs are recommendation-only.  No phase or inventory records are mutated.
    Returns 404 if the project does not exist.
    """
    return service.build_project_phasing_recommendations(project_id)


@portfolio_router.get(
    "/phasing-insights",
    response_model=PortfolioPhasingInsightsResponse,
)
def get_portfolio_phasing_insights(
    service: ServiceDep,
) -> PortfolioPhasingInsightsResponse:
    """Return portfolio-wide phasing intelligence.

    Aggregates per-project phasing recommendations into a portfolio view.
    Identifies:
      - Projects that should prepare the next phase (high demand, low inventory)
      - Projects that should hold inventory (low demand)
      - Projects that should delay further releases (low demand, high unsold stock)
      - Projects with insufficient data

    All values are computed live from source records on every request.
    No phase records are mutated.
    """
    return service.build_portfolio_phasing_insights()
