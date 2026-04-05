"""
strategy_execution_outcome.models

ORM model for the StrategyExecutionOutcome entity (PR-V7-10).

Persists the realized execution outcome for a triggered strategy.
Outcome records are immutable snapshots — once written they are never
updated in place; re-recording supersedes the prior record and creates a
new authoritative row.

Outcome result classification
------------------------------
  matched_strategy    — execution matched the approved strategy
  partially_matched   — some but not all strategy actions were executed
  diverged            — execution materially diverged from the strategy
  cancelled_execution — execution was cancelled before completion
  insufficient_data   — outcome cannot be classified (no comparable strategy data)

Status lifecycle
----------------
  recorded    → superseded  (when a newer outcome is recorded for the same trigger)

The 'recorded' status is the only authoritative state.  Prior outcomes for
the same trigger are marked 'superseded' when a new outcome is recorded.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class StrategyExecutionOutcome(Base, TimestampMixin):
    """Realized execution outcome record for a strategy trigger.

    One record is created per outcome recording action.  If a new outcome is
    recorded for the same trigger, all prior 'recorded' rows for that trigger
    are marked 'superseded' and a new 'recorded' record is inserted.
    The latest 'recorded' row per trigger is the authoritative outcome.
    """

    __tablename__ = "strategy_execution_outcomes"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reference to the execution trigger whose outcome is being recorded.
    # SET NULL on delete so the outcome record survives if the trigger is removed.
    execution_trigger_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("strategy_execution_triggers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Reference to the approval that authorised the trigger.
    # SET NULL on delete so the outcome record survives approval removal.
    approval_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("strategy_approvals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Outcome record status: recorded | superseded
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="recorded",
    )

    # Actual execution values (what really happened).
    # These fields are optional — not all outcomes have comparable numeric data.
    actual_price_adjustment_pct: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    actual_phase_delay_months: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    actual_release_strategy: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Human-authored outcome summary and result classification.
    execution_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    outcome_result: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    outcome_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Audit: who recorded this outcome and when.
    recorded_by_user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
