"""
strategy_execution_outcome.repository

Data access layer for the Strategy Execution Outcome module (PR-V7-10).

All write operations go through this layer.  Cross-module DB logic is
forbidden — this repository only touches strategy_execution_outcomes,
strategy_execution_triggers (read-only), strategy_approvals (read-only),
and projects (read-only).
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
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

    def get_triggers_by_ids(
        self, trigger_ids: List[str]
    ) -> Dict[str, StrategyExecutionTrigger]:
        """Return a {trigger_id: trigger} map for the given IDs in one query."""
        if not trigger_ids:
            return {}
        rows = (
            self._db.query(StrategyExecutionTrigger)
            .filter(StrategyExecutionTrigger.id.in_(trigger_ids))
            .all()
        )
        return {t.id: t for t in rows}

    # ------------------------------------------------------------------
    # Outcome writes
    # ------------------------------------------------------------------

    def supersede_and_create(
        self, outcome: StrategyExecutionOutcome
    ) -> StrategyExecutionOutcome:
        """Supersede prior 'recorded' outcomes for the same trigger and insert the new one.

        Both operations run inside a single transaction so there is never a
        moment where the trigger has zero authoritative outcomes or two.

        Translates any IntegrityError (from the partial unique index on
        recorded outcomes per trigger) into ConflictError so concurrent
        races surface as HTTP 409 rather than an unhandled 500.
        """
        trigger_id = outcome.execution_trigger_id
        try:
            if trigger_id is not None:
                # Supersede prior recorded outcomes inside the same transaction.
                superseded_rows = (
                    self._db.query(StrategyExecutionOutcome)
                    .filter(
                        StrategyExecutionOutcome.execution_trigger_id == trigger_id,
                        StrategyExecutionOutcome.status == "recorded",
                    )
                    .all()
                )
                for row in superseded_rows:
                    row.status = "superseded"

            self._db.add(outcome)
            self._db.commit()
            self._db.refresh(outcome)
            return outcome
        except IntegrityError:
            self._db.rollback()
            raise ConflictError(
                f"A concurrent outcome recording is already in progress for trigger "
                f"'{trigger_id}'. Retry once the concurrent request completes."
            )

    def save(
        self, outcome: StrategyExecutionOutcome
    ) -> StrategyExecutionOutcome:
        """Flush an in-place-mutated outcome record and return it refreshed."""
        self._db.add(outcome)
        self._db.commit()
        self._db.refresh(outcome)
        return outcome

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

    def list_projects_awaiting_outcome(
        self,
        limit: Optional[int] = None,
    ) -> List[Tuple[str, str]]:
        """Return one (project_id, trigger_id) per project whose most recent
        completed trigger has no recorded outcome.

        De-duplicates by project: for each project with at least one completed
        trigger, we select the *latest* completed trigger.  If that trigger
        has no recorded outcome the project is included in the result.

        When *limit* is provided the database applies the cap directly so the
        caller does not need to slice.

        Returns a list of (project_id, trigger_id) tuples.
        """
        # Step 1 — Latest completed-trigger timestamp per project.
        latest_ts_subq = (
            self._db.query(
                StrategyExecutionTrigger.project_id,
                func.max(StrategyExecutionTrigger.created_at).label("max_created_at"),
            )
            .filter(StrategyExecutionTrigger.status == "completed")
            .group_by(StrategyExecutionTrigger.project_id)
            .subquery()
        )

        # Step 2 — Join back to get the actual trigger rows for those timestamps.
        latest_completed = (
            self._db.query(
                StrategyExecutionTrigger.id,
                StrategyExecutionTrigger.project_id,
            )
            .join(
                latest_ts_subq,
                (StrategyExecutionTrigger.project_id == latest_ts_subq.c.project_id)
                & (
                    StrategyExecutionTrigger.created_at
                    == latest_ts_subq.c.max_created_at
                ),
            )
            .filter(StrategyExecutionTrigger.status == "completed")
            .subquery()
        )

        # Step 3 — Exclude trigger IDs that already have a recorded outcome
        #          (NOT EXISTS correlated subquery).
        recorded_outcome_exists = (
            self._db.query(StrategyExecutionOutcome.id)
            .filter(
                StrategyExecutionOutcome.execution_trigger_id == latest_completed.c.id,
                StrategyExecutionOutcome.status == "recorded",
            )
            .exists()
        )

        query = (
            self._db.query(
                latest_completed.c.project_id,
                latest_completed.c.id,
            )
            .filter(~recorded_outcome_exists)
            .order_by(latest_completed.c.project_id)
        )

        if limit is not None:
            query = query.limit(limit)

        return [(row[0], row[1]) for row in query.all()]

    def count_projects_awaiting_outcome(self) -> int:
        """Return the count of distinct projects whose latest completed trigger
        has no recorded outcome.

        Uses the same logic as list_projects_awaiting_outcome but returns
        only the total count without the display limit applied.
        """
        # Latest completed-trigger timestamp per project.
        latest_ts_subq = (
            self._db.query(
                StrategyExecutionTrigger.project_id,
                func.max(StrategyExecutionTrigger.created_at).label("max_created_at"),
            )
            .filter(StrategyExecutionTrigger.status == "completed")
            .group_by(StrategyExecutionTrigger.project_id)
            .subquery()
        )

        latest_completed = (
            self._db.query(
                StrategyExecutionTrigger.id,
                StrategyExecutionTrigger.project_id,
            )
            .join(
                latest_ts_subq,
                (StrategyExecutionTrigger.project_id == latest_ts_subq.c.project_id)
                & (
                    StrategyExecutionTrigger.created_at
                    == latest_ts_subq.c.max_created_at
                ),
            )
            .filter(StrategyExecutionTrigger.status == "completed")
            .subquery()
        )

        recorded_outcome_exists = (
            self._db.query(StrategyExecutionOutcome.id)
            .filter(
                StrategyExecutionOutcome.execution_trigger_id == latest_completed.c.id,
                StrategyExecutionOutcome.status == "recorded",
            )
            .exists()
        )

        return (
            self._db.query(latest_completed.c.project_id)
            .filter(~recorded_outcome_exists)
            .count()
        )

