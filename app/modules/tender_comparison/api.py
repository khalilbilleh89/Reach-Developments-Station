"""
tender_comparison.api

Auth-protected REST API for the Tender Comparison & Cost Variance domain.

Endpoints
---------
GET    /api/v1/projects/{project_id}/tender-comparisons
POST   /api/v1/projects/{project_id}/tender-comparisons
GET    /api/v1/projects/{project_id}/tender-comparisons/active-baseline
GET    /api/v1/tender-comparisons/{set_id}
PATCH  /api/v1/tender-comparisons/{set_id}
GET    /api/v1/tender-comparisons/{set_id}/summary
POST   /api/v1/tender-comparisons/{set_id}/approve-baseline
POST   /api/v1/tender-comparisons/{set_id}/lines
PATCH  /api/v1/tender-comparisons/lines/{line_id}
DELETE /api/v1/tender-comparisons/lines/{line_id}

All routes require authentication.
No write-back to feasibility, finance, or construction cost records.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.tender_comparison.schemas import (
    ActiveTenderBaselineResponse,
    ConstructionCostComparisonLineCreate,
    ConstructionCostComparisonLineResponse,
    ConstructionCostComparisonLineUpdate,
    ConstructionCostComparisonSetCreate,
    ConstructionCostComparisonSetList,
    ConstructionCostComparisonSetResponse,
    ConstructionCostComparisonSetUpdate,
    ConstructionCostComparisonSummaryResponse,
)
from app.modules.tender_comparison.service import TenderComparisonService

router = APIRouter(
    tags=["Tender Comparisons"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]
UserPayloadDep = Annotated[dict, Depends(get_current_user_payload)]


def _service(db: DbDep) -> TenderComparisonService:
    return TenderComparisonService(db)


ServiceDep = Annotated[TenderComparisonService, Depends(_service)]


# ---------------------------------------------------------------------------
# Project-scoped endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/tender-comparisons",
    response_model=ConstructionCostComparisonSetList,
)
def list_tender_comparisons(
    project_id: str,
    service: ServiceDep,
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ConstructionCostComparisonSetList:
    return service.list_sets(project_id, is_active=is_active, skip=skip, limit=limit)


@router.post(
    "/projects/{project_id}/tender-comparisons",
    response_model=ConstructionCostComparisonSetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tender_comparison(
    project_id: str,
    data: ConstructionCostComparisonSetCreate,
    service: ServiceDep,
) -> ConstructionCostComparisonSetResponse:
    return service.create_set(project_id, data)


@router.get(
    "/projects/{project_id}/tender-comparisons/active-baseline",
    response_model=ActiveTenderBaselineResponse,
)
def get_project_active_baseline(
    project_id: str,
    service: ServiceDep,
) -> ActiveTenderBaselineResponse:
    """Return the currently approved tender baseline for a project.

    Returns has_approved_baseline=False and baseline=null when no baseline
    has been approved yet.
    """
    return service.get_project_active_baseline(project_id)


# ---------------------------------------------------------------------------
# Set-level endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/tender-comparisons/{set_id}",
    response_model=ConstructionCostComparisonSetResponse,
)
def get_tender_comparison(
    set_id: str,
    service: ServiceDep,
) -> ConstructionCostComparisonSetResponse:
    return service.get_set(set_id)


@router.patch(
    "/tender-comparisons/{set_id}",
    response_model=ConstructionCostComparisonSetResponse,
)
def update_tender_comparison(
    set_id: str,
    data: ConstructionCostComparisonSetUpdate,
    service: ServiceDep,
) -> ConstructionCostComparisonSetResponse:
    return service.update_set(set_id, data)


@router.get(
    "/tender-comparisons/{set_id}/summary",
    response_model=ConstructionCostComparisonSummaryResponse,
)
def get_tender_comparison_summary(
    set_id: str,
    service: ServiceDep,
) -> ConstructionCostComparisonSummaryResponse:
    return service.get_set_summary(set_id)


@router.post(
    "/tender-comparisons/{set_id}/approve-baseline",
    response_model=ConstructionCostComparisonSetResponse,
)
def approve_tender_baseline(
    set_id: str,
    service: ServiceDep,
    payload: UserPayloadDep,
) -> ConstructionCostComparisonSetResponse:
    """Approve a comparison set as the official project baseline.

    Atomically deactivates any existing approved baseline for the same project
    and marks this comparison set as the new approved baseline.

    The action is recorded with the authenticated user's ID and a UTC
    timestamp.

    Approving an already-active baseline is idempotent: the approval metadata
    is refreshed and the updated record is returned.
    """
    user_id: str = payload.get("sub", "")
    return service.approve_tender_baseline(set_id, user_id)


# ---------------------------------------------------------------------------
# Line endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/tender-comparisons/{set_id}/lines",
    response_model=ConstructionCostComparisonLineResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comparison_line(
    set_id: str,
    data: ConstructionCostComparisonLineCreate,
    service: ServiceDep,
) -> ConstructionCostComparisonLineResponse:
    return service.create_line(set_id, data)


@router.patch(
    "/tender-comparisons/lines/{line_id}",
    response_model=ConstructionCostComparisonLineResponse,
)
def update_comparison_line(
    line_id: str,
    data: ConstructionCostComparisonLineUpdate,
    service: ServiceDep,
) -> ConstructionCostComparisonLineResponse:
    return service.update_line(line_id, data)


@router.delete(
    "/tender-comparisons/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_comparison_line(
    line_id: str,
    service: ServiceDep,
) -> None:
    service.delete_line(line_id)
