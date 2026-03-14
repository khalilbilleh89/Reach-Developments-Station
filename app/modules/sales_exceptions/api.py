"""
sales_exceptions.api

REST API router for the Sales Exceptions / Incentives module.

Endpoints
---------
  POST   /api/v1/sales-exceptions
  GET    /api/v1/sales-exceptions/{id}
  PATCH  /api/v1/sales-exceptions/{id}
  POST   /api/v1/sales-exceptions/{id}/approve
  POST   /api/v1/sales-exceptions/{id}/reject

  GET    /api/v1/projects/{project_id}/sales-exceptions
  GET    /api/v1/projects/{project_id}/sales-exceptions/summary
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.sales_exceptions.schemas import (
    SalesExceptionApproval,
    SalesExceptionCreate,
    SalesExceptionListResponse,
    SalesExceptionResponse,
    SalesExceptionSummary,
    SalesExceptionUpdate,
)
from app.modules.sales_exceptions.service import SalesExceptionService

router = APIRouter(tags=["sales-exceptions"])


def get_service(db: Session = Depends(get_db)) -> SalesExceptionService:
    return SalesExceptionService(db)


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------

@router.post(
    "/sales-exceptions",
    response_model=SalesExceptionResponse,
    status_code=201,
)
def create_exception(
    data: SalesExceptionCreate,
    service: Annotated[SalesExceptionService, Depends(get_service)],
) -> SalesExceptionResponse:
    """Request a new sales exception (discount, incentive, etc.)."""
    return service.create_exception(data)


@router.get(
    "/sales-exceptions/{exception_id}",
    response_model=SalesExceptionResponse,
)
def get_exception(
    exception_id: str,
    service: Annotated[SalesExceptionService, Depends(get_service)],
) -> SalesExceptionResponse:
    """Retrieve a sales exception by ID."""
    return service.get_exception(exception_id)


@router.patch(
    "/sales-exceptions/{exception_id}",
    response_model=SalesExceptionResponse,
)
def update_exception(
    exception_id: str,
    data: SalesExceptionUpdate,
    service: Annotated[SalesExceptionService, Depends(get_service)],
) -> SalesExceptionResponse:
    """Update a pending sales exception (notes, incentive, contract link)."""
    return service.update_exception(exception_id, data)


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------

@router.post(
    "/sales-exceptions/{exception_id}/approve",
    response_model=SalesExceptionResponse,
)
def approve_exception(
    exception_id: str,
    data: SalesExceptionApproval,
    service: Annotated[SalesExceptionService, Depends(get_service)],
) -> SalesExceptionResponse:
    """Approve a pending sales exception."""
    return service.approve_exception(exception_id, data)


@router.post(
    "/sales-exceptions/{exception_id}/reject",
    response_model=SalesExceptionResponse,
)
def reject_exception(
    exception_id: str,
    data: SalesExceptionApproval,
    service: Annotated[SalesExceptionService, Depends(get_service)],
) -> SalesExceptionResponse:
    """Reject a pending sales exception."""
    return service.reject_exception(exception_id, data)


# ---------------------------------------------------------------------------
# Project-scoped views
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/sales-exceptions",
    response_model=SalesExceptionListResponse,
)
def list_project_exceptions(
    project_id: str,
    service: Annotated[SalesExceptionService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> SalesExceptionListResponse:
    """List all sales exceptions for a project."""
    return service.list_by_project(project_id, skip=skip, limit=limit)


@router.get(
    "/projects/{project_id}/sales-exceptions/summary",
    response_model=SalesExceptionSummary,
)
def get_project_exceptions_summary(
    project_id: str,
    service: Annotated[SalesExceptionService, Depends(get_service)],
) -> SalesExceptionSummary:
    """Aggregate discount and incentive analytics for a project."""
    return service.get_project_summary(project_id)
