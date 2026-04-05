"""
strategy_learning.models

ORM model for the StrategyLearningMetrics entity (PR-V7-11).

Persists aggregated, deterministically derived learning signals for a
project / strategy-type pair.  Records are upserted — never appended — so
each row always represents the current best estimate for that pair.

Confidence formula (deterministic, no ML):
  confidence = (match_rate * 0.6) + ((1 - divergence_rate) * 0.4)
  Capped at 0.5 when sample_size < 5 (low-sample guard).

Accuracy sub-scores (each in [0, 1]):
  pricing_accuracy_score   — fraction of outcomes where price adjustment matched
  phasing_accuracy_score   — fraction of outcomes where phase delay matched
  overall_strategy_accuracy — match_rate (alias kept for readability)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

_LOW_SAMPLE_THRESHOLD = 5
_LOW_SAMPLE_CONFIDENCE_CAP = 0.5


class StrategyLearningMetrics(Base, TimestampMixin):
    """Aggregated learning metrics for a (project, strategy_type) pair.

    Upserted each time the learning service recomputes confidence for this
    project.  The ``last_updated`` column records when the metrics were last
    recalculated; ``created_at`` / ``updated_at`` are managed by TimestampMixin.
    """

    __tablename__ = "strategy_learning_metrics"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Strategy type label — e.g. "maintain", "accelerate", "hold", or "_all_"
    # for the project-wide aggregate row.
    strategy_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Number of recorded outcomes contributing to this metric row.
    sample_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Fraction of outcomes whose outcome_result was 'matched_strategy'.
    match_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    # Fraction of outcomes whose outcome_result was 'partially_matched'.
    partial_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    # Fraction of outcomes whose outcome_result was 'diverged'.
    divergence_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    # Composite confidence score in [0, 1].
    # Capped at _LOW_SAMPLE_CONFIDENCE_CAP when sample_size < _LOW_SAMPLE_THRESHOLD.
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    # Per-dimension accuracy sub-scores (fractions of outcomes that matched
    # in that dimension; None when there were no comparable values).
    pricing_accuracy_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    phasing_accuracy_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    overall_strategy_accuracy: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    # Direction of change in confidence since the previous computation:
    # "improving" | "declining" | "stable" | "insufficient_data"
    trend_direction: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="insufficient_data",
    )

    # UTC timestamp of the last recalculation.
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
