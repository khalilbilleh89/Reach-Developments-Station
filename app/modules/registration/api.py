"""
registration.api

REST API router for the Registration/Conveyancing module.

Endpoints
---------
POST   /registration/cases
GET    /registration/cases/{case_id}
GET    /registration/cases/by-sale/{sale_contract_id}
PATCH  /registration/cases/{case_id}
GET    /registration/projects/{project_id}/cases
GET    /registration/projects/{project_id}/summary
GET    /registration/cases/{case_id}/milestones
PATCH  /registration/cases/{case_id}/milestones/{milestone_id}
GET    /registration/cases/{case_id}/documents
PATCH  /registration/cases/{case_id}/documents/{document_id}
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.registration.schemas import (
    RegistrationCaseCreate,
    RegistrationCaseListResponse,
    RegistrationCaseResponse,
    RegistrationCaseUpdate,
    RegistrationDocumentResponse,
    RegistrationDocumentUpdate,
    RegistrationMilestoneResponse,
    RegistrationMilestoneUpdate,
    RegistrationSummaryResponse,
)
from app.modules.registration.service import RegistrationService

router = APIRouter(prefix="/registration", tags=["registration"])


def get_service(db: Session = Depends(get_db)) -> RegistrationService:
    return RegistrationService(db)


# ---------------------------------------------------------------------------
# Case endpoints
# ---------------------------------------------------------------------------

@router.post("/cases", response_model=RegistrationCaseResponse, status_code=201)
def create_case(
    data: RegistrationCaseCreate,
    service: Annotated[RegistrationService, Depends(get_service)],
) -> RegistrationCaseResponse:
    """Open a new registration case for a sold unit."""
    return service.create_case(data)


@router.get("/cases/by-sale/{sale_contract_id}", response_model=RegistrationCaseResponse)
def get_case_by_sale(
    sale_contract_id: str,
    service: Annotated[RegistrationService, Depends(get_service)],
) -> RegistrationCaseResponse:
    """Retrieve the registration case linked to a specific sales contract."""
    return service.get_case_by_sale_contract(sale_contract_id)


@router.get("/cases/{case_id}", response_model=RegistrationCaseResponse)
def get_case(
    case_id: str,
    service: Annotated[RegistrationService, Depends(get_service)],
) -> RegistrationCaseResponse:
    """Retrieve a registration case by ID."""
    return service.get_case(case_id)


@router.patch("/cases/{case_id}", response_model=RegistrationCaseResponse)
def update_case(
    case_id: str,
    data: RegistrationCaseUpdate,
    service: Annotated[RegistrationService, Depends(get_service)],
) -> RegistrationCaseResponse:
    """Update status, dates, or notes on a registration case."""
    return service.update_case(case_id, data)


# ---------------------------------------------------------------------------
# Project-scoped endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/cases",
    response_model=RegistrationCaseListResponse,
)
def list_project_cases(
    project_id: str,
    service: Annotated[RegistrationService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> RegistrationCaseListResponse:
    """List all registration cases for a project."""
    return service.list_project_cases(project_id, skip=skip, limit=limit)


@router.get(
    "/projects/{project_id}/summary",
    response_model=RegistrationSummaryResponse,
)
def get_project_summary(
    project_id: str,
    service: Annotated[RegistrationService, Depends(get_service)],
) -> RegistrationSummaryResponse:
    """Return registration progress summary for a project."""
    return service.get_project_summary(project_id)


# ---------------------------------------------------------------------------
# Milestone endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/cases/{case_id}/milestones",
    response_model=list[RegistrationMilestoneResponse],
)
def list_milestones(
    case_id: str,
    service: Annotated[RegistrationService, Depends(get_service)],
) -> list[RegistrationMilestoneResponse]:
    """List milestones for a registration case."""
    return service.list_milestones(case_id)


@router.patch(
    "/cases/{case_id}/milestones/{milestone_id}",
    response_model=RegistrationMilestoneResponse,
)
def update_milestone(
    case_id: str,
    milestone_id: str,
    data: RegistrationMilestoneUpdate,
    service: Annotated[RegistrationService, Depends(get_service)],
) -> RegistrationMilestoneResponse:
    """Update a milestone's status, due date, or remarks."""
    return service.update_milestone(case_id, milestone_id, data)


# ---------------------------------------------------------------------------
# Document endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/cases/{case_id}/documents",
    response_model=list[RegistrationDocumentResponse],
)
def list_documents(
    case_id: str,
    service: Annotated[RegistrationService, Depends(get_service)],
) -> list[RegistrationDocumentResponse]:
    """List documents for a registration case."""
    return service.list_documents(case_id)


@router.patch(
    "/cases/{case_id}/documents/{document_id}",
    response_model=RegistrationDocumentResponse,
)
def update_document(
    case_id: str,
    document_id: str,
    data: RegistrationDocumentUpdate,
    service: Annotated[RegistrationService, Depends(get_service)],
) -> RegistrationDocumentResponse:
    """Mark a document as received or update its reference details."""
    return service.update_document(case_id, document_id, data)
