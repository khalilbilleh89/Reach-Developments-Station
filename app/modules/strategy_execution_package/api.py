"""
strategy_execution_package.api

Strategy Execution Package Generator API router (PR-V7-07).

Endpoints:
  GET /api/v1/projects/{project_id}/strategy-execution-package
    — Project-level execution-ready action package.
  GET /api/v1/portfolio/execution-packages
    — Portfolio-level packaged intervention outputs.

Both endpoints are read-only.  No strategy decisions are persisted and no
source records are mutated.  All values are computed live on every request.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.strategy_execution_package.schemas import (
    PortfolioExecutionPackageResponse,
    ProjectStrategyExecutionPackageResponse,
)
from app.modules.strategy_execution_package.service import StrategyExecutionPackageService

projects_router = APIRouter(
    prefix="/projects",
    tags=["Strategy Execution Package"],
    dependencies=[Depends(get_current_user_payload)],
)

portfolio_router = APIRouter(
    prefix="/portfolio",
    tags=["Strategy Execution Package"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> StrategyExecutionPackageService:
    return StrategyExecutionPackageService(db)


ServiceDep = Annotated[StrategyExecutionPackageService, Depends(_service)]


@projects_router.get(
    "/{project_id}/strategy-execution-package",
    response_model=ProjectStrategyExecutionPackageResponse,
)
def get_project_strategy_execution_package(
    project_id: str,
    service: ServiceDep,
) -> ProjectStrategyExecutionPackageResponse:
    """Return the strategy execution package for a single project.

    Translates the recommended strategy (PR-V7-05) into a structured,
    execution-ready action bundle.  Includes:
      - Execution readiness classification
      - Ordered action steps with urgency and review flags
      - Dependency checks (feasibility baseline, strategy data)
      - Caution notes (risk level, missing baseline, phase delay)
      - Supporting simulation metrics
      - Expected impact summary

    Returns HTTP 404 when the project does not exist.
    All values are computed live from source records.
    No records are mutated.
    """
    return service.get_project_execution_package(project_id)


@portfolio_router.get(
    "/execution-packages",
    response_model=PortfolioExecutionPackageResponse,
)
def get_portfolio_execution_packages(
    service: ServiceDep,
) -> PortfolioExecutionPackageResponse:
    """Return portfolio-level execution packages for all projects.

    For each project, translates the recommended strategy into an execution-
    ready compact intervention card.  Portfolio outputs include:
      - Summary KPI counts by execution readiness
      - Top 5 projects ready for review (highest urgency first)
      - Top 5 blocked projects (needs baseline resolution)
      - Top 5 high-risk packages (caution required)
      - All project execution package cards

    All values are computed live from source records.
    No records are mutated.
    """
    return service.build_portfolio_execution_packages()
