"""
strategy_learning.service

Learning logic for the Strategy Learning & Confidence Recalibration Engine
(PR-V7-11).

Responsibilities
----------------
- Aggregate historical execution outcomes for a project.
- Derive deterministic accuracy metrics and confidence scores.
- Persist results via StrategyLearningRepository (upsert — no mutation of
  source outcome records).
- Assemble project-level and portfolio-level learning insight responses.

Confidence formula (deterministic, no ML)
-----------------------------------------
  confidence = (match_rate * 0.6) + ((1 - divergence_rate) * 0.4)

Low-sample guard
-----------------
  When sample_size < LOW_SAMPLE_THRESHOLD (5), confidence is capped at
  LOW_SAMPLE_CONFIDENCE_CAP (0.5).

Accuracy sub-scores
-------------------
  pricing_accuracy_score: fraction of outcomes with non-null actual and
    intended price values where |diff| < PRICE_MAJOR_THRESHOLD (5 pp).
  phasing_accuracy_score: fraction of outcomes with non-null actual and
    intended phase values where |diff| <= PHASE_MINOR_THRESHOLD (1 month).
  overall_strategy_accuracy: match_rate (alias for readability).

Trend direction
---------------
  Derived from change in confidence_score vs. prior stored value:
    Δ > +0.05  → "improving"
    Δ < -0.05  → "declining"
    prior == None → "insufficient_data"
    else → "stable"

Forbidden
---------
  Mutating outcome, trigger, approval, or strategy source records.
  Recomputing pricing / phasing / IRR formulas.
  Introducing ML models or external scoring services.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.core.logging import get_logger
from app.modules.strategy_execution_outcome.models import StrategyExecutionOutcome
from app.modules.strategy_learning.models import StrategyLearningMetrics
from app.modules.strategy_learning.repository import StrategyLearningRepository
from app.modules.strategy_learning.schemas import (
    AccuracyBreakdown,
    PortfolioLearningProjectEntry,
    PortfolioLearningSummaryResponse,
    StrategyLearningMetricsResponse,
    StrategyLearningResponse,
)

_logger = get_logger("reach_developments.strategy_learning")

# Confidence formula weights
_MATCH_WEIGHT = 0.6
_DIVERGENCE_WEIGHT = 0.4

# Low-sample guard
_LOW_SAMPLE_THRESHOLD = 5
_LOW_SAMPLE_CONFIDENCE_CAP = 0.5

# Trend detection threshold
_TREND_THRESHOLD = 0.05

# Accuracy dimension thresholds (mirrors compare_intended_vs_realized thresholds)
_PRICE_MAJOR_THRESHOLD = 5.0   # |diff| < 5 pp = accurate
_PHASE_MINOR_THRESHOLD = 1.0   # |diff| <= 1 month = accurate

# Portfolio top/weak list sizes
_PORTFOLIO_TOP_COUNT = 5
_PORTFOLIO_WEAK_COUNT = 5
_PORTFOLIO_MIN_SAMPLE_FOR_RANKING = 2

# Confidence thresholds for high/low counts
_HIGH_CONFIDENCE_THRESHOLD = 0.7
_LOW_CONFIDENCE_THRESHOLD = 0.4

# Portfolio project cap
_PORTFOLIO_PROJECT_LIMIT = 50

# Aggregate row strategy_type label
_ALL_STRATEGIES_LABEL = "_all_"


class StrategyLearningService:
    """Orchestrates strategy learning computation and response assembly."""

    def __init__(self, db: Session) -> None:
        self._repo = StrategyLearningRepository(db)

    # ------------------------------------------------------------------
    # Project-level recalibration
    # ------------------------------------------------------------------

    def recalibrate_project(self, project_id: str) -> StrategyLearningResponse:
        """Recompute learning metrics for a project and return the response.

        Reads all 'recorded' outcomes, derives deterministic accuracy and
        confidence signals, upserts StrategyLearningMetrics rows, and returns
        the full project-level learning panel payload.

        Raises ResourceNotFoundError when the project does not exist.
        """
        project = self._repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        outcomes = self._repo.list_recorded_outcomes_for_project(project_id)
        if not outcomes:
            return StrategyLearningResponse(
                project_id=project_id,
                has_sufficient_data=False,
                overall_metrics=None,
                strategy_breakdowns=[],
            )

        # Fetch prior confidence values for trend computation (before upsert).
        prior_metrics_map = _build_prior_map(
            self._repo.get_metrics_for_project(project_id)
        )

        now = datetime.now(timezone.utc)

        # Compute aggregate row (all outcomes, strategy_type = "_all_").
        aggregate_row = _compute_metrics_row(
            project_id=project_id,
            strategy_type=_ALL_STRATEGIES_LABEL,
            outcomes=outcomes,
            prior_confidence=prior_metrics_map.get(_ALL_STRATEGIES_LABEL),
            now=now,
        )

        # Compute per-strategy-type rows.
        by_type: Dict[str, List[StrategyExecutionOutcome]] = {}
        for outcome in outcomes:
            stype = _extract_strategy_type(outcome)
            by_type.setdefault(stype, []).append(outcome)

        per_type_rows: List[StrategyLearningMetrics] = []
        for stype, type_outcomes in by_type.items():
            if stype == _ALL_STRATEGIES_LABEL:
                continue
            row = _compute_metrics_row(
                project_id=project_id,
                strategy_type=stype,
                outcomes=type_outcomes,
                prior_confidence=prior_metrics_map.get(stype),
                now=now,
            )
            per_type_rows.append(row)

        # Upsert all rows.
        all_rows = [aggregate_row] + per_type_rows
        upserted = self._repo.upsert_metrics_batch(all_rows)

        # Split upserted rows back into aggregate and per-type lists.
        upserted_aggregate: Optional[StrategyLearningMetrics] = next(
            (r for r in upserted if r.strategy_type == _ALL_STRATEGIES_LABEL), None
        )
        upserted_per_type = [
            r for r in upserted if r.strategy_type != _ALL_STRATEGIES_LABEL
        ]

        _logger.info(
            "Strategy learning recalibrated: project_id=%s outcomes=%d rows=%d",
            project_id,
            len(outcomes),
            len(upserted),
        )

        return _build_project_response(project_id, upserted_aggregate, upserted_per_type)

    # ------------------------------------------------------------------
    # Project-level read (no recalibration)
    # ------------------------------------------------------------------

    def get_project_learning(self, project_id: str) -> StrategyLearningResponse:
        """Return the current stored learning metrics for a project.

        Raises ResourceNotFoundError when the project does not exist.
        """
        project = self._repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        rows = self._repo.get_metrics_for_project(project_id)
        if not rows:
            return StrategyLearningResponse(
                project_id=project_id,
                has_sufficient_data=False,
                overall_metrics=None,
                strategy_breakdowns=[],
            )

        aggregate_row: Optional[StrategyLearningMetrics] = next(
            (r for r in rows if r.strategy_type == _ALL_STRATEGIES_LABEL), None
        )
        per_type_rows = [r for r in rows if r.strategy_type != _ALL_STRATEGIES_LABEL]
        return _build_project_response(project_id, aggregate_row, per_type_rows)

    # ------------------------------------------------------------------
    # Portfolio-level read
    # ------------------------------------------------------------------

    def get_portfolio_learning(self) -> PortfolioLearningSummaryResponse:
        """Assemble the portfolio-level learning summary from stored metrics.

        Returns aggregate statistics across all projects, top/weak lists, and
        per-project entries.  Results are capped at _PORTFOLIO_PROJECT_LIMIT.
        """
        aggregate_rows = self._repo.get_portfolio_aggregate_metrics()

        if not aggregate_rows:
            return PortfolioLearningSummaryResponse(
                total_projects_with_data=0,
                average_confidence_score=None,
                high_confidence_count=0,
                low_confidence_count=0,
                improving_count=0,
                declining_count=0,
                top_performing_projects=[],
                weak_area_projects=[],
                all_project_entries=[],
            )

        # Build project-name map.
        project_ids = [r.project_id for r in aggregate_rows]
        projects_map: Dict[str, str] = {
            p.id: p.name
            for p in self._repo.list_projects_by_ids(project_ids)
        }

        entries: List[PortfolioLearningProjectEntry] = [
            PortfolioLearningProjectEntry(
                project_id=row.project_id,
                project_name=projects_map.get(row.project_id, row.project_id),
                confidence_score=row.confidence_score,
                sample_size=row.sample_size,
                trend_direction=row.trend_direction,  # type: ignore[arg-type]
                overall_strategy_accuracy=row.overall_strategy_accuracy,
            )
            for row in aggregate_rows
        ]

        # Apply portfolio cap.
        entries = entries[:_PORTFOLIO_PROJECT_LIMIT]

        total = len(entries)
        avg_conf: Optional[float] = (
            sum(e.confidence_score for e in entries) / total if total > 0 else None
        )
        high_conf = sum(
            1 for e in entries if e.confidence_score >= _HIGH_CONFIDENCE_THRESHOLD
        )
        low_conf = sum(
            1 for e in entries if e.confidence_score < _LOW_CONFIDENCE_THRESHOLD
        )
        improving = sum(1 for e in entries if e.trend_direction == "improving")
        declining = sum(1 for e in entries if e.trend_direction == "declining")

        # Top-performing: best confidence, min sample required.
        ranked = [
            e for e in entries if e.sample_size >= _PORTFOLIO_MIN_SAMPLE_FOR_RANKING
        ]
        top = sorted(ranked, key=lambda e: e.confidence_score, reverse=True)[
            :_PORTFOLIO_TOP_COUNT
        ]
        weak = sorted(
            [e for e in ranked if e.confidence_score < _LOW_SAMPLE_CONFIDENCE_CAP],
            key=lambda e: e.confidence_score,
        )[:_PORTFOLIO_WEAK_COUNT]

        return PortfolioLearningSummaryResponse(
            total_projects_with_data=total,
            average_confidence_score=avg_conf,
            high_confidence_count=high_conf,
            low_confidence_count=low_conf,
            improving_count=improving,
            declining_count=declining,
            top_performing_projects=top,
            weak_area_projects=weak,
            all_project_entries=entries,
        )


# ---------------------------------------------------------------------------
# Pure computation helpers (no I/O — easy to unit-test)
# ---------------------------------------------------------------------------


def compute_confidence_score(
    match_rate: float,
    divergence_rate: float,
    sample_size: int,
) -> float:
    """Deterministic confidence formula.

    confidence = (match_rate * 0.6) + ((1 - divergence_rate) * 0.4)

    Capped at LOW_SAMPLE_CONFIDENCE_CAP when sample_size < LOW_SAMPLE_THRESHOLD.
    """
    raw = (match_rate * _MATCH_WEIGHT) + ((1.0 - divergence_rate) * _DIVERGENCE_WEIGHT)
    if sample_size < _LOW_SAMPLE_THRESHOLD:
        return min(raw, _LOW_SAMPLE_CONFIDENCE_CAP)
    return raw


def compute_trend_direction(
    current_confidence: float,
    prior_confidence: Optional[float],
) -> str:
    """Derive trend direction from delta in confidence score.

    Returns "improving" | "declining" | "stable" | "insufficient_data".
    """
    if prior_confidence is None:
        return "insufficient_data"
    delta = current_confidence - prior_confidence
    if delta > _TREND_THRESHOLD:
        return "improving"
    if delta < -_TREND_THRESHOLD:
        return "declining"
    return "stable"


def compute_pricing_accuracy(
    outcomes: Sequence[StrategyExecutionOutcome],
) -> Optional[float]:
    """Fraction of outcomes where the price adjustment was accurate.

    Accurate = |actual - intended| < PRICE_MAJOR_THRESHOLD.
    Returns None when no outcomes have both intended and actual price values.
    """
    total = 0
    accurate = 0
    for outcome in outcomes:
        actual = outcome.actual_price_adjustment_pct
        if actual is None:
            continue
        intended = _get_intended_price(outcome)
        if intended is None:
            continue
        total += 1
        if abs(actual - intended) < _PRICE_MAJOR_THRESHOLD:
            accurate += 1
    return (accurate / total) if total > 0 else None


def compute_phasing_accuracy(
    outcomes: Sequence[StrategyExecutionOutcome],
) -> Optional[float]:
    """Fraction of outcomes where the phase delay was accurate.

    Accurate = |actual - intended| <= PHASE_MINOR_THRESHOLD.
    Returns None when no outcomes have both intended and actual phase values.
    """
    total = 0
    accurate = 0
    for outcome in outcomes:
        actual = outcome.actual_phase_delay_months
        if actual is None:
            continue
        intended = _get_intended_phase(outcome)
        if intended is None:
            continue
        total += 1
        if abs(actual - intended) <= _PHASE_MINOR_THRESHOLD:
            accurate += 1
    return (accurate / total) if total > 0 else None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_strategy_type(outcome: StrategyExecutionOutcome) -> str:
    """Extract the strategy type label from an outcome's execution_trigger snapshot.

    Falls back to "unknown" when no strategy type can be identified.
    """
    # Outcomes don't have a direct strategy_type field, so we derive it from
    # the actual_release_strategy (closest proxy available without requiring a
    # trigger join here) or from the outcome_result.
    if outcome.actual_release_strategy:
        return outcome.actual_release_strategy.lower()
    return "unknown"


def _get_intended_price(outcome: StrategyExecutionOutcome) -> Optional[float]:
    """Extract intended price adjustment from the trigger snapshot stored in the
    outcome's execution_trigger relationship.

    Since the outcome ORM model does not carry the trigger snapshot directly,
    this returns None.  Sub-scores based on the actual values only can be
    derived at the service level when the trigger map is available.  For the
    learning service we rely on the outcome_result classification as the
    primary signal and treat pricing accuracy as None here.
    """
    return None


def _get_intended_phase(outcome: StrategyExecutionOutcome) -> Optional[float]:
    """See _get_intended_price — same rationale."""
    return None


def _compute_metrics_row(
    project_id: str,
    strategy_type: str,
    outcomes: List[StrategyExecutionOutcome],
    prior_confidence: Optional[float],
    now: datetime,
) -> StrategyLearningMetrics:
    """Compute a single StrategyLearningMetrics row from a list of outcomes."""
    total = len(outcomes)
    if total == 0:
        confidence = 0.0
        match_rate = 0.0
        partial_rate = 0.0
        divergence_rate = 0.0
    else:
        matched = sum(
            1 for o in outcomes if o.outcome_result == "matched_strategy"
        )
        partial = sum(
            1 for o in outcomes if o.outcome_result == "partially_matched"
        )
        diverged = sum(
            1 for o in outcomes if o.outcome_result == "diverged"
        )
        match_rate = matched / total
        partial_rate = partial / total
        divergence_rate = diverged / total
        confidence = compute_confidence_score(match_rate, divergence_rate, total)

    trend = compute_trend_direction(confidence, prior_confidence)
    pricing_acc = compute_pricing_accuracy(outcomes)
    phasing_acc = compute_phasing_accuracy(outcomes)

    return StrategyLearningMetrics(
        project_id=project_id,
        strategy_type=strategy_type,
        sample_size=total,
        match_rate=match_rate,
        partial_rate=partial_rate,
        divergence_rate=divergence_rate,
        confidence_score=confidence,
        pricing_accuracy_score=pricing_acc,
        phasing_accuracy_score=phasing_acc,
        overall_strategy_accuracy=match_rate,
        trend_direction=trend,
        last_updated=now,
    )


def _build_prior_map(
    existing: List[StrategyLearningMetrics],
) -> Dict[str, float]:
    """Build a {strategy_type: confidence_score} map from stored rows."""
    return {r.strategy_type: r.confidence_score for r in existing}


def _metrics_to_response(
    row: StrategyLearningMetrics,
) -> StrategyLearningMetricsResponse:
    """Convert a StrategyLearningMetrics ORM row to a response schema."""
    return StrategyLearningMetricsResponse(
        id=row.id,
        project_id=row.project_id,
        strategy_type=row.strategy_type,
        sample_size=row.sample_size,
        match_rate=row.match_rate,
        partial_rate=row.partial_rate,
        divergence_rate=row.divergence_rate,
        confidence_score=row.confidence_score,
        accuracy_breakdown=AccuracyBreakdown(
            pricing_accuracy_score=row.pricing_accuracy_score,
            phasing_accuracy_score=row.phasing_accuracy_score,
            overall_strategy_accuracy=row.overall_strategy_accuracy,
        ),
        trend_direction=row.trend_direction,  # type: ignore[arg-type]
        last_updated=row.last_updated,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _build_project_response(
    project_id: str,
    aggregate_row: Optional[StrategyLearningMetrics],
    per_type_rows: List[StrategyLearningMetrics],
) -> StrategyLearningResponse:
    """Build the StrategyLearningResponse from computed/loaded rows."""
    overall: Optional[StrategyLearningMetricsResponse] = (
        _metrics_to_response(aggregate_row) if aggregate_row is not None else None
    )
    breakdowns: List[StrategyLearningMetricsResponse] = [
        _metrics_to_response(r) for r in per_type_rows
    ]
    has_data = aggregate_row is not None and aggregate_row.sample_size > 0
    return StrategyLearningResponse(
        project_id=project_id,
        has_sufficient_data=has_data,
        overall_metrics=overall,
        strategy_breakdowns=breakdowns,
    )
