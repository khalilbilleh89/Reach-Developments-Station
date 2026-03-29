"""
portfolio_auto_strategy.repository

Read-only data access for the Portfolio Auto-Strategy engine (PR-V7-06).

Provides efficient project list retrieval for portfolio-scale orchestration.
All queries are read-only — no records are mutated.

N+1 patterns are avoided: projects are fetched in a single bulk query.
"""

from typing import List

from sqlalchemy.orm import Session

from app.modules.projects.models import Project


class PortfolioAutoStrategyRepository:
    """Read-only repository for portfolio auto-strategy data access."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_projects(self) -> List[Project]:
        """Return all projects ordered by name for deterministic portfolio analysis."""
        return self._db.query(Project).order_by(Project.name).all()
