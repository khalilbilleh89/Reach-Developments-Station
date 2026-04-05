"""
strategy_execution_outcome.repository

Data access layer for the Strategy Execution Outcome module (PR-V7-10).

All write operations go through this layer.  Cross-module DB logic is
forbidden — this repository only touches strategy_execution_outcomes,
strategy_execution_triggers (read-only), strategy_approvals (read-only),
and projects (read-only).
"""

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.modules.projects.models import Project
from app.modules.strategy_execution_trigger.models import StrategyExecutionTrigger
from app.modules.strategy_execution_outcome.models import StrategyExecutionOutcome


class StrategyExecutionOutcomeRepository:
    """Data access layer for strategy execution outcome records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Project helpers (read-only — project records are never mutated)
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> Optional[Project]:
        """Return a project by ID or None if not found."""
        return self._db.query(Project).filter(Project.id == project_id).first()

    def list_projects_by_ids(self, project_ids: List[str]) -> List[Project]:
        """Return projects for the given IDs in arbitrary order."""
        if not project_ids:
            return []
        return (
            self._db.query(Project)
            .filter(Project.id.in_(project_ids))
            .all()
        )

    # ------------------------------------------------------------------
    # Trigger helpers (read-only — trigger records are never mutated here)
    # ------------------------------------------------------------------

    def get_trigger(self, trigger_id: str) -> Optional[StrategyExecutionTrigger]:
        """Return an execution trigger by ID or None if not found."""
        return (
            self._db.query(StrategyExecutionTrigger)
            .filter(StrategyExecutionTrigger.id == trigger_id)
            .first()
        )

    def get_latest_trigger_for_project(
        self, project_id: str
    ) -> Optional[StrategyExecutionTrigger]:
        """Return the most recently created trigger for a project, or None."""
        return (
            self._db.query(StrategyExecutionTrigger)
            .filter(StrategyExecutionTrigger.project_id == project_id)
            .order_by(StrategyExecutionTrigger.created_at.desc())
            .first()
        )

    # ------------------------------------------------------------------
    # Outcome writes
    # ------------------------------------------------------------------

    def create(
        self, outcome: StrategyExecutionOutcome
    ) -> StrategyExecutionOutcome:
        """Persist a new outcome record and return it with generated fields."""
        self._db.add(outcome)
        self._db.commit()
        self._db.refresh(outcome)
        return outcome

    def save(
        self, outcome: StrategyExecutionOutcome
    ) -> StrategyExecutionOutcome:
        """Flush an in-place-mutated outcome record and return it refreshed."""
        self._db.add(outcome)
        self._db.commit()
        self._db.refresh(outcome)
        return outcome

    def supersede_active_for_trigger(self, trigger_id: str) -> int:
        """Mark all 'recorded' outcomes for a trigger as 'superseded'.

        Returns the count of rows that were superseded.
        """
        rows = (
            self._db.query(StrategyExecutionOutcome)
            .filter(
                StrategyExecutionOutcome.execution_trigger_id == trigger_id,
                StrategyExecutionOutcome.status == "recorded",
            )
            .all()
        )
        for row in rows:
            row.status = "superseded"
        if rows:
            self._db.commit()
        return len(rows)

    # ------------------------------------------------------------------
    # Outcome reads
    # ------------------------------------------------------------------

    def get_by_id(
        self, outcome_id: str
    ) -> Optional[StrategyExecutionOutcome]:
        """Return a single outcome record by primary key or None."""
        return (
            self._db.query(StrategyExecutionOutcome)
            .filter(StrategyExecutionOutcome.id == outcome_id)
            .first()
        )

    def get_latest_for_project(
        self, project_id: str
    ) -> Optional[StrategyExecutionOutcome]:
        """Return the most recent 'recorded' outcome for a project, or None."""
        return (
            self._db.query(StrategyExecutionOutcome)
            .filter(
                StrategyExecutionOutcome.project_id == project_id,
                StrategyExecutionOutcome.status == "recorded",
            )
            .order_by(StrategyExecutionOutcome.recorded_at.desc())
            .first()
        )

    def get_by_trigger_id(
        self, trigger_id: str
    ) -> Optional[StrategyExecutionOutcome]:
        """Return the latest 'recorded' outcome for a trigger, or None."""
        return (
            self._db.query(StrategyExecutionOutcome)
            .filter(
                StrategyExecutionOutcome.execution_trigger_id == trigger_id,
                StrategyExecutionOutcome.status == "recorded",
            )
            .order_by(StrategyExecutionOutcome.recorded_at.desc())
            .first()
        )

    def has_outcome_for_trigger(self, trigger_id: str) -> bool:
        """Return True when a 'recorded' outcome exists for the trigger."""
        return (
            self._db.query(StrategyExecutionOutcome)
            .filter(
                StrategyExecutionOutcome.execution_trigger_id == trigger_id,
                StrategyExecutionOutcome.status == "recorded",
            )
            .first()
            is not None
        )

    def list_for_portfolio(
        self, limit: Optional[int] = None
    ) -> List[StrategyExecutionOutcome]:
        """Return recent 'recorded' outcomes across all projects.

        When *limit* is provided the database applies the cap directly.
        """
        query = (
            self._db.query(StrategyExecutionOutcome)
            .filter(StrategyExecutionOutcome.status == "recorded")
            .order_by(StrategyExecutionOutcome.recorded_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def count_by_outcome_result(self, outcome_result: str) -> int:
        """Return the count of 'recorded' outcomes with the given result."""
        return (
            self._db.query(StrategyExecutionOutcome)
            .filter(
                StrategyExecutionOutcome.outcome_result == outcome_result,
                StrategyExecutionOutcome.status == "recorded",
            )
            .count()
        )

    def list_completed_triggers_without_outcome(
        self,
    ) -> List[Tuple[str, str]]:
        """Return (project_id, trigger_id) for completed triggers with no recorded outcome.

        Used to surface projects that finished execution but haven't had
        an outcome recorded yet.
        """
        completed = (
            self._db.query(
                StrategyExecutionTrigger.id,
                StrategyExecutionTrigger.project_id,
            )
            .filter(StrategyExecutionTrigger.status == "completed")
            .all()
        )
        if not completed:
            return []

        trigger_ids = [row[0] for row in completed]

        with_outcome = (
            self._db.query(StrategyExecutionOutcome.execution_trigger_id)
            .filter(
                StrategyExecutionOutcome.execution_trigger_id.in_(trigger_ids),
                StrategyExecutionOutcome.status == "recorded",
            )
            .distinct()
            .all()
        )
        with_outcome_ids = {row[0] for row in with_outcome}

        return [
            (project_id, trigger_id)
            for trigger_id, project_id in completed
            if trigger_id not in with_outcome_ids
        ]
