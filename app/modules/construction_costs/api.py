"""
construction_costs.api

CRUD API router for project Construction Cost Records.

Endpoints
---------
GET    /api/v1/projects/{project_id}/construction-cost-records
POST   /api/v1/projects/{project_id}/construction-cost-records
GET    /api/v1/projects/{project_id}/construction-cost-records/summary
GET    /api/v1/projects/{project_id}/construction-scorecard
GET    /api/v1/construction-cost-records/{record_id}
PATCH  /api/v1/construction-cost-records/{record_id}
POST   /api/v1/construction-cost-records/{record_id}/archive
GET    /api/v1/construction/portfolio/scorecards

All routes require authentication.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.construction_costs.analytics_schemas import (
    ConstructionPortfolioScorecardsResponse,
    ConstructionProjectScorecardResponse,
)
from app.modules.construction_costs.analytics_service import ConstructionAnalyticsService
from app.modules.construction_costs.schemas import (
    ConstructionCostRecordCreate,
    ConstructionCostRecordList,
    ConstructionCostRecordResponse,
    ConstructionCostRecordUpdate,
    ConstructionCostSummaryResponse,
)
from app.modules.construction_costs.service import ConstructionCostService
from app.shared.enums.construction_costs import CostCategory, CostStage

router = APIRouter(
    tags=["Construction Cost Records"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> ConstructionCostService:
    return ConstructionCostService(db)


def _analytics_service(db: DbDep) -> ConstructionAnalyticsService:
    return ConstructionAnalyticsService(db)


ServiceDep = Annotated[ConstructionCostService, Depends(_service)]
AnalyticsServiceDep = Annotated[ConstructionAnalyticsService, Depends(_analytics_service)]


# ---------------------------------------------------------------------------
# Project-scoped endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/construction-cost-records",
    response_model=ConstructionCostRecordList,
)
def list_construction_cost_records(
    project_id: str,
    service: ServiceDep,
    is_active: Optional[bool] = Query(default=None),
    cost_category: Optional[CostCategory] = Query(default=None),
    cost_stage: Optional[CostStage] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ConstructionCostRecordList:
    return service.list_records(
        project_id,
        is_active=is_active,
        cost_category=cost_category,
        cost_stage=cost_stage,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/projects/{project_id}/construction-cost-records",
    response_model=ConstructionCostRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_construction_cost_record(
    project_id: str,
    data: ConstructionCostRecordCreate,
    service: ServiceDep,
) -> ConstructionCostRecordResponse:
    return service.create_record(project_id, data)


@router.get(
    "/projects/{project_id}/construction-cost-records/summary",
    response_model=ConstructionCostSummaryResponse,
)
def get_construction_cost_summary(
    project_id: str,
    service: ServiceDep,
) -> ConstructionCostSummaryResponse:
    return service.get_project_summary(project_id)


@router.get(
    "/projects/{project_id}/construction-scorecard",
    response_model=ConstructionProjectScorecardResponse,
)
def get_project_construction_scorecard(
    project_id: str,
    service: AnalyticsServiceDep,
) -> ConstructionProjectScorecardResponse:
    """Return the construction health scorecard for a project.

    Computes baseline-vs-actual cost variance, contingency pressure, and
    overall health status from the project's approved tender baseline and
    active construction cost records.

    Returns an incomplete-state scorecard when no approved baseline exists.
    """
    return service.build_project_construction_scorecard(project_id)


# ---------------------------------------------------------------------------
# Record-level endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/construction-cost-records/{record_id}",
    response_model=ConstructionCostRecordResponse,
)
def get_construction_cost_record(
    record_id: str,
    service: ServiceDep,
) -> ConstructionCostRecordResponse:
    return service.get_record(record_id)


@router.patch(
    "/construction-cost-records/{record_id}",
    response_model=ConstructionCostRecordResponse,
)
def update_construction_cost_record(
    record_id: str,
    data: ConstructionCostRecordUpdate,
    service: ServiceDep,
) -> ConstructionCostRecordResponse:
    return service.update_record(record_id, data)


@router.post(
    "/construction-cost-records/{record_id}/archive",
    response_model=ConstructionCostRecordResponse,
)
def archive_construction_cost_record(
    record_id: str,
    service: ServiceDep,
) -> ConstructionCostRecordResponse:
    return service.archive_record(record_id)


# ---------------------------------------------------------------------------
# Portfolio construction scorecards endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/construction/portfolio/scorecards",
    response_model=ConstructionPortfolioScorecardsResponse,
)
def get_portfolio_construction_scorecards(
    service: AnalyticsServiceDep,
) -> ConstructionPortfolioScorecardsResponse:
    """Return construction health scorecards for all projects.

    Aggregates project-level construction scorecards into a portfolio-wide
    summary.  Includes health status counts, ordered project list, top-risk
    projects, and projects missing an approved baseline.

    All values are computed live from source records on every request.
    """
    return service.build_portfolio_construction_scorecards()
