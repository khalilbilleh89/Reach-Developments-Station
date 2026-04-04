"""
strategy_execution_trigger.repository

Data access layer for the Strategy Execution Trigger module (PR-V7-09).

All write operations go through this layer.  Cross-module DB logic is
forbidden — this repository only touches strategy_execution_triggers,
strategy_approvals (read-only), and projects (read-only).
"""

from typing import List, Optional

from sqlalchemy.orm import Session

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
        """Persist a new trigger record and return it with generated fields."""
        self._db.add(trigger)
        self._db.commit()
        self._db.refresh(trigger)
        return trigger

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

    def list_active_triggers(self) -> List[StrategyExecutionTrigger]:
        """Return all active (triggered or in_progress) triggers across all projects."""
        return (
            self._db.query(StrategyExecutionTrigger)
            .filter(StrategyExecutionTrigger.status.in_(_ACTIVE_STATUSES))
            .order_by(StrategyExecutionTrigger.triggered_at.desc())
            .all()
        )

    def count_triggers_by_status(self, status: str) -> int:
        """Return the count of triggers with the given status."""
        return (
            self._db.query(StrategyExecutionTrigger)
            .filter(StrategyExecutionTrigger.status == status)
            .count()
        )

    def get_approved_project_ids(self) -> List[str]:
        """Return distinct project IDs that have at least one approved strategy approval."""
        rows = (
            self._db.query(StrategyApproval.project_id)
            .filter(StrategyApproval.status == "approved")
            .distinct()
            .all()
        )
        return [row[0] for row in rows]
