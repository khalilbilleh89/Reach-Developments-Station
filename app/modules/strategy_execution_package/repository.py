"""
strategy_execution_package.repository

Read-only data access for the Strategy Execution Package generator (PR-V7-07).

Provides efficient project list retrieval for portfolio-scale orchestration.
All queries are read-only — no records are mutated.

N+1 patterns are avoided: projects are fetched in a single bulk query.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.projects.models import Project


class StrategyExecutionPackageRepository:
    """Read-only repository for strategy execution package data access."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_projects(self) -> List[Project]:
        """Return all projects ordered by name for deterministic portfolio packaging."""
        return self._db.query(Project).order_by(Project.name).all()

    def get_project(self, project_id: str) -> Optional[Project]:
        """Return a single project by ID, or None if not found."""
        return self._db.query(Project).filter(Project.id == project_id).first()
