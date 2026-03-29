"""
strategy_generator.api

Automated Strategy Generator API router (PR-V7-05).

Endpoints:
  GET /api/v1/projects/{project_id}/recommended-strategy
    — Generate and rank candidate strategies; return best strategy + top 3.
  GET /api/v1/portfolio/strategy-insights
    — Portfolio-wide strategy intelligence aggregated across all projects.

Both endpoints are read-only.  No source records are mutated.
Strategy outputs are never persisted.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.strategy_generator.schemas import (
    PortfolioStrategyInsightsResponse,
    RecommendedStrategyResponse,
)
from app.modules.strategy_generator.service import StrategyGeneratorService

# Project-scoped router (registered under /api/v1/projects)
projects_router = APIRouter(
    prefix="/projects",
    tags=["Strategy Generator"],
    dependencies=[Depends(get_current_user_payload)],
)

# Portfolio-scoped router (registered under /api/v1/portfolio)
portfolio_router = APIRouter(
    prefix="/portfolio",
    tags=["Strategy Generator"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> StrategyGeneratorService:
    return StrategyGeneratorService(db)


ServiceDep = Annotated[StrategyGeneratorService, Depends(_service)]


@projects_router.get(
    "/{project_id}/recommended-strategy",
    response_model=RecommendedStrategyResponse,
)
def get_recommended_strategy(
    project_id: str,
    service: ServiceDep,
) -> RecommendedStrategyResponse:
    """Generate and rank candidate release strategies for a project.

    Produces candidate scenarios from the cross-product of price adjustments,
    phase delays, and release strategies.  Runs each through the simulation
    engine, then ranks by:
      1. IRR descending (higher = better)
      2. risk_score ascending ('low' < 'medium' < 'high')
      3. cashflow_delay_months ascending (less delay = better)

    Response includes:
    - best_strategy    — top-ranked SimulationResult
    - top_strategies   — top 3 ranked strategies
    - reason           — human-readable recommendation explanation
    - generated_scenario_count — number of candidate scenarios evaluated

    All values are derived from the latest calculated feasibility run.
    No source records are mutated.  Returns 404 if the project does not exist.
    """
    return service.generate_recommended_strategy(project_id)


@portfolio_router.get(
    "/strategy-insights",
    response_model=PortfolioStrategyInsightsResponse,
)
def get_portfolio_strategy_insights(
    service: ServiceDep,
) -> PortfolioStrategyInsightsResponse:
    """Return portfolio-wide strategy intelligence.

    Runs the strategy recommendation engine for every project and aggregates
    results into a portfolio view.  Identifies:
      - Top-performing projects by simulated IRR (top_strategies)
      - Projects requiring intervention due to high-risk best strategy
        (intervention_required)
      - Summary counts (with-baseline, high-risk, low-risk)

    All values are computed live from source records on every request.
    No source records are mutated.
    """
    return service.build_portfolio_strategy_insights()
