"""
strategy_execution_trigger.service

Business rules for the Strategy Execution Trigger module (PR-V7-09).

Responsibilities
----------------
- Enforce that execution triggers may only be created from approved strategies.
- Enforce the single-active-trigger invariant (at most one active trigger per
  project at a time).
- Validate and execute state transitions:
    triggered   → in_progress
    triggered   → cancelled
    in_progress → completed
    in_progress → cancelled
- Guard against reverse transitions and transitions from terminal states.
- Freeze the approved strategy context (snapshot) at trigger creation time.
- Assemble portfolio-level trigger summary.

Forbidden
---------
  Trigger creation when the latest strategy approval is not 'approved'.
  Multiple concurrent active triggers per project.
  Transitions from terminal states (completed, cancelled).
  Mutation of strategy, execution-package, pricing, phasing, or project records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ResourceNotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.strategy_execution_trigger.models import StrategyExecutionTrigger
from app.modules.strategy_execution_trigger.repository import (
    StrategyExecutionTriggerRepository,
)
from app.modules.strategy_execution_trigger.schemas import (
    PortfolioExecutionTriggerSummaryResponse,
    PortfolioProjectEntry,
    PortfolioTriggerEntry,
    StrategyExecutionTriggerResponse,
)

_logger = get_logger("reach_developments.strategy_execution_trigger")

# Portfolio project cap — consistent with other portfolio modules.
_PORTFOLIO_PROJECT_LIMIT = 50

# Allowed forward-only state transitions.
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "triggered": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
}

# Status values that represent an active (not terminal) execution handoff.
_ACTIVE_STATUSES = {"triggered", "in_progress"}


class StrategyExecutionTriggerService:
    """Orchestrates execution trigger lifecycle operations."""

    def __init__(self, db: Session) -> None:
        self._repo = StrategyExecutionTriggerRepository(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_execution_trigger(
        self,
        project_id: str,
        triggered_by_user_id: str,
    ) -> StrategyExecutionTrigger:
        """Create a formal execution handoff trigger for an approved project strategy.

        Raises ResourceNotFoundError when the project does not exist.
        Raises ValidationError when the latest strategy approval is not 'approved'.
        Raises ConflictError when an active trigger already exists for the project.
        """
        project = self._repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        latest_approval = self._repo.get_latest_approval_for_project(project_id)
        if latest_approval is None or latest_approval.status != "approved":
            current_status = (
                f"'{latest_approval.status}'" if latest_approval else "none"
            )
            raise ValidationError(
                f"Cannot create an execution trigger for project '{project_id}': "
                f"the latest strategy approval status is {current_status}. "
                "An execution trigger requires an 'approved' strategy approval."
            )

        existing_active = self._repo.get_active_for_project(project_id)
        if existing_active is not None:
            raise ConflictError(
                f"An active execution trigger (id='{existing_active.id}', "
                f"status='{existing_active.status}') already exists for project "
                f"'{project_id}'. Resolve the existing trigger before creating a new one."
            )

        now = datetime.now(timezone.utc)
        trigger = StrategyExecutionTrigger(
            project_id=project_id,
            approval_id=latest_approval.id,
            strategy_snapshot=latest_approval.strategy_snapshot,
            execution_package_snapshot=latest_approval.execution_package_snapshot,
            status="triggered",
            triggered_by_user_id=triggered_by_user_id,
            triggered_at=now,
        )
        record = self._repo.create(trigger)
        _logger.info(
            "Execution trigger created: id=%s project_id=%s approval_id=%s by=%s",
            record.id,
            project_id,
            latest_approval.id,
            triggered_by_user_id,
        )
        return record

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def mark_in_progress(
        self,
        trigger_id: str,
        user_id: str,
    ) -> StrategyExecutionTrigger:
        """Transition a triggered execution to in_progress.

        Raises ResourceNotFoundError when the trigger record does not exist.
        Raises ValidationError when the trigger is not in 'triggered' state.
        """
        trigger = self._repo.get_by_id(trigger_id)
        if trigger is None:
            raise ResourceNotFoundError(f"Execution trigger '{trigger_id}' not found.")

        _assert_transition(trigger, target="in_progress")

        trigger.status = "in_progress"
        record = self._repo.save(trigger)
        _logger.info(
            "Execution trigger started: id=%s project_id=%s by=%s",
            record.id,
            record.project_id,
            user_id,
        )
        return record

    def mark_completed(
        self,
        trigger_id: str,
        user_id: str,
    ) -> StrategyExecutionTrigger:
        """Transition an in_progress execution to completed.

        Raises ResourceNotFoundError when the trigger record does not exist.
        Raises ValidationError when the trigger is not in 'in_progress' state.
        """
        trigger = self._repo.get_by_id(trigger_id)
        if trigger is None:
            raise ResourceNotFoundError(f"Execution trigger '{trigger_id}' not found.")

        _assert_transition(trigger, target="completed")

        trigger.status = "completed"
        trigger.completed_at = datetime.now(timezone.utc)
        record = self._repo.save(trigger)
        _logger.info(
            "Execution trigger completed: id=%s project_id=%s by=%s",
            record.id,
            record.project_id,
            user_id,
        )
        return record

    def cancel_trigger(
        self,
        trigger_id: str,
        user_id: str,
        cancellation_reason: str,
    ) -> StrategyExecutionTrigger:
        """Cancel a triggered or in_progress execution.

        Raises ResourceNotFoundError when the trigger record does not exist.
        Raises ValidationError when the trigger is in a terminal state.
        """
        trigger = self._repo.get_by_id(trigger_id)
        if trigger is None:
            raise ResourceNotFoundError(f"Execution trigger '{trigger_id}' not found.")

        _assert_transition(trigger, target="cancelled")

        trigger.status = "cancelled"
        trigger.cancelled_at = datetime.now(timezone.utc)
        trigger.cancellation_reason = cancellation_reason
        record = self._repo.save(trigger)
        _logger.info(
            "Execution trigger cancelled: id=%s project_id=%s by=%s reason=%r",
            record.id,
            record.project_id,
            user_id,
            cancellation_reason,
        )
        return record

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_latest_execution_trigger(
        self, project_id: str
    ) -> Optional[StrategyExecutionTrigger]:
        """Return the most recently created trigger for a project, or None.

        Raises ResourceNotFoundError when the project does not exist.
        """
        project = self._repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        return self._repo.get_latest_for_project(project_id)

    def get_portfolio_trigger_summary(
        self,
    ) -> PortfolioExecutionTriggerSummaryResponse:
        """Assemble a portfolio-level execution trigger summary.

        Counts triggers by status, lists active execution handoffs, and
        identifies approved projects awaiting their first trigger.

        Capped at _PORTFOLIO_PROJECT_LIMIT projects per active/awaiting list.
        """
        triggered_count = self._repo.count_triggers_by_status("triggered")
        in_progress_count = self._repo.count_triggers_by_status("in_progress")
        completed_count = self._repo.count_triggers_by_status("completed")
        cancelled_count = self._repo.count_triggers_by_status("cancelled")

        # Active triggers and their project names.
        active_triggers = self._repo.list_active_triggers()[:_PORTFOLIO_PROJECT_LIMIT]
        active_project_ids = [t.project_id for t in active_triggers]
        active_projects_map = {
            p.id: p.name
            for p in self._repo.list_projects_by_ids(active_project_ids)
        }

        active_entries: List[PortfolioTriggerEntry] = []
        for trigger in active_triggers:
            project_name = active_projects_map.get(trigger.project_id, trigger.project_id)
            active_entries.append(
                PortfolioTriggerEntry(
                    project_id=trigger.project_id,
                    project_name=project_name,
                    trigger=StrategyExecutionTriggerResponse.model_validate(trigger),
                )
            )

        # Projects with approved strategies but no active trigger.
        approved_pids = set(self._repo.get_approved_project_ids())
        active_pids_set = set(active_project_ids)
        awaiting_pids = list(approved_pids - active_pids_set)[:_PORTFOLIO_PROJECT_LIMIT]
        awaiting_projects_data = self._repo.list_projects_by_ids(awaiting_pids)
        awaiting_projects_map = {p.id: p.name for p in awaiting_projects_data}

        awaiting_entries: List[PortfolioProjectEntry] = [
            PortfolioProjectEntry(
                project_id=pid,
                project_name=awaiting_projects_map.get(pid, pid),
            )
            for pid in awaiting_pids
        ]

        return PortfolioExecutionTriggerSummaryResponse(
            triggered_count=triggered_count,
            in_progress_count=in_progress_count,
            completed_count=completed_count,
            cancelled_count=cancelled_count,
            awaiting_trigger_count=len(awaiting_entries),
            active_triggers=active_entries,
            awaiting_trigger_projects=awaiting_entries,
        )


# ---------------------------------------------------------------------------
# Pure helper — no I/O (easy to unit-test)
# ---------------------------------------------------------------------------


def _assert_transition(trigger: StrategyExecutionTrigger, target: str) -> None:
    """Raise ValidationError if the transition from current status → target is invalid.

    Allowed transitions:
      triggered   → in_progress, cancelled
      in_progress → completed, cancelled

    Terminal states (completed, cancelled) allow no further transitions.
    """
    allowed = _VALID_TRANSITIONS.get(trigger.status, set())
    if target not in allowed:
        raise ValidationError(
            f"Cannot transition execution trigger from '{trigger.status}' to '{target}'. "
            f"Allowed transitions from '{trigger.status}': {sorted(allowed) or 'none'}."
        )
