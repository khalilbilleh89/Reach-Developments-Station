"""
project_structure.api

Read-only structure viewer endpoint.

Endpoint:
  GET /api/v1/projects/{project_id}/structure

Returns the canonical Project → Phase → Building → Floor → Unit hierarchy
as a typed, nested JSON response.

Forbidden: no mutating routes; no raw ORM dumps without contract shaping.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.project_structure.schemas import ProjectStructureResponse
from app.modules.project_structure.service import ProjectStructureService

router = APIRouter(
    prefix="/projects",
    tags=["Project Structure"],
    dependencies=[Depends(get_current_user_payload)],
)


def _get_service(db: Session = Depends(get_db)) -> ProjectStructureService:
    return ProjectStructureService(db)


@router.get("/{project_id}/structure", response_model=ProjectStructureResponse)
def get_project_structure(
    project_id: str,
    service: Annotated[ProjectStructureService, Depends(_get_service)],
) -> ProjectStructureResponse:
    """Return the full canonical hierarchy for a project.

    Returns a nested tree of phases → buildings → floors → units with
    summary counts at each level.

    Raises 404 if the project does not exist.
    """
    return service.get_structure(project_id)
