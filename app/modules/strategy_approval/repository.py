"""
strategy_approval.repository

Data access layer for the Strategy Approval Workflow (PR-V7-08).

All write operations go through this layer.  Cross-module DB logic is
forbidden — this repository only touches strategy_approvals and projects
(read-only check for project existence).
"""

from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.modules.projects.models import Project
from app.modules.strategy_approval.models import StrategyApproval


class StrategyApprovalRepository:
    """Data access layer for strategy approval records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Project helpers (read-only — project records are never mutated)
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> Optional[Project]:
        """Return a project by ID or None if not found."""
        return self._db.query(Project).filter(Project.id == project_id).first()

    # ------------------------------------------------------------------
    # Approval writes
    # ------------------------------------------------------------------

    def create(self, approval: StrategyApproval) -> StrategyApproval:
        """Persist a new approval record and return it with generated fields.

        Translates any IntegrityError (e.g. from the partial unique index on
        pending approvals per project) into ConflictError so concurrent races
        are surfaced as a clean HTTP 409 rather than an unhandled 500.
        """
        try:
            self._db.add(approval)
            self._db.commit()
            self._db.refresh(approval)
            return approval
        except IntegrityError:
            self._db.rollback()
            raise ConflictError(
                f"A pending approval already exists for project '{approval.project_id}'. "
                "Resolve the existing request before creating a new one."
            )

    def save(self, approval: StrategyApproval) -> StrategyApproval:
        """Flush an in-place-mutated approval record and return it refreshed."""
        self._db.add(approval)
        self._db.commit()
        self._db.refresh(approval)
        return approval

    # ------------------------------------------------------------------
    # Approval reads
    # ------------------------------------------------------------------

    def get_by_id(self, approval_id: str) -> Optional[StrategyApproval]:
        """Return a single approval record by primary key or None."""
        return (
            self._db.query(StrategyApproval)
            .filter(StrategyApproval.id == approval_id)
            .first()
        )

    def get_latest_for_project(self, project_id: str) -> Optional[StrategyApproval]:
        """Return the most recently created approval for a project, or None."""
        return (
            self._db.query(StrategyApproval)
            .filter(StrategyApproval.project_id == project_id)
            .order_by(StrategyApproval.created_at.desc())
            .first()
        )

    def get_pending_for_project(self, project_id: str) -> Optional[StrategyApproval]:
        """Return the active (pending) approval for a project, or None."""
        return (
            self._db.query(StrategyApproval)
            .filter(
                StrategyApproval.project_id == project_id,
                StrategyApproval.status == "pending",
            )
            .first()
        )

    def list_for_project(self, project_id: str) -> List[StrategyApproval]:
        """Return all approvals for a project ordered by creation time descending."""
        return (
            self._db.query(StrategyApproval)
            .filter(StrategyApproval.project_id == project_id)
            .order_by(StrategyApproval.created_at.desc())
            .all()
        )
