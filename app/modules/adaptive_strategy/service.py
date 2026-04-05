"""
adaptive_strategy.service

Adaptive Strategy Influence Layer (PR-V7-12).

Applies deterministic, bounded confidence-weighted influence to strategy
recommendation ranking.  The system will:

  1. Generate raw candidate strategies via StrategyGeneratorService.
  2. Load project-level learning metrics via AdaptiveStrategyRepository.
  3. Derive a per-scenario confidence influence weight using the stored
     strategy-type-specific metrics (falling back to the project-wide
     aggregate if no type-specific row exists).
  4. Compute an adjusted ranking score and re-rank.
  5. Return both the raw best strategy and the adaptive best strategy so
     leadership can always see both outputs.

Influence model (deterministic, bounded)
-----------------------------------------
  base_score         = irr (raw)
  type_metrics       = strategy_learning_metrics for (project, release_strategy)
                       or the '_all_' aggregate when no type row exists
  confidence_weight  = clamp(confidence_score − 0.5, −MAX_INFLUENCE, +MAX_INFLUENCE)
  adjusted_score     = base_score × (1 + confidence_weight × INFLUENCE_SCALE)

  MAX_INFLUENCE  = 0.3    (confidence can shift score by at most ±30%)
  INFLUENCE_SCALE = 0.10  (each unit of weight moves score by 10 %)

  Example:
    confidence_score=0.8  → weight=+0.3  → score × 1.03 (+3%)
    confidence_score=0.2  → weight=-0.3  → score × 0.97 (-3%)
    confidence_score=0.5  → weight= 0.0  → score unchanged (neutral)

  Low-sample guard: when sample_size < MIN_SAMPLE_FOR_INFLUENCE (5) the
  influence is further halved to limit drift from sparse data.

Confidence bands
----------------
  high        : confidence_score >= HIGH_CONFIDENCE_THRESHOLD (0.7)
  medium      : HIGH_CONFIDENCE_THRESHOLD > score >= LOW_CONFIDENCE_THRESHOLD (0.4)
  low         : score < LOW_CONFIDENCE_THRESHOLD
  insufficient: no learning metrics exist

Architecture constraints
------------------------
- Read-only — no source records are mutated.
- Deterministic — same inputs always produce the same output.
- Bounded — influence cannot overwhelm raw IRR economics.
- Explainable — raw and adaptive outputs are always both returned.
- No ML — all influence logic is formulaic and inspectable.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.core.logging import get_logger
from app.modules.adaptive_strategy.repository import AdaptiveStrategyRepository
from app.modules.adaptive_strategy.schemas import (
    AdaptiveStrategyComparisonBlock,
    AdaptiveStrategyResponse,
    ConfidenceBand,
    PortfolioAdaptiveStrategyProjectCard,
    PortfolioAdaptiveStrategySummaryResponse,
)
from app.modules.strategy_generator.service import StrategyGeneratorService
from app.modules.strategy_learning.models import StrategyLearningMetrics

_logger = get_logger("reach_developments.adaptive_strategy")

# ---------------------------------------------------------------------------
# Influence model constants
# ---------------------------------------------------------------------------

# Maximum fraction of confidence_score that can shift the adjusted score.
_MAX_INFLUENCE: float = 0.3

# Scale applied to the clamped confidence weight before multiplying the score.
_INFLUENCE_SCALE: float = 0.10

# Minimum sample size before full influence is applied.
_MIN_SAMPLE_FOR_INFLUENCE: int = 5

# Confidence band thresholds.
_HIGH_CONFIDENCE_THRESHOLD: float = 0.7
_LOW_CONFIDENCE_THRESHOLD: float = 0.4

# Portfolio top-N limits.
_TOP_N_CONFIDENT: int = 5
_TOP_N_LOW_CONFIDENCE: int = 5


# ---------------------------------------------------------------------------
# Public helpers (importable for unit tests)
# ---------------------------------------------------------------------------


def compute_confidence_band(confidence_score: Optional[float]) -> ConfidenceBand:
    """Map a confidence_score to a ConfidenceBand label.

    Returns 'insufficient' when no score is available.
    """
    if confidence_score is None:
        return "insufficient"
    if confidence_score >= _HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if confidence_score >= _LOW_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def compute_adjusted_score(
    raw_irr: float,
    confidence_score: Optional[float],
    sample_size: int,
) -> float:
    """Apply bounded confidence influence to a raw IRR score.

    When confidence_score is None (no metrics) the raw score is returned
    unchanged (neutral influence).

    Low-sample guard: when sample_size < _MIN_SAMPLE_FOR_INFLUENCE, the
    influence weight is halved to limit drift from sparse data.
    """
    if confidence_score is None:
        return raw_irr

    # Weight ∈ [−MAX_INFLUENCE, +MAX_INFLUENCE]
    weight = max(-_MAX_INFLUENCE, min(_MAX_INFLUENCE, confidence_score - 0.5))

    # Halve influence for small sample sizes.
    if sample_size < _MIN_SAMPLE_FOR_INFLUENCE:
        weight *= 0.5

    return raw_irr * (1.0 + weight * _INFLUENCE_SCALE)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _metrics_for_scenario(
    release_strategy: str,
    type_metrics_map: Dict[str, StrategyLearningMetrics],
    aggregate_metrics: Optional[StrategyLearningMetrics],
) -> Optional[StrategyLearningMetrics]:
    """Return the best-available metrics row for a release_strategy label.

    Preference order:
      1. Strategy-type-specific metrics (e.g. strategy_type='maintain').
      2. Project-wide '_all_' aggregate row.
      3. None (no metrics available → neutral influence).
    """
    return type_metrics_map.get(release_strategy) or aggregate_metrics


def _build_adjusted_reason(
    confidence_score: Optional[float],
    confidence_band: ConfidenceBand,
    sample_size: int,
    changed: bool,
) -> str:
    """Build a human-readable explanation of the confidence influence."""
    if confidence_score is None:
        return (
            "No learning metrics available for this project. "
            "Recommendation reflects raw simulation ranking only."
        )
    pct = round(confidence_score * 100)
    band_label = confidence_band.capitalize()
    if sample_size < _MIN_SAMPLE_FOR_INFLUENCE:
        influence_note = (
            f"Confidence influence was reduced (sample size {sample_size} < "
            f"{_MIN_SAMPLE_FOR_INFLUENCE} outcomes required for full weight)."
        )
    else:
        influence_note = (
            f"Confidence influence applied at full weight ({sample_size} outcomes)."
        )
    if changed:
        return (
            f"{band_label} confidence ({pct}%). "
            f"Confidence adjustment shifted the strategy selection. "
            f"{influence_note}"
        )
    return (
        f"{band_label} confidence ({pct}%). "
        f"Confidence adjustment did not change the top strategy selection. "
        f"{influence_note}"
    )


def _build_comparison(
    raw: Optional[object],
    adaptive: Optional[object],
) -> AdaptiveStrategyComparisonBlock:
    """Build an AdaptiveStrategyComparisonBlock from raw/adaptive SimulationResult objects."""
    if raw is None and adaptive is None:
        return AdaptiveStrategyComparisonBlock(
            raw_irr=None,
            adaptive_irr=None,
            raw_risk_score=None,
            adaptive_risk_score=None,
            raw_release_strategy=None,
            adaptive_release_strategy=None,
            raw_price_adjustment_pct=None,
            adaptive_price_adjustment_pct=None,
            raw_phase_delay_months=None,
            adaptive_phase_delay_months=None,
            changed_by_confidence=False,
        )
    raw_strategy = raw.release_strategy if raw else None
    adaptive_strategy = adaptive.release_strategy if adaptive else None
    changed = (
        raw_strategy != adaptive_strategy
        or (raw.price_adjustment_pct if raw else None)
        != (adaptive.price_adjustment_pct if adaptive else None)
        or (raw.phase_delay_months if raw else None)
        != (adaptive.phase_delay_months if adaptive else None)
    ) if raw and adaptive else False

    return AdaptiveStrategyComparisonBlock(
        raw_irr=raw.irr if raw else None,
        adaptive_irr=adaptive.irr if adaptive else None,
        raw_risk_score=raw.risk_score if raw else None,
        adaptive_risk_score=adaptive.risk_score if adaptive else None,
        raw_release_strategy=raw_strategy,
        adaptive_release_strategy=adaptive_strategy,
        raw_price_adjustment_pct=raw.price_adjustment_pct if raw else None,
        adaptive_price_adjustment_pct=adaptive.price_adjustment_pct if adaptive else None,
        raw_phase_delay_months=raw.phase_delay_months if raw else None,
        adaptive_phase_delay_months=adaptive.phase_delay_months if adaptive else None,
        changed_by_confidence=changed,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AdaptiveStrategyService:
    """Orchestrates learning-aware strategy recommendation ranking."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = AdaptiveStrategyRepository(db)
        self._generator = StrategyGeneratorService(db)

    # ------------------------------------------------------------------
    # Project-level
    # ------------------------------------------------------------------

    def get_project_adaptive_strategy(
        self, project_id: str
    ) -> AdaptiveStrategyResponse:
        """Return confidence-adjusted strategy recommendation for a project.

        Raises ResourceNotFoundError when the project does not exist.
        All source records are read-only — nothing is mutated.
        """
        project = self._repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        # 1. Raw strategy ranking from simulation engine.
        try:
            rec = self._generator.generate_recommended_strategy(project_id)
        except ResourceNotFoundError:
            raise

        raw_best = rec.best_strategy
        top_strategies = rec.top_strategies  # already ranked by raw IRR

        # 2. Load learning metrics.
        all_metrics = self._repo.get_all_metrics_for_project(project_id)
        type_metrics_map: Dict[str, StrategyLearningMetrics] = {
            m.strategy_type: m
            for m in all_metrics
            if m.strategy_type != "_all_"
        }
        aggregate_metrics: Optional[StrategyLearningMetrics] = next(
            (m for m in all_metrics if m.strategy_type == "_all_"), None
        )

        # 3. Derive confidence metadata.
        confidence_score = (
            aggregate_metrics.confidence_score if aggregate_metrics is not None else None
        )
        sample_size = aggregate_metrics.sample_size if aggregate_metrics is not None else 0
        trend_direction = (
            aggregate_metrics.trend_direction
            if aggregate_metrics is not None
            else "insufficient_data"
        )
        confidence_band = compute_confidence_band(confidence_score)
        low_confidence_flag = confidence_band in ("low", "insufficient")

        # 4. Apply confidence influence to re-rank top strategies.
        scored: List[Tuple[float, object]] = []
        for scenario in top_strategies:
            metrics = _metrics_for_scenario(
                scenario.release_strategy, type_metrics_map, aggregate_metrics
            )
            m_confidence = metrics.confidence_score if metrics else None
            m_sample = metrics.sample_size if metrics else 0
            adj_score = compute_adjusted_score(scenario.irr, m_confidence, m_sample)
            scored.append((adj_score, scenario))

        # Sort by adjusted score descending; preserve raw order for ties.
        scored.sort(key=lambda t: -t[0])
        adaptive_best = scored[0][1] if scored else None

        confidence_influence_applied = (
            confidence_score is not None
            and confidence_score != 0.5
            and sample_size > 0
        )
        changed = (
            raw_best is not None
            and adaptive_best is not None
            and (
                raw_best.release_strategy != adaptive_best.release_strategy
                or raw_best.price_adjustment_pct != adaptive_best.price_adjustment_pct
                or raw_best.phase_delay_months != adaptive_best.phase_delay_months
            )
        )

        adjusted_reason = _build_adjusted_reason(
            confidence_score, confidence_band, sample_size, changed
        )
        comparison = _build_comparison(raw_best, adaptive_best)

        _logger.info(
            "adaptive_strategy: project=%s confidence=%.3f band=%s changed=%s",
            project_id,
            confidence_score or 0.0,
            confidence_band,
            changed,
        )

        return AdaptiveStrategyResponse(
            project_id=project_id,
            project_name=project.name,
            raw_best_strategy=raw_best.release_strategy if raw_best else None,
            raw_best_irr=raw_best.irr if raw_best else None,
            raw_best_risk_score=raw_best.risk_score if raw_best else None,
            raw_best_price_adjustment_pct=raw_best.price_adjustment_pct if raw_best else None,
            raw_best_phase_delay_months=raw_best.phase_delay_months if raw_best else None,
            adaptive_best_strategy=adaptive_best.release_strategy if adaptive_best else None,
            adaptive_best_irr=adaptive_best.irr if adaptive_best else None,
            adaptive_best_risk_score=adaptive_best.risk_score if adaptive_best else None,
            adaptive_best_price_adjustment_pct=adaptive_best.price_adjustment_pct if adaptive_best else None,
            adaptive_best_phase_delay_months=adaptive_best.phase_delay_months if adaptive_best else None,
            confidence_score=confidence_score,
            confidence_band=confidence_band,
            confidence_influence_applied=confidence_influence_applied,
            low_confidence_flag=low_confidence_flag,
            sample_size=sample_size,
            trend_direction=trend_direction,
            adjusted_reason=adjusted_reason,
            comparison=comparison,
        )

    # ------------------------------------------------------------------
    # Portfolio-level
    # ------------------------------------------------------------------

    def build_portfolio_adaptive_strategy_summary(
        self,
    ) -> PortfolioAdaptiveStrategySummaryResponse:
        """Return portfolio-wide confidence-adjusted strategy summary.

        Evaluates all projects.  Per-project failures are caught and logged;
        the project receives a neutral/insufficient card rather than failing
        the whole response.  All source records are read-only.
        """
        all_projects = self._repo.list_all_projects()
        project_ids = [p.id for p in all_projects]

        # Batch-load all aggregate learning metrics in a single query.
        metrics_map = self._repo.get_metrics_by_project_ids(project_ids)

        # Build a project_id → name lookup.
        name_map = {p.id: p.name for p in all_projects}

        cards: List[PortfolioAdaptiveStrategyProjectCard] = []
        for project in all_projects:
            pid = project.id
            pname = name_map[pid]
            try:
                result = self.get_project_adaptive_strategy(pid)
                cards.append(
                    PortfolioAdaptiveStrategyProjectCard(
                        project_id=pid,
                        project_name=pname,
                        raw_best_strategy=result.raw_best_strategy,
                        adaptive_best_strategy=result.adaptive_best_strategy,
                        confidence_score=result.confidence_score,
                        confidence_band=result.confidence_band,
                        confidence_influence_applied=result.confidence_influence_applied,
                        low_confidence_flag=result.low_confidence_flag,
                        sample_size=result.sample_size,
                        trend_direction=result.trend_direction,
                        adjusted_reason=result.adjusted_reason,
                    )
                )
            except Exception:
                _logger.exception(
                    "adaptive_strategy: portfolio — failed for project=%s", pid
                )
                cards.append(
                    PortfolioAdaptiveStrategyProjectCard(
                        project_id=pid,
                        project_name=pname,
                        raw_best_strategy=None,
                        adaptive_best_strategy=None,
                        confidence_score=None,
                        confidence_band="insufficient",
                        confidence_influence_applied=False,
                        low_confidence_flag=True,
                        sample_size=0,
                        trend_direction="insufficient_data",
                        adjusted_reason=(
                            "Strategy evaluation failed for this project."
                        ),
                    )
                )

        # Sort by confidence_score descending (None last).
        cards.sort(
            key=lambda c: (
                c.confidence_score is None,
                -(c.confidence_score or 0.0),
            )
        )

        high_confidence = sum(1 for c in cards if c.confidence_band == "high")
        low_confidence = sum(
            1 for c in cards if c.confidence_band in ("low", "insufficient")
        )
        adjusted = sum(1 for c in cards if c.confidence_influence_applied and
                       _card_changed(c))
        neutral = len(cards) - adjusted

        top_confident = [
            c for c in cards if c.confidence_band == "high"
        ][:_TOP_N_CONFIDENT]
        top_low = [
            c for c in cards if c.low_confidence_flag
        ][:_TOP_N_LOW_CONFIDENCE]

        return PortfolioAdaptiveStrategySummaryResponse(
            total_projects=len(cards),
            high_confidence_projects=high_confidence,
            low_confidence_projects=low_confidence,
            confidence_adjusted_projects=adjusted,
            neutral_projects=neutral,
            top_confident_recommendations=top_confident,
            top_low_confidence_projects=top_low,
            project_cards=cards,
        )


def _card_changed(card: PortfolioAdaptiveStrategyProjectCard) -> bool:
    """Return True when the card's raw and adaptive strategies differ."""
    return card.raw_best_strategy != card.adaptive_best_strategy
