"""
adaptive_strategy.repository

Data access layer for the Adaptive Strategy Influence Layer (PR-V7-12).

Responsibilities
----------------
- Read strategy_learning_metrics (read-only; never mutated here).
- Read projects (read-only).
- Support batch portfolio reads without N+1 patterns.

Cross-module rules
------------------
- Never write to any source table.
- No ranking or influence logic — that lives in service.py.
- Reuses strategy_learning models directly; does not duplicate them.
"""

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.projects.models import Project
from app.modules.strategy_learning.models import StrategyLearningMetrics


class AdaptiveStrategyRepository:
    """Read-only data access for adaptive strategy inputs."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Project reads
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> Optional[Project]:
        """Return a project by ID or None if not found."""
        return self._db.query(Project).filter(Project.id == project_id).first()

    def list_all_projects(self) -> List[Project]:
        """Return all projects."""
        return self._db.query(Project).all()

    # ------------------------------------------------------------------
    # Learning metrics reads
    # ------------------------------------------------------------------

    def get_all_metrics_for_project(
        self, project_id: str
    ) -> List[StrategyLearningMetrics]:
        """Return all metrics rows for a project (all strategy_type values)."""
        return (
            self._db.query(StrategyLearningMetrics)
            .filter(StrategyLearningMetrics.project_id == project_id)
            .order_by(StrategyLearningMetrics.strategy_type.asc())
            .all()
        )

    def get_aggregate_metrics_for_project(
        self, project_id: str
    ) -> Optional[StrategyLearningMetrics]:
        """Return the '_all_' aggregate metrics row for a project or None."""
        return (
            self._db.query(StrategyLearningMetrics)
            .filter(
                StrategyLearningMetrics.project_id == project_id,
                StrategyLearningMetrics.strategy_type == "_all_",
            )
            .first()
        )

    def get_metrics_by_strategy_type(
        self, project_id: str, strategy_type: str
    ) -> Optional[StrategyLearningMetrics]:
        """Return the metrics row for a specific (project, strategy_type) pair."""
        return (
            self._db.query(StrategyLearningMetrics)
            .filter(
                StrategyLearningMetrics.project_id == project_id,
                StrategyLearningMetrics.strategy_type == strategy_type,
            )
            .first()
        )

    def get_all_metrics_for_portfolio(self) -> List[StrategyLearningMetrics]:
        """Return all '_all_' aggregate rows across the portfolio in one query."""
        return (
            self._db.query(StrategyLearningMetrics)
            .filter(StrategyLearningMetrics.strategy_type == "_all_")
            .order_by(StrategyLearningMetrics.confidence_score.desc())
            .all()
        )

    def get_metrics_by_project_ids(
        self, project_ids: List[str]
    ) -> Dict[str, StrategyLearningMetrics]:
        """Return a {project_id: '_all_' metrics} map for the given project IDs."""
        if not project_ids:
            return {}
        rows = (
            self._db.query(StrategyLearningMetrics)
            .filter(
                StrategyLearningMetrics.project_id.in_(project_ids),
                StrategyLearningMetrics.strategy_type == "_all_",
            )
            .all()
        )
        return {r.project_id: r for r in rows}
