"""
projects.service

Business logic for the Project entity.
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.projects.models import Project
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import ProjectCreate, ProjectList, ProjectResponse, ProjectUpdate
from app.shared.enums.project import ProjectStatus


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.repo = ProjectRepository(db)

    def create_project(self, data: ProjectCreate) -> ProjectResponse:
        existing = self.repo.get_by_code(data.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with code '{data.code}' already exists.",
            )
        project = self.repo.create(data)
        return ProjectResponse.model_validate(project)

    def get_project(self, project_id: str) -> ProjectResponse:
        project = self._require_project(project_id)
        return ProjectResponse.model_validate(project)

    def list_projects(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> ProjectList:
        projects = self.repo.list(skip=skip, limit=limit, status=status, search=search)
        total = self.repo.count(status=status, search=search)
        return ProjectList(
            items=[ProjectResponse.model_validate(p) for p in projects],
            total=total,
        )

    def update_project(self, project_id: str, data: ProjectUpdate) -> ProjectResponse:
        project = self._require_project(project_id)
        updated = self.repo.update(project, data)
        return ProjectResponse.model_validate(updated)

    def archive_project(self, project_id: str) -> ProjectResponse:
        """Set a project's status to on_hold, effectively archiving it."""
        project = self._require_project(project_id)
        if project.status == ProjectStatus.ON_HOLD.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project '{project_id}' is already archived (on_hold).",
            )
        archive_data = ProjectUpdate(status=ProjectStatus.ON_HOLD)
        updated = self.repo.update(project, archive_data)
        return ProjectResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str) -> Project:
        project = self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return project
