"""
strategy_learning.repository

Data access layer for the Strategy Learning module (PR-V7-11).

Responsibilities
----------------
- Read strategy_execution_outcomes (read-only; never mutated here).
- Read projects (read-only).
- Upsert strategy_learning_metrics rows.

Cross-module rules
------------------
- Never write to strategy_execution_outcomes, strategy_execution_triggers,
  strategy_approvals, or any other source table.
- Only produce derived confidence signal rows in strategy_learning_metrics.
"""

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.projects.models import Project
from app.modules.strategy_execution_outcome.models import StrategyExecutionOutcome
from app.modules.strategy_learning.models import StrategyLearningMetrics


class StrategyLearningRepository:
    """Data access layer for strategy learning metrics."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Project helpers (read-only)
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> Optional[Project]:
        """Return a project by ID or None if not found."""
        return self._db.query(Project).filter(Project.id == project_id).first()

    def list_all_projects(self) -> List[Project]:
        """Return all projects (used by portfolio-level aggregation)."""
        return self._db.query(Project).all()

    def list_projects_by_ids(self, project_ids: List[str]) -> List[Project]:
        """Return projects for the given IDs in arbitrary order."""
        if not project_ids:
            return []
        return self._db.query(Project).filter(Project.id.in_(project_ids)).all()

    # ------------------------------------------------------------------
    # Outcome reads (read-only)
    # ------------------------------------------------------------------

    def list_recorded_outcomes_for_project(
        self, project_id: str
    ) -> List[StrategyExecutionOutcome]:
        """Return all 'recorded' outcomes for a project ordered by recorded_at."""
        return (
            self._db.query(StrategyExecutionOutcome)
            .filter(
                StrategyExecutionOutcome.project_id == project_id,
                StrategyExecutionOutcome.status == "recorded",
            )
            .order_by(StrategyExecutionOutcome.recorded_at.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # Metrics reads
    # ------------------------------------------------------------------

    def get_metrics_for_project(
        self, project_id: str
    ) -> List[StrategyLearningMetrics]:
        """Return all metrics rows for a project (all strategy_type values)."""
        return (
            self._db.query(StrategyLearningMetrics)
            .filter(StrategyLearningMetrics.project_id == project_id)
            .order_by(StrategyLearningMetrics.strategy_type.asc())
            .all()
        )

    def get_metrics_by_strategy_type(
        self, project_id: str, strategy_type: str
    ) -> Optional[StrategyLearningMetrics]:
        """Return a specific (project_id, strategy_type) metrics row or None."""
        return (
            self._db.query(StrategyLearningMetrics)
            .filter(
                StrategyLearningMetrics.project_id == project_id,
                StrategyLearningMetrics.strategy_type == strategy_type,
            )
            .first()
        )

    def get_portfolio_aggregate_metrics(self) -> List[StrategyLearningMetrics]:
        """Return all '_all_' aggregate rows across all projects."""
        return (
            self._db.query(StrategyLearningMetrics)
            .filter(StrategyLearningMetrics.strategy_type == "_all_")
            .order_by(StrategyLearningMetrics.confidence_score.desc())
            .all()
        )

    def get_metrics_for_portfolio(self) -> List[StrategyLearningMetrics]:
        """Return all metrics rows across all projects (for portfolio views)."""
        return (
            self._db.query(StrategyLearningMetrics)
            .order_by(
                StrategyLearningMetrics.project_id.asc(),
                StrategyLearningMetrics.strategy_type.asc(),
            )
            .all()
        )

    # ------------------------------------------------------------------
    # Metrics writes
    # ------------------------------------------------------------------

    def upsert_metrics(
        self, metrics: StrategyLearningMetrics
    ) -> StrategyLearningMetrics:
        """Upsert a metrics row: update in place if it exists, insert otherwise.

        Existing rows are matched on (project_id, strategy_type).
        """
        existing = self.get_metrics_by_strategy_type(
            metrics.project_id, metrics.strategy_type
        )
        if existing is not None:
            existing.sample_size = metrics.sample_size
            existing.match_rate = metrics.match_rate
            existing.partial_rate = metrics.partial_rate
            existing.divergence_rate = metrics.divergence_rate
            existing.confidence_score = metrics.confidence_score
            existing.pricing_accuracy_score = metrics.pricing_accuracy_score
            existing.phasing_accuracy_score = metrics.phasing_accuracy_score
            existing.overall_strategy_accuracy = metrics.overall_strategy_accuracy
            existing.trend_direction = metrics.trend_direction
            existing.last_updated = metrics.last_updated
            self._db.add(existing)
            self._db.commit()
            self._db.refresh(existing)
            return existing
        else:
            self._db.add(metrics)
            self._db.commit()
            self._db.refresh(metrics)
            return metrics

    def upsert_metrics_batch(
        self, rows: List[StrategyLearningMetrics]
    ) -> List[StrategyLearningMetrics]:
        """Upsert a list of metrics rows in a single transaction."""
        # Build lookup for existing rows using one query per project.
        project_ids = list({r.project_id for r in rows})
        existing_map: Dict[tuple, StrategyLearningMetrics] = {}
        for pid in project_ids:
            for row in self.get_metrics_for_project(pid):
                existing_map[(row.project_id, row.strategy_type)] = row

        results: List[StrategyLearningMetrics] = []
        for metrics in rows:
            key = (metrics.project_id, metrics.strategy_type)
            existing = existing_map.get(key)
            if existing is not None:
                existing.sample_size = metrics.sample_size
                existing.match_rate = metrics.match_rate
                existing.partial_rate = metrics.partial_rate
                existing.divergence_rate = metrics.divergence_rate
                existing.confidence_score = metrics.confidence_score
                existing.pricing_accuracy_score = metrics.pricing_accuracy_score
                existing.phasing_accuracy_score = metrics.phasing_accuracy_score
                existing.overall_strategy_accuracy = metrics.overall_strategy_accuracy
                existing.trend_direction = metrics.trend_direction
                existing.last_updated = metrics.last_updated
                self._db.add(existing)
                results.append(existing)
            else:
                self._db.add(metrics)
                results.append(metrics)

        self._db.commit()
        for r in results:
            self._db.refresh(r)
        return results
