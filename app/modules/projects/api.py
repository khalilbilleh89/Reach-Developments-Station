"""
projects.api

CRUD API router for the Project entity and project attribute definitions/options.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.projects.schemas import (
    AttributeDefinitionCreate,
    AttributeDefinitionList,
    AttributeDefinitionResponse,
    AttributeDefinitionUpdate,
    AttributeOptionCreate,
    AttributeOptionResponse,
    AttributeOptionUpdate,
    ProjectCreate,
    ProjectHierarchy,
    ProjectList,
    ProjectResponse,
    ProjectSummary,
    ProjectUpdate,
)
from app.modules.projects.service import ProjectService
from app.shared.enums.project import ProjectStatus

router = APIRouter(prefix="/projects", tags=["projects"])


def get_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    service: Annotated[ProjectService, Depends(get_service)],
) -> ProjectResponse:
    """Create a new project."""
    return service.create_project(data)


@router.get("", response_model=ProjectList)
def list_projects(
    service: Annotated[ProjectService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[ProjectStatus] = Query(default=None, description="Filter by project status"),
    search: Optional[str] = Query(default=None, description="Search by name or code"),
) -> ProjectList:
    """List all projects, with optional status filter and name/code search."""
    return service.list_projects(skip=skip, limit=limit, status=status, search=search)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_service)],
) -> ProjectResponse:
    """Get a project by ID."""
    return service.get_project(project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    service: Annotated[ProjectService, Depends(get_service)],
) -> ProjectResponse:
    """Update a project."""
    return service.update_project(project_id, data)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_service)],
) -> Response:
    """Delete a project.

    Returns 204 on success.
    Returns 404 if the project does not exist.
    Returns 409 if the project has dependent phase records.
    """
    service.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/summary", response_model=ProjectSummary)
def get_project_summary(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_service)],
) -> ProjectSummary:
    """Return aggregated KPI summary (phase counts, timeline) for a project."""
    return service.get_project_summary(project_id)


@router.get("/{project_id}/hierarchy", response_model=ProjectHierarchy)
def get_project_hierarchy(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_service)],
) -> ProjectHierarchy:
    """Return the full Project → Phase → Building → Floor hierarchy with unit counts."""
    return service.get_project_hierarchy(project_id)


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_service)],
) -> ProjectResponse:
    """Archive (set to on_hold) a project."""
    return service.archive_project(project_id)


# ---------------------------------------------------------------------------
# Project Attribute Definitions
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/attribute-definitions",
    response_model=AttributeDefinitionList,
)
def list_attribute_definitions(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_service)],
) -> AttributeDefinitionList:
    """List all attribute definitions for a project (with nested options)."""
    return service.list_attribute_definitions(project_id)


@router.post(
    "/{project_id}/attribute-definitions",
    response_model=AttributeDefinitionResponse,
    status_code=201,
)
def create_attribute_definition(
    project_id: str,
    data: AttributeDefinitionCreate,
    service: Annotated[ProjectService, Depends(get_service)],
) -> AttributeDefinitionResponse:
    """Create a project attribute definition (e.g. view_type)."""
    return service.create_attribute_definition(project_id, data)


@router.patch(
    "/{project_id}/attribute-definitions/{definition_id}",
    response_model=AttributeDefinitionResponse,
)
def update_attribute_definition(
    project_id: str,
    definition_id: str,
    data: AttributeDefinitionUpdate,
    service: Annotated[ProjectService, Depends(get_service)],
) -> AttributeDefinitionResponse:
    """Update label or active status of an attribute definition."""
    return service.update_attribute_definition(project_id, definition_id, data)


# ---------------------------------------------------------------------------
# Project Attribute Options
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/attribute-definitions/{definition_id}/options",
    response_model=AttributeOptionResponse,
    status_code=201,
)
def create_attribute_option(
    project_id: str,
    definition_id: str,
    data: AttributeOptionCreate,
    service: Annotated[ProjectService, Depends(get_service)],
) -> AttributeOptionResponse:
    """Add an option to a project attribute definition."""
    return service.create_attribute_option(project_id, definition_id, data)


@router.patch(
    "/{project_id}/attribute-definitions/{definition_id}/options/{option_id}",
    response_model=AttributeOptionResponse,
)
def update_attribute_option(
    project_id: str,
    definition_id: str,
    option_id: str,
    data: AttributeOptionUpdate,
    service: Annotated[ProjectService, Depends(get_service)],
) -> AttributeOptionResponse:
    """Update label, sort_order, or active status of an option."""
    return service.update_attribute_option(project_id, definition_id, option_id, data)
