"""
projects.repository

Data access layer for the Project entity and project attribute definitions/options.
"""

from typing import List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app.modules.phases.models import Phase
from app.modules.projects.models import Project, ProjectAttributeDefinition, ProjectAttributeOption
from app.modules.projects.schemas import (
    AttributeDefinitionCreate,
    AttributeDefinitionUpdate,
    AttributeOptionCreate,
    AttributeOptionUpdate,
    ProjectCreate,
    ProjectUpdate,
)
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

    def delete(self, project: Project) -> None:
        self.db.delete(project)
        self.db.commit()

    def has_phases(self, project_id: str) -> bool:
        """Return True if at least one Phase record exists for the given project."""
        return (
            self.db.query(Phase.id)
            .filter(Phase.project_id == project_id)
            .first()
        ) is not None

    def update(self, project: Project, data: ProjectUpdate) -> Project:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_project_phase_summary(self, project_id: str) -> dict:
        """Aggregate phase counts and timeline dates for a project using SQL."""
        result = (
            self.db.query(
                func.count(Phase.id).label("total_phases"),
                func.sum(
                    case((Phase.status == PhaseStatus.ACTIVE.value, 1), else_=0)
                ).label("active_phases"),
                func.sum(
                    case((Phase.status == PhaseStatus.PLANNED.value, 1), else_=0)
                ).label("planned_phases"),
                func.sum(
                    case((Phase.status == PhaseStatus.COMPLETED.value, 1), else_=0)
                ).label("completed_phases"),
                func.min(Phase.start_date).label("earliest_start_date"),
                func.max(Phase.end_date).label("latest_target_completion"),
            )
            .filter(Phase.project_id == project_id)
            .one()
        )
        return {
            "total_phases": result.total_phases or 0,
            "active_phases": result.active_phases or 0,
            "planned_phases": result.planned_phases or 0,
            "completed_phases": result.completed_phases or 0,
            "earliest_start_date": result.earliest_start_date,
            "latest_target_completion": result.latest_target_completion,
        }

    # ------------------------------------------------------------------
    # Attribute Definitions
    # ------------------------------------------------------------------

    def get_definition_by_id(self, definition_id: str) -> Optional[ProjectAttributeDefinition]:
        return (
            self.db.query(ProjectAttributeDefinition)
            .filter(ProjectAttributeDefinition.id == definition_id)
            .first()
        )

    def get_definition_by_project_and_key(
        self, project_id: str, key: str
    ) -> Optional[ProjectAttributeDefinition]:
        return (
            self.db.query(ProjectAttributeDefinition)
            .filter(
                ProjectAttributeDefinition.project_id == project_id,
                ProjectAttributeDefinition.key == key,
            )
            .first()
        )

    def list_definitions(self, project_id: str) -> List[ProjectAttributeDefinition]:
        return (
            self.db.query(ProjectAttributeDefinition)
            .filter(ProjectAttributeDefinition.project_id == project_id)
            .options(selectinload(ProjectAttributeDefinition.options))
            .order_by(ProjectAttributeDefinition.created_at.asc())
            .all()
        )

    def create_definition(
        self, project_id: str, data: AttributeDefinitionCreate
    ) -> ProjectAttributeDefinition:
        definition = ProjectAttributeDefinition(
            project_id=project_id,
            key=data.key,
            label=data.label,
            input_type=data.input_type,
        )
        self.db.add(definition)
        self.db.commit()
        self.db.refresh(definition)
        return definition

    def update_definition(
        self, definition: ProjectAttributeDefinition, data: AttributeDefinitionUpdate
    ) -> ProjectAttributeDefinition:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(definition, field, value)
        self.db.commit()
        self.db.refresh(definition)
        return definition

    # ------------------------------------------------------------------
    # Attribute Options
    # ------------------------------------------------------------------

    def get_option_by_id(self, option_id: str) -> Optional[ProjectAttributeOption]:
        return (
            self.db.query(ProjectAttributeOption)
            .filter(ProjectAttributeOption.id == option_id)
            .first()
        )

    def get_option_by_definition_and_value(
        self, definition_id: str, value: str
    ) -> Optional[ProjectAttributeOption]:
        return (
            self.db.query(ProjectAttributeOption)
            .filter(
                ProjectAttributeOption.definition_id == definition_id,
                ProjectAttributeOption.value == value,
            )
            .first()
        )

    def get_option_by_definition_and_label(
        self, definition_id: str, label: str
    ) -> Optional[ProjectAttributeOption]:
        return (
            self.db.query(ProjectAttributeOption)
            .filter(
                ProjectAttributeOption.definition_id == definition_id,
                ProjectAttributeOption.label == label,
            )
            .first()
        )

    def create_option(
        self, definition_id: str, data: AttributeOptionCreate
    ) -> ProjectAttributeOption:
        option = ProjectAttributeOption(
            definition_id=definition_id,
            value=data.value,
            label=data.label,
            sort_order=data.sort_order,
        )
        self.db.add(option)
        self.db.commit()
        self.db.refresh(option)
        return option

    def update_option(
        self, option: ProjectAttributeOption, data: AttributeOptionUpdate
    ) -> ProjectAttributeOption:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(option, field, value)
        self.db.commit()
        self.db.refresh(option)
        return option
