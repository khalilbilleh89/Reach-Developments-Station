"""
strategy_approval.service

Business rules for the Strategy Approval Workflow (PR-V7-08).

Responsibilities
----------------
- Enforce single-active-approval invariant (at most one pending per project).
- Validate and execute state transitions:
    pending → approved
    pending → rejected
- Guard against reverse transitions and invalid states.
- Never mutate strategy, execution-package, project, pricing, or phasing data.

Forbidden
---------
  Reverse state transitions (approved → pending, rejected → pending)
  Mutation of strategy_generator or strategy_execution_package records
  Any cross-module DB writes
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ResourceNotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.strategy_approval.models import StrategyApproval
from app.modules.strategy_approval.repository import StrategyApprovalRepository

_logger = get_logger("reach_developments.strategy_approval")

# Allowed forward-only state transitions.
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"approved", "rejected"},
}


class StrategyApprovalService:
    """Orchestrates approval lifecycle operations."""

    def __init__(self, db: Session) -> None:
        self._repo = StrategyApprovalRepository(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_approval_request(
        self,
        project_id: str,
        strategy_snapshot: dict,
        execution_package_snapshot: dict,
    ) -> StrategyApproval:
        """Create a new pending approval request for a project.

        Raises ResourceNotFoundError when the project does not exist.
        Raises ConflictError when a pending approval already exists for the project.
        """
        project = self._repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        existing_pending = self._repo.get_pending_for_project(project_id)
        if existing_pending is not None:
            raise ConflictError(
                f"A pending approval already exists for project '{project_id}'. "
                "Resolve the existing request before creating a new one."
            )

        approval = StrategyApproval(
            project_id=project_id,
            strategy_snapshot=strategy_snapshot,
            execution_package_snapshot=execution_package_snapshot,
            status="pending",
        )
        record = self._repo.create(approval)
        _logger.info(
            "Approval request created: id=%s project_id=%s", record.id, project_id
        )
        return record

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def approve_strategy(
        self,
        approval_id: str,
        approved_by_user_id: str,
    ) -> StrategyApproval:
        """Transition a pending approval to approved.

        Raises ResourceNotFoundError when the approval record does not exist.
        Raises ValidationError when the approval is not in pending state.
        """
        approval = self._repo.get_by_id(approval_id)
        if approval is None:
            raise ResourceNotFoundError(f"Approval '{approval_id}' not found.")

        _assert_transition(approval, target="approved")

        approval.status = "approved"
        approval.approved_by_user_id = approved_by_user_id
        approval.approved_at = datetime.now(timezone.utc)
        record = self._repo.save(approval)
        _logger.info(
            "Strategy approved: id=%s project_id=%s by=%s",
            record.id,
            record.project_id,
            approved_by_user_id,
        )
        return record

    def reject_strategy(
        self,
        approval_id: str,
        rejection_reason: str,
    ) -> StrategyApproval:
        """Transition a pending approval to rejected.

        Raises ResourceNotFoundError when the approval record does not exist.
        Raises ValidationError when the approval is not in pending state.
        """
        approval = self._repo.get_by_id(approval_id)
        if approval is None:
            raise ResourceNotFoundError(f"Approval '{approval_id}' not found.")

        _assert_transition(approval, target="rejected")

        approval.status = "rejected"
        approval.rejection_reason = rejection_reason
        record = self._repo.save(approval)
        _logger.info(
            "Strategy rejected: id=%s project_id=%s reason=%r",
            record.id,
            record.project_id,
            rejection_reason,
        )
        return record

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_latest_approval(self, project_id: str) -> Optional[StrategyApproval]:
        """Return the most recently created approval for a project, or None.

        Raises ResourceNotFoundError when the project does not exist.
        """
        project = self._repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        return self._repo.get_latest_for_project(project_id)


# ---------------------------------------------------------------------------
# Pure helper — no I/O (easy to unit-test)
# ---------------------------------------------------------------------------


def _assert_transition(approval: StrategyApproval, target: str) -> None:
    """Raise ValidationError if the transition from current status → target is invalid.

    Only pending → approved and pending → rejected are allowed.
    """
    allowed = _VALID_TRANSITIONS.get(approval.status, set())
    if target not in allowed:
        raise ValidationError(
            f"Cannot transition approval from '{approval.status}' to '{target}'. "
            f"Allowed transitions from '{approval.status}': {sorted(allowed) or 'none'}."
        )
