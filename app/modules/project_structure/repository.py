"""
project_structure.repository

Read-only data access for the Project Structure Viewer.

Uses eager loading (selectinload) on all hierarchy levels to retrieve the full
Project → Phase → Building → Floor → Unit tree in a small number of queries,
avoiding N+1 patterns during structure display.

Forbidden: no hierarchy record mutations; no ownership relationship inference.
"""

from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.modules.buildings.models import Building
from app.modules.floors.models import Floor
from app.modules.phases.models import Phase
from app.modules.projects.models import Project
from app.modules.units.models import Unit


class ProjectStructureRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_project_by_id(self, project_id: str) -> Optional[Project]:
        """Return the Project record without hierarchy loading."""
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_project_with_full_hierarchy(self, project_id: str) -> Optional[Project]:
        """Return a Project with phases → buildings → floors → units eagerly loaded.

        selectinload is used at each level so the ORM issues a fixed number of
        SELECT IN queries rather than one per row (N+1 avoidance).
        """
        return (
            self.db.query(Project)
            .filter(Project.id == project_id)
            .options(
                selectinload(Project.phases).selectinload(Phase.buildings).selectinload(
                    Building.floors
                ).selectinload(Floor.units)
            )
            .first()
        )
