"""
projects.service

Business logic for the Project entity.
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.projects.models import Project
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import ProjectCreate, ProjectList, ProjectResponse, ProjectSummary, ProjectUpdate
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
        status: Optional[ProjectStatus] = None,
        search: Optional[str] = None,
    ) -> ProjectList:
        status_value = status.value if status else None
        projects = self.repo.list(skip=skip, limit=limit, status=status_value, search=search)
        total = self.repo.count(status=status_value, search=search)
        return ProjectList(
            items=[ProjectResponse.model_validate(p) for p in projects],
            total=total,
        )

    def update_project(self, project_id: str, data: ProjectUpdate) -> ProjectResponse:
        project = self._require_project(project_id)
        # Validate date range using merged values: payload overrides persisted
        effective_start = (
            data.start_date if "start_date" in data.model_fields_set else project.start_date
        )
        effective_end = (
            data.target_end_date
            if "target_end_date" in data.model_fields_set
            else project.target_end_date
        )
        if effective_start and effective_end and effective_end < effective_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="target_end_date must be on or after start_date.",
            )
        updated = self.repo.update(project, data)
        return ProjectResponse.model_validate(updated)

    def delete_project(self, project_id: str) -> None:
        project = self._require_project(project_id)
        if self.repo.has_phases(project_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Project '{project_id}' cannot be deleted because it has "
                    "dependent phase records. Remove all dependent phases first."
                ),
            )
        self.repo.delete(project)

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

    def get_project_summary(self, project_id: str) -> ProjectSummary:
        """Return aggregated KPI summary for a project's phases."""
        self._require_project(project_id)
        data = self.repo.get_project_phase_summary(project_id)
        return ProjectSummary(project_id=project_id, **data)

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
