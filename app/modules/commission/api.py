"""
commission.api

REST API router for the Commission module.

Router prefix: /commission
Full prefix:   /api/v1/commission/...

Endpoints
---------
  POST  /api/v1/commission/plans
  GET   /api/v1/commission/plans/{plan_id}
  GET   /api/v1/commission/projects/{project_id}/plans

  POST  /api/v1/commission/plans/{plan_id}/slabs
  GET   /api/v1/commission/plans/{plan_id}/slabs

  POST  /api/v1/commission/payouts/calculate
  GET   /api/v1/commission/payouts/{payout_id}
  GET   /api/v1/commission/projects/{project_id}/payouts
  GET   /api/v1/commission/projects/{project_id}/summary

  POST  /api/v1/commission/payouts/{payout_id}/approve
"""

from typing import Annotated, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.commission.schemas import (
    CommissionPayoutListResponse,
    CommissionPayoutRequest,
    CommissionPayoutResponse,
    CommissionPlanCreate,
    CommissionPlanResponse,
    CommissionSlabCreate,
    CommissionSlabResponse,
    CommissionSummaryResponse,
)
from app.modules.commission.service import CommissionService

router = APIRouter(prefix="/commission", tags=["commission"], dependencies=[Depends(get_current_user_payload)])


def get_service(db: Session = Depends(get_db)) -> CommissionService:
    return CommissionService(db)


# ---------------------------------------------------------------------------
# Project-scoped views (declared before /{plan_id} to avoid path conflicts)
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/plans",
    response_model=List[CommissionPlanResponse],
)
def list_project_plans(
    project_id: str,
    service: Annotated[CommissionService, Depends(get_service)],
) -> List[CommissionPlanResponse]:
    """List all commission plans for a project."""
    return service.list_plans_by_project(project_id)


@router.get(
    "/projects/{project_id}/payouts",
    response_model=CommissionPayoutListResponse,
)
def list_project_payouts(
    project_id: str,
    service: Annotated[CommissionService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> CommissionPayoutListResponse:
    """List all commission payouts for a project."""
    return service.list_payouts_by_project(project_id, skip=skip, limit=limit)


@router.get(
    "/projects/{project_id}/summary",
    response_model=CommissionSummaryResponse,
)
def get_project_summary(
    project_id: str,
    service: Annotated[CommissionService, Depends(get_service)],
) -> CommissionSummaryResponse:
    """Aggregate commission analytics for a project."""
    return service.get_project_summary(project_id)


# ---------------------------------------------------------------------------
# Plan CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/plans",
    response_model=CommissionPlanResponse,
    status_code=201,
)
def create_plan(
    data: CommissionPlanCreate,
    service: Annotated[CommissionService, Depends(get_service)],
) -> CommissionPlanResponse:
    """Create a new commission plan for a project."""
    return service.create_plan(data)


@router.get(
    "/plans/{plan_id}",
    response_model=CommissionPlanResponse,
)
def get_plan(
    plan_id: str,
    service: Annotated[CommissionService, Depends(get_service)],
) -> CommissionPlanResponse:
    """Retrieve a commission plan by ID."""
    return service.get_plan(plan_id)


# ---------------------------------------------------------------------------
# Slab management
# ---------------------------------------------------------------------------


@router.post(
    "/plans/{plan_id}/slabs",
    response_model=CommissionSlabResponse,
    status_code=201,
)
def add_slab(
    plan_id: str,
    data: CommissionSlabCreate,
    service: Annotated[CommissionService, Depends(get_service)],
) -> CommissionSlabResponse:
    """Add a slab tier to a commission plan."""
    return service.add_slab(plan_id, data)


@router.get(
    "/plans/{plan_id}/slabs",
    response_model=List[CommissionSlabResponse],
)
def list_slabs(
    plan_id: str,
    service: Annotated[CommissionService, Depends(get_service)],
) -> List[CommissionSlabResponse]:
    """List all slabs for a commission plan (ordered by sequence)."""
    return service.list_slabs(plan_id)


# ---------------------------------------------------------------------------
# Payout operations
# ---------------------------------------------------------------------------


@router.post(
    "/payouts/calculate",
    response_model=CommissionPayoutResponse,
    status_code=201,
)
def calculate_payout(
    data: CommissionPayoutRequest,
    service: Annotated[CommissionService, Depends(get_service)],
) -> CommissionPayoutResponse:
    """Calculate a commission payout for a sale contract."""
    return service.calculate_payout(data)


@router.get(
    "/payouts/{payout_id}",
    response_model=CommissionPayoutResponse,
)
def get_payout(
    payout_id: str,
    service: Annotated[CommissionService, Depends(get_service)],
) -> CommissionPayoutResponse:
    """Retrieve a commission payout by ID."""
    return service.get_payout(payout_id)


@router.post(
    "/payouts/{payout_id}/approve",
    response_model=CommissionPayoutResponse,
)
def approve_payout(
    payout_id: str,
    service: Annotated[CommissionService, Depends(get_service)],
) -> CommissionPayoutResponse:
    """Approve a commission payout (makes it immutable)."""
    return service.approve_payout(payout_id)
