"""
projects.repository

Data access layer for the Project entity.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.phases.models import Phase
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate, ProjectUpdate
from app.shared.enums.project import PhaseStatus


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ProjectCreate) -> Project:
        project = Project(**data.model_dump())
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_by_id(self, project_id: str) -> Optional[Project]:
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_by_code(self, code: str) -> Optional[Project]:
        return self.db.query(Project).filter(Project.code == code).first()

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Project]:
        query = self.db.query(Project)
        if status:
            query = query.filter(Project.status == status)
        if search:
            term = f"%{search}%"
            query = query.filter(
                Project.name.ilike(term) | Project.code.ilike(term)
            )
        return query.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()

    def count(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> int:
        query = self.db.query(Project)
        if status:
            query = query.filter(Project.status == status)
        if search:
            term = f"%{search}%"
            query = query.filter(
                Project.name.ilike(term) | Project.code.ilike(term)
            )
        return query.count()

    def update(self, project: Project, data: ProjectUpdate) -> Project:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_project_phase_summary(self, project_id: str) -> dict:
        """Aggregate phase counts and timeline dates for a project."""
        phases = (
            self.db.query(Phase)
            .filter(Phase.project_id == project_id)
            .all()
        )
        total = len(phases)
        active = sum(1 for p in phases if p.status == PhaseStatus.ACTIVE.value)
        planned = sum(1 for p in phases if p.status == PhaseStatus.PLANNED.value)
        completed = sum(1 for p in phases if p.status == PhaseStatus.COMPLETED.value)
        start_dates = [p.start_date for p in phases if p.start_date is not None]
        end_dates = [p.end_date for p in phases if p.end_date is not None]
        return {
            "total_phases": total,
            "active_phases": active,
            "planned_phases": planned,
            "completed_phases": completed,
            "earliest_start_date": min(start_dates) if start_dates else None,
            "latest_target_completion": max(end_dates) if end_dates else None,
        }
