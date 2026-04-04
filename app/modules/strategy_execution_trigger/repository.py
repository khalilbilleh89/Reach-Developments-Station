"""
strategy_execution_trigger.repository

Data access layer for the Strategy Execution Trigger module (PR-V7-09).

All write operations go through this layer.  Cross-module DB logic is
forbidden — this repository only touches strategy_execution_triggers,
strategy_approvals (read-only), and projects (read-only).
"""

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.modules.projects.models import Project
from app.modules.strategy_approval.models import StrategyApproval
from app.modules.strategy_execution_trigger.models import StrategyExecutionTrigger

# Status values that represent an active (not terminal) execution handoff.
_ACTIVE_STATUSES = ("triggered", "in_progress")


class StrategyExecutionTriggerRepository:
    """Data access layer for strategy execution trigger records."""

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
    # Approval helpers (read-only — approval records are never mutated)
    # ------------------------------------------------------------------

    def get_latest_approval_for_project(
        self, project_id: str
    ) -> Optional[StrategyApproval]:
        """Return the most recently created approval for a project, or None."""
        return (
            self._db.query(StrategyApproval)
            .filter(StrategyApproval.project_id == project_id)
            .order_by(StrategyApproval.created_at.desc())
            .first()
        )

    # ------------------------------------------------------------------
    # Trigger writes
    # ------------------------------------------------------------------

    def create(
        self, trigger: StrategyExecutionTrigger
    ) -> StrategyExecutionTrigger:
        """Persist a new trigger record and return it with generated fields.

        Translates any IntegrityError (e.g. from the partial unique index on
        active triggers per project) into ConflictError so concurrent races
        are surfaced as a clean HTTP 409 rather than an unhandled 500.
        """
        try:
            self._db.add(trigger)
            self._db.commit()
            self._db.refresh(trigger)
            return trigger
        except IntegrityError:
            self._db.rollback()
            raise ConflictError(
                f"An active execution trigger already exists for project "
                f"'{trigger.project_id}'. Resolve the existing trigger before "
                "creating a new one."
            )

    def save(
        self, trigger: StrategyExecutionTrigger
    ) -> StrategyExecutionTrigger:
        """Flush an in-place-mutated trigger record and return it refreshed."""
        self._db.add(trigger)
        self._db.commit()
        self._db.refresh(trigger)
        return trigger

    # ------------------------------------------------------------------
    # Trigger reads
    # ------------------------------------------------------------------

    def get_by_id(self, trigger_id: str) -> Optional[StrategyExecutionTrigger]:
        """Return a single trigger record by primary key or None."""
        return (
            self._db.query(StrategyExecutionTrigger)
            .filter(StrategyExecutionTrigger.id == trigger_id)
            .first()
        )

    def get_latest_for_project(
        self, project_id: str
    ) -> Optional[StrategyExecutionTrigger]:
        """Return the most recently created trigger for a project, or None."""
        return (
            self._db.query(StrategyExecutionTrigger)
            .filter(StrategyExecutionTrigger.project_id == project_id)
            .order_by(StrategyExecutionTrigger.created_at.desc())
            .first()
        )

    def get_active_for_project(
        self, project_id: str
    ) -> Optional[StrategyExecutionTrigger]:
        """Return the active (triggered or in_progress) trigger for a project, or None."""
        return (
            self._db.query(StrategyExecutionTrigger)
            .filter(
                StrategyExecutionTrigger.project_id == project_id,
                StrategyExecutionTrigger.status.in_(_ACTIVE_STATUSES),
            )
            .first()
        )

    def list_active_triggers(
        self, limit: Optional[int] = None
    ) -> List[StrategyExecutionTrigger]:
        """Return active (triggered or in_progress) triggers across all projects.

        When *limit* is provided the database applies the cap directly so only
        the required rows are fetched.
        """
        query = (
            self._db.query(StrategyExecutionTrigger)
            .filter(StrategyExecutionTrigger.status.in_(_ACTIVE_STATUSES))
            .order_by(StrategyExecutionTrigger.triggered_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def count_triggers_by_status(self, status: str) -> int:
        """Return the count of triggers with the given status."""
        return (
            self._db.query(StrategyExecutionTrigger)
            .filter(StrategyExecutionTrigger.status == status)
            .count()
        )

    def list_projects_awaiting_trigger(self) -> List[Tuple[str, str]]:
        """Return (project_id, approval_id) pairs where:
          - The project's latest strategy approval has status 'approved', and
          - No execution trigger is linked to that approval.

        This is the canonical "awaiting trigger" query.  It correctly excludes:
          - Projects whose latest approval is pending or rejected.
          - Projects whose latest approved approval already has a trigger (of any
            status, including completed or cancelled).

        Returns the full uncapped list so callers can compute an accurate count
        before slicing for display.
        """
        # Step 1 — Subquery: latest created_at timestamp per project.
        latest_ts_subq = (
            self._db.query(
                StrategyApproval.project_id,
                func.max(StrategyApproval.created_at).label("max_created_at"),
            )
            .group_by(StrategyApproval.project_id)
            .subquery()
        )

        # Step 2 — Join back to get the actual approval rows for those latest
        # timestamps and filter for status = 'approved'.
        latest_approved_rows = (
            self._db.query(StrategyApproval.id, StrategyApproval.project_id)
            .join(
                latest_ts_subq,
                (StrategyApproval.project_id == latest_ts_subq.c.project_id)
                & (
                    StrategyApproval.created_at
                    == latest_ts_subq.c.max_created_at
                ),
            )
            .filter(StrategyApproval.status == "approved")
            .all()
        )

        if not latest_approved_rows:
            return []

        # Step 3 — Find which of those approval IDs already have any trigger.
        approval_ids = [row[0] for row in latest_approved_rows]
        triggered_rows = (
            self._db.query(StrategyExecutionTrigger.approval_id)
            .filter(
                StrategyExecutionTrigger.approval_id.in_(approval_ids),
                StrategyExecutionTrigger.approval_id.isnot(None),
            )
            .distinct()
            .all()
        )
        triggered_ids = {row[0] for row in triggered_rows}

        # Step 4 — Return pairs not yet triggered.
        return [
            (project_id, approval_id)
            for approval_id, project_id in latest_approved_rows
            if approval_id not in triggered_ids
        ]
