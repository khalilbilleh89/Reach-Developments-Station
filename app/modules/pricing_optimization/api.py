"""
pricing_optimization.api

Pricing Optimization Engine API router (PR-V7-02).

Endpoints:
  GET /api/v1/projects/{project_id}/pricing-recommendations
    — Per-project demand-responsive pricing recommendations.
  GET /api/v1/portfolio/pricing-insights
    — Portfolio-wide pricing intelligence.

Both endpoints are read-only.  No pricing records are mutated.
Recommendations are deterministic and explainable from source data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.pricing_optimization.schemas import (
    PortfolioPricingInsightsResponse,
    ProjectPricingRecommendationsResponse,
)
from app.modules.pricing_optimization.service import PricingOptimizationService

# Project-scoped router (registered under /api/v1/projects)
projects_router = APIRouter(
    prefix="/projects",
    tags=["Pricing Optimization"],
    dependencies=[Depends(get_current_user_payload)],
)

# Portfolio-scoped router (registered under /api/v1/portfolio)
portfolio_router = APIRouter(
    prefix="/portfolio",
    tags=["Pricing Optimization"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> PricingOptimizationService:
    return PricingOptimizationService(db)


ServiceDep = Annotated[PricingOptimizationService, Depends(_service)]


@projects_router.get(
    "/{project_id}/pricing-recommendations",
    response_model=ProjectPricingRecommendationsResponse,
)
def get_project_pricing_recommendations(
    project_id: str,
    service: ServiceDep,
) -> ProjectPricingRecommendationsResponse:
    """Return demand-responsive pricing recommendations for a project.

    Derives demand classification from absorption velocity vs feasibility plan,
    then applies deterministic pricing rules per unit type.  Recommendations
    account for:
      - Sales velocity (actual vs planned absorption rate)
      - Unit type availability percentage
      - Current average formal pricing records

    All outputs are recommendation-only.  No pricing records are mutated.
    Returns 404 if the project does not exist.
    """
    return service.build_pricing_recommendations(project_id)


@portfolio_router.get(
    "/pricing-insights",
    response_model=PortfolioPricingInsightsResponse,
)
def get_portfolio_pricing_insights(
    service: ServiceDep,
) -> PortfolioPricingInsightsResponse:
    """Return portfolio-wide pricing intelligence.

    Aggregates per-project pricing recommendations into a portfolio view.
    Identifies:
      - Projects that are underpriced (high demand, upward adjustment suggested)
      - Projects that are overpriced (low demand, downward adjustment suggested)
      - Top pricing opportunities and risk zones

    All values are computed live from source records on every request.
    No pricing records are mutated.
    """
    return service.build_portfolio_pricing_insights()
