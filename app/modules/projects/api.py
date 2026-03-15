"""
projects.api

CRUD API router for the Project entity.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.projects.schemas import ProjectCreate, ProjectList, ProjectResponse, ProjectUpdate
from app.modules.projects.service import ProjectService

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
    status: Optional[str] = Query(default=None, description="Filter by project status"),
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


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_service)],
) -> ProjectResponse:
    """Archive (set to on_hold) a project."""
    return service.archive_project(project_id)
