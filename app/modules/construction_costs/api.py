"""
construction_costs.api

CRUD API router for project Construction Cost Records.

Endpoints
---------
GET    /api/v1/projects/{project_id}/construction-cost-records
POST   /api/v1/projects/{project_id}/construction-cost-records
GET    /api/v1/projects/{project_id}/construction-cost-records/summary
GET    /api/v1/construction-cost-records/{record_id}
PATCH  /api/v1/construction-cost-records/{record_id}
POST   /api/v1/construction-cost-records/{record_id}/archive

All routes require authentication.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
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


ServiceDep = Annotated[ConstructionCostService, Depends(_service)]


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
