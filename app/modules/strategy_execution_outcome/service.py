"""
strategy_execution_outcome.service

Business rules for the Strategy Execution Outcome module (PR-V7-10).

Responsibilities
----------------
- Enforce that outcome recording is only permitted for eligible trigger states.
- Manage append-only outcome history: re-recording supersedes the prior outcome.
- Compare intended strategy (from trigger snapshot) vs realized outcome.
- Derive match_status, divergence_summary, execution_quality, and
  has_material_divergence deterministically from persisted fields.
- Assemble project-scoped and portfolio-level outcome views.

Eligible trigger states for outcome recording
---------------------------------------------
  in_progress — execution is underway; interim outcome may be recorded.
  completed   — execution finished; final outcome may be recorded.

Forbidden
---------
  Recording outcomes for 'triggered' or 'cancelled' triggers.
  Mutating pricing, phasing, feasibility, or project source records.
  Rewriting prior approval, trigger, or outcome records.
  Recomputing pricing or phasing formulas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.strategy_execution_outcome.models import StrategyExecutionOutcome
from app.modules.strategy_execution_outcome.repository import (
    StrategyExecutionOutcomeRepository,
)
from app.modules.strategy_execution_outcome.schemas import (
    ExecutionOutcomeComparisonBlock,
    PortfolioExecutionOutcomeSummaryResponse,
    PortfolioOutcomeEntry,
    PortfolioOutcomeProjectEntry,
    ProjectExecutionOutcomeResponse,
    RecordExecutionOutcomeRequest,
    StrategyExecutionOutcomeResponse,
)
from app.modules.strategy_execution_trigger.models import StrategyExecutionTrigger

_logger = get_logger("reach_developments.strategy_execution_outcome")

# Portfolio project cap — consistent with other portfolio modules.
_PORTFOLIO_PROJECT_LIMIT = 50

# Trigger states that permit outcome recording.
_ELIGIBLE_TRIGGER_STATUSES = {"in_progress", "completed"}

# Comparison thresholds for price adjustment (percentage points).
# |diff| < 1 pp → exact_match; 1 pp ≤ |diff| < 5 pp → minor_variance; |diff| ≥ 5 pp → major_variance
_PRICE_MINOR_THRESHOLD = 1.0
_PRICE_MAJOR_THRESHOLD = 5.0

# Comparison threshold for phase delay (months).
# diff == 0 → exact_match; 0 < |diff| ≤ 1 month → minor_variance; |diff| > 1 month → major_variance
_PHASE_MINOR_THRESHOLD = 1.0


class StrategyExecutionOutcomeService:
    """Orchestrates execution outcome recording and comparison operations."""

    def __init__(self, db: Session) -> None:
        self._repo = StrategyExecutionOutcomeRepository(db)

    # ------------------------------------------------------------------
    # Record — public method returns a fully-built response
    # ------------------------------------------------------------------

    def record_execution_outcome(
        self,
        trigger_id: str,
        payload: RecordExecutionOutcomeRequest,
        recorded_by_user_id: str,
    ) -> StrategyExecutionOutcomeResponse:
        """Record the realized execution outcome for a trigger.

        Eligibility rule: the trigger must be in 'in_progress' or 'completed'
        state.  Recording for 'triggered' or 'cancelled' triggers is forbidden.

        History model: if a prior 'recorded' outcome already exists for this
        trigger, it is marked 'superseded' inside the same transaction before
        the new record is inserted.  The partial unique index on the DB
        guarantees at most one 'recorded' outcome per trigger at any time;
        any concurrent race that slips past the application-layer check is
        translated into a ConflictError (HTTP 409) by the repository.

        Returns a fully-built StrategyExecutionOutcomeResponse including the
        live comparison block — callers do not need to touch the repository.

        Raises ResourceNotFoundError when the trigger does not exist.
        Raises ValidationError when the trigger is not in an eligible state.
        Raises ConflictError when a concurrent recording wins the DB race.
        """
        trigger = self._repo.get_trigger(trigger_id)
        if trigger is None:
            raise ResourceNotFoundError(
                f"Execution trigger '{trigger_id}' not found."
            )

        if trigger.status not in _ELIGIBLE_TRIGGER_STATUSES:
            raise ValidationError(
                f"Cannot record an outcome for execution trigger '{trigger_id}': "
                f"trigger status is '{trigger.status}'. "
                f"Outcome recording requires the trigger to be in "
                f"'in_progress' or 'completed' state."
            )

        now = datetime.now(timezone.utc)
        outcome = StrategyExecutionOutcome(
            project_id=trigger.project_id,
            execution_trigger_id=trigger_id,
            approval_id=trigger.approval_id,
            status="recorded",
            actual_price_adjustment_pct=payload.actual_price_adjustment_pct,
            actual_phase_delay_months=payload.actual_phase_delay_months,
            actual_release_strategy=payload.actual_release_strategy,
            execution_summary=payload.execution_summary,
            outcome_result=payload.outcome_result,
            outcome_notes=payload.outcome_notes,
            recorded_by_user_id=recorded_by_user_id,
            recorded_at=now,
        )
        # Supersede prior outcomes and insert new one atomically.
        record = self._repo.supersede_and_create(outcome)
        _logger.info(
            "Execution outcome recorded: id=%s project_id=%s trigger_id=%s "
            "result=%s by=%s",
            record.id,
            record.project_id,
            trigger_id,
            record.outcome_result,
            recorded_by_user_id,
        )
        return build_outcome_response(record, trigger)

    # ------------------------------------------------------------------
    # Project read
    # ------------------------------------------------------------------

    def get_project_execution_outcome(
        self, project_id: str
    ) -> ProjectExecutionOutcomeResponse:
        """Return the latest execution outcome state for a project.

        Returns the most recent trigger context, eligibility flag, and the
        latest recorded outcome (or null when none has been recorded yet).

        Raises ResourceNotFoundError when the project does not exist.
        """
        project = self._repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        trigger = self._repo.get_latest_trigger_for_project(project_id)
        outcome_eligible = (
            trigger is not None and trigger.status in _ELIGIBLE_TRIGGER_STATUSES
        )

        latest_outcome = self._repo.get_latest_for_project(project_id)
        outcome_response: Optional[StrategyExecutionOutcomeResponse] = None
        if latest_outcome is not None:
            resolved_trigger = (
                trigger
                if trigger is not None and trigger.id == latest_outcome.execution_trigger_id
                else self._repo.get_trigger(latest_outcome.execution_trigger_id or "")
            )
            outcome_response = build_outcome_response(latest_outcome, resolved_trigger)

        return ProjectExecutionOutcomeResponse(
            project_id=project_id,
            execution_trigger_id=trigger.id if trigger else None,
            trigger_status=trigger.status if trigger else None,
            outcome_eligible=outcome_eligible,
            latest_outcome=outcome_response,
        )

    # ------------------------------------------------------------------
    # Portfolio read
    # ------------------------------------------------------------------

    def build_portfolio_execution_outcomes(
        self,
    ) -> PortfolioExecutionOutcomeSummaryResponse:
        """Assemble a portfolio-level execution outcome summary.

        Counts outcomes by result, lists recent recorded outcomes, and
        identifies projects whose latest completed trigger has no recorded
        outcome (one entry per project, not per trigger).

        List results are capped at _PORTFOLIO_PROJECT_LIMIT.
        Trigger data for the comparison block is batch-loaded in one query.
        """
        matched_count = self._repo.count_by_outcome_result("matched_strategy")
        partially_count = self._repo.count_by_outcome_result("partially_matched")
        diverged_count = self._repo.count_by_outcome_result("diverged")
        cancelled_count = self._repo.count_by_outcome_result("cancelled_execution")
        insufficient_count = self._repo.count_by_outcome_result("insufficient_data")

        # Recent outcomes — cap is pushed into SQL.
        recent_outcomes = self._repo.list_for_portfolio(limit=_PORTFOLIO_PROJECT_LIMIT)

        # Batch-load project names and trigger data — O(2) queries.
        outcome_project_ids = [o.project_id for o in recent_outcomes]
        projects_map: Dict[str, str] = {
            p.id: p.name
            for p in self._repo.list_projects_by_ids(outcome_project_ids)
        }
        trigger_ids = [
            o.execution_trigger_id
            for o in recent_outcomes
            if o.execution_trigger_id is not None
        ]
        triggers_map = self._repo.get_triggers_by_ids(trigger_ids)

        outcome_entries: List[PortfolioOutcomeEntry] = [
            PortfolioOutcomeEntry(
                project_id=outcome.project_id,
                project_name=projects_map.get(outcome.project_id, outcome.project_id),
                outcome=build_outcome_response(
                    outcome,
                    triggers_map.get(outcome.execution_trigger_id or ""),
                ),
            )
            for outcome in recent_outcomes
        ]

        # Projects awaiting outcome recording — project-based (one entry per project),
        # capped at _PORTFOLIO_PROJECT_LIMIT at the DB level.
        awaiting_pairs: List[Tuple[str, str]] = (
            self._repo.list_projects_awaiting_outcome(limit=_PORTFOLIO_PROJECT_LIMIT)
        )
        # Get the total count without the limit for the summary field.
        awaiting_count = self._repo.count_projects_awaiting_outcome()

        awaiting_project_ids = [pid for pid, _ in awaiting_pairs]
        awaiting_projects_map: Dict[str, str] = {
            p.id: p.name
            for p in self._repo.list_projects_by_ids(awaiting_project_ids)
        }

        awaiting_entries: List[PortfolioOutcomeProjectEntry] = [
            PortfolioOutcomeProjectEntry(
                project_id=pid,
                project_name=awaiting_projects_map.get(pid, pid),
                trigger_id=tid,
            )
            for pid, tid in awaiting_pairs
        ]

        return PortfolioExecutionOutcomeSummaryResponse(
            matched_strategy_count=matched_count,
            partially_matched_count=partially_count,
            diverged_count=diverged_count,
            cancelled_execution_count=cancelled_count,
            insufficient_data_count=insufficient_count,
            awaiting_outcome_count=awaiting_count,
            recent_outcomes=outcome_entries,
            awaiting_outcome_projects=awaiting_entries,
        )


# ---------------------------------------------------------------------------
# Public response builder — no I/O (easy to unit-test)
# ---------------------------------------------------------------------------


def build_outcome_response(
    outcome: StrategyExecutionOutcome,
    trigger: Optional[StrategyExecutionTrigger],
) -> StrategyExecutionOutcomeResponse:
    """Build the full outcome response including the comparison block.

    Public so that callers outside this module (e.g. tests) can construct
    typed responses without going through a full service instantiation.
    """
    comparison = compare_intended_vs_realized(trigger, outcome)
    return StrategyExecutionOutcomeResponse(
        id=outcome.id,
        project_id=outcome.project_id,
        execution_trigger_id=outcome.execution_trigger_id,
        approval_id=outcome.approval_id,
        status=outcome.status,  # type: ignore[arg-type]
        outcome_result=outcome.outcome_result,  # type: ignore[arg-type]
        actual_price_adjustment_pct=outcome.actual_price_adjustment_pct,
        actual_phase_delay_months=outcome.actual_phase_delay_months,
        actual_release_strategy=outcome.actual_release_strategy,
        execution_summary=outcome.execution_summary,
        outcome_notes=outcome.outcome_notes,
        recorded_by_user_id=outcome.recorded_by_user_id,
        recorded_at=outcome.recorded_at,
        created_at=outcome.created_at,
        updated_at=outcome.updated_at,
        comparison=comparison,
        has_material_divergence=comparison.has_material_divergence,
    )


def compare_intended_vs_realized(
    trigger: Optional[StrategyExecutionTrigger],
    outcome: StrategyExecutionOutcome,
) -> ExecutionOutcomeComparisonBlock:
    """Derive the intended vs realized comparison block deterministically.

    Intended values are extracted from the trigger's execution_package_snapshot
    (supporting_metrics sub-object).  If the trigger is absent or the snapshot
    does not contain supporting_metrics, all intended values are None.

    match_status classification:
      price_adjustment_pct — exact if |diff| < 1 pp, minor if 1–5 pp, major if ≥ 5 pp
      phase_delay_months   — exact if diff = 0, minor if 0 < |diff| ≤ 1 month, major if |diff| > 1 month
      release_strategy     — exact if equal, major_variance if different

    Overall match_status is the worst classification across all comparable fields.
    no_comparable_strategy is returned when no intended values are available.
    """
    intended_price: Optional[float] = None
    intended_phase: Optional[float] = None
    intended_release: Optional[str] = None

    if trigger is not None:
        pkg_snapshot = trigger.execution_package_snapshot
        if isinstance(pkg_snapshot, dict):
            metrics = pkg_snapshot.get("supporting_metrics")
            if isinstance(metrics, dict):
                raw_price = metrics.get("price_adjustment_pct")
                raw_phase = metrics.get("phase_delay_months")
                raw_release = metrics.get("release_strategy")
                if isinstance(raw_price, (int, float)):
                    intended_price = float(raw_price)
                if isinstance(raw_phase, (int, float)):
                    intended_phase = float(raw_phase)
                if isinstance(raw_release, str):
                    intended_release = raw_release

    actual_price = outcome.actual_price_adjustment_pct
    actual_phase = outcome.actual_phase_delay_months
    actual_release = outcome.actual_release_strategy

    # Evaluate per-field match statuses.
    field_statuses: List[str] = []
    divergence_parts: List[str] = []

    # Price adjustment comparison.
    if intended_price is not None and actual_price is not None:
        diff = abs(actual_price - intended_price)
        if diff < _PRICE_MINOR_THRESHOLD:
            field_statuses.append("exact_match")
        elif diff < _PRICE_MAJOR_THRESHOLD:
            field_statuses.append("minor_variance")
            divergence_parts.append(
                f"price adjustment: intended {intended_price:+.1f}% vs actual {actual_price:+.1f}%"
            )
        else:
            field_statuses.append("major_variance")
            divergence_parts.append(
                f"price adjustment: intended {intended_price:+.1f}% vs actual {actual_price:+.1f}%"
            )

    # Phase delay comparison.
    if intended_phase is not None and actual_phase is not None:
        diff = abs(actual_phase - intended_phase)
        if diff == 0:
            field_statuses.append("exact_match")
        elif diff <= _PHASE_MINOR_THRESHOLD:
            field_statuses.append("minor_variance")
            divergence_parts.append(
                f"phase delay: intended {intended_phase:.1f}m vs actual {actual_phase:.1f}m"
            )
        else:
            field_statuses.append("major_variance")
            divergence_parts.append(
                f"phase delay: intended {intended_phase:.1f}m vs actual {actual_phase:.1f}m"
            )

    # Release strategy comparison.
    if intended_release is not None and actual_release is not None:
        if intended_release == actual_release:
            field_statuses.append("exact_match")
        else:
            field_statuses.append("major_variance")
            divergence_parts.append(
                f"release strategy: intended '{intended_release}' vs actual '{actual_release}'"
            )

    # Determine overall match_status.
    if not field_statuses:
        match_status = "no_comparable_strategy"
    elif "major_variance" in field_statuses:
        match_status = "major_variance"
    elif "minor_variance" in field_statuses:
        match_status = "minor_variance"
    else:
        match_status = "exact_match"

    # Build divergence summary text.
    if match_status == "no_comparable_strategy":
        divergence_summary = (
            "No comparable intended strategy values available for comparison."
        )
    elif match_status == "exact_match":
        divergence_summary = "Realized outcome matches the intended strategy."
    else:
        divergence_summary = "Divergence detected: " + "; ".join(divergence_parts) + "."

    # Derive execution quality.
    quality_map: Dict[str, str] = {
        "exact_match": "high",
        "minor_variance": "medium",
        "major_variance": "low",
        "no_comparable_strategy": "unknown",
    }
    execution_quality = quality_map[match_status]

    return ExecutionOutcomeComparisonBlock(
        intended_price_adjustment_pct=intended_price,
        actual_price_adjustment_pct=actual_price,
        intended_phase_delay_months=intended_phase,
        actual_phase_delay_months=actual_phase,
        intended_release_strategy=intended_release,
        actual_release_strategy=actual_release,
        match_status=match_status,  # type: ignore[arg-type]
        divergence_summary=divergence_summary,
        execution_quality=execution_quality,  # type: ignore[arg-type]
        has_material_divergence=(match_status == "major_variance"),
    )

