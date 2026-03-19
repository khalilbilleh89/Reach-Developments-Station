"""
registry.api

REST API router for the Registry/Conveyancing module.

Endpoints
---------
POST   /registry/cases
GET    /registry/cases/{case_id}
GET    /registry/cases/by-sale/{sale_contract_id}
PATCH  /registry/cases/{case_id}
GET    /registry/projects/{project_id}/cases
GET    /registry/projects/{project_id}/summary
GET    /registry/cases/{case_id}/milestones
PATCH  /registry/cases/{case_id}/milestones/{milestone_id}
GET    /registry/cases/{case_id}/documents
PATCH  /registry/cases/{case_id}/documents/{document_id}
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.registry.schemas import (
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
from app.modules.registry.service import RegistryService

router = APIRouter(prefix="/registry", tags=["registry"])


def get_service(db: Session = Depends(get_db)) -> RegistryService:
    return RegistryService(db)


# ---------------------------------------------------------------------------
# Case endpoints
# ---------------------------------------------------------------------------

@router.post("/cases", response_model=RegistrationCaseResponse, status_code=201)
def create_case(
    data: RegistrationCaseCreate,
    service: Annotated[RegistryService, Depends(get_service)],
) -> RegistrationCaseResponse:
    """Open a new registry case for a sold unit."""
    return service.create_case(data)


@router.get("/cases/by-sale/{sale_contract_id}", response_model=RegistrationCaseResponse)
def get_case_by_sale(
    sale_contract_id: str,
    service: Annotated[RegistryService, Depends(get_service)],
) -> RegistrationCaseResponse:
    """Retrieve the registry case linked to a specific sales contract."""
    return service.get_case_by_sale_contract(sale_contract_id)


@router.get("/cases/{case_id}", response_model=RegistrationCaseResponse)
def get_case(
    case_id: str,
    service: Annotated[RegistryService, Depends(get_service)],
) -> RegistrationCaseResponse:
    """Retrieve a registry case by ID."""
    return service.get_case(case_id)


@router.patch("/cases/{case_id}", response_model=RegistrationCaseResponse)
def update_case(
    case_id: str,
    data: RegistrationCaseUpdate,
    service: Annotated[RegistryService, Depends(get_service)],
) -> RegistrationCaseResponse:
    """Update status, dates, or notes on a registry case."""
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
    service: Annotated[RegistryService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> RegistrationCaseListResponse:
    """List all registry cases for a project."""
    return service.list_project_cases(project_id, skip=skip, limit=limit)


@router.get(
    "/projects/{project_id}/summary",
    response_model=RegistrationSummaryResponse,
)
def get_project_summary(
    project_id: str,
    service: Annotated[RegistryService, Depends(get_service)],
) -> RegistrationSummaryResponse:
    """Return registry progress summary for a project."""
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
    service: Annotated[RegistryService, Depends(get_service)],
) -> list[RegistrationMilestoneResponse]:
    """List milestones for a registry case."""
    return service.list_milestones(case_id)


@router.patch(
    "/cases/{case_id}/milestones/{milestone_id}",
    response_model=RegistrationMilestoneResponse,
)
def update_milestone(
    case_id: str,
    milestone_id: str,
    data: RegistrationMilestoneUpdate,
    service: Annotated[RegistryService, Depends(get_service)],
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
    service: Annotated[RegistryService, Depends(get_service)],
) -> list[RegistrationDocumentResponse]:
    """List documents for a registry case."""
    return service.list_documents(case_id)


@router.patch(
    "/cases/{case_id}/documents/{document_id}",
    response_model=RegistrationDocumentResponse,
)
def update_document(
    case_id: str,
    document_id: str,
    data: RegistrationDocumentUpdate,
    service: Annotated[RegistryService, Depends(get_service)],
) -> RegistrationDocumentResponse:
    """Mark a document as received or update its reference details."""
    return service.update_document(case_id, document_id, data)


# ---------------------------------------------------------------------------
# Backward-compatibility alias — temporary, PR-D1 normalization safety net.
#
# These routes mirror /api/v1/registry/* exactly under the legacy
# /api/v1/registration/* prefix. They are excluded from the OpenAPI schema
# (include_in_schema=False) and are kept only to prevent runtime regressions
# during the transition period.
#
# Remove this section (and the legacy_router include in app/main.py) in a
# follow-up PR once all callers have been migrated to /api/v1/registry/*.
# ---------------------------------------------------------------------------

legacy_router = APIRouter(
    prefix="/registration",
    tags=["registry"],
    include_in_schema=False,
)

legacy_router.add_api_route(
    "/cases",
    create_case,
    methods=["POST"],
    response_model=RegistrationCaseResponse,
    status_code=201,
)
legacy_router.add_api_route(
    "/cases/by-sale/{sale_contract_id}",
    get_case_by_sale,
    methods=["GET"],
    response_model=RegistrationCaseResponse,
)
legacy_router.add_api_route(
    "/cases/{case_id}",
    get_case,
    methods=["GET"],
    response_model=RegistrationCaseResponse,
)
legacy_router.add_api_route(
    "/cases/{case_id}",
    update_case,
    methods=["PATCH"],
    response_model=RegistrationCaseResponse,
)
legacy_router.add_api_route(
    "/projects/{project_id}/cases",
    list_project_cases,
    methods=["GET"],
    response_model=RegistrationCaseListResponse,
)
legacy_router.add_api_route(
    "/projects/{project_id}/summary",
    get_project_summary,
    methods=["GET"],
    response_model=RegistrationSummaryResponse,
)
legacy_router.add_api_route(
    "/cases/{case_id}/milestones",
    list_milestones,
    methods=["GET"],
    response_model=list[RegistrationMilestoneResponse],
)
legacy_router.add_api_route(
    "/cases/{case_id}/milestones/{milestone_id}",
    update_milestone,
    methods=["PATCH"],
    response_model=RegistrationMilestoneResponse,
)
legacy_router.add_api_route(
    "/cases/{case_id}/documents",
    list_documents,
    methods=["GET"],
    response_model=list[RegistrationDocumentResponse],
)
legacy_router.add_api_route(
    "/cases/{case_id}/documents/{document_id}",
    update_document,
    methods=["PATCH"],
    response_model=RegistrationDocumentResponse,
)
