"""
strategy_execution_trigger.models

ORM model for the StrategyExecutionTrigger entity (PR-V7-09).

Persists the formal execution handoff record for an approved project strategy.
A snapshot of the approved strategy and execution package is captured at the
time the trigger is created so that the handoff record is self-contained even
when the underlying approval or strategy changes later.

State machine
-------------
  triggered   → in_progress  (via start action)
  triggered   → cancelled    (via cancel action)
  in_progress → completed    (via complete action)
  in_progress → cancelled    (via cancel action)

Reverse transitions and transitions from terminal states are forbidden and
enforced in the service layer.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class StrategyExecutionTrigger(Base, TimestampMixin):
    """Execution handoff record for an approved project strategy.

    One record is created per formal trigger action.  The status field tracks
    the current execution lifecycle state.  Snapshots of the strategy and
    execution package are stored verbatim from the approval record so that
    the handoff audit trail is self-contained and immutable.
    """

    __tablename__ = "strategy_execution_triggers"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reference to the approval record that authorised this trigger.
    # SET NULL on delete so the trigger audit record survives if the
    # underlying approval is ever removed.
    approval_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("strategy_approvals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # JSON snapshots copied from the approval at trigger creation time.
    # Never recomputed or mutated after creation.
    strategy_snapshot: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
    )
    execution_package_snapshot: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Execution lifecycle state: triggered | in_progress | completed | cancelled
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="triggered",
    )

    # Populated at trigger creation time.
    triggered_by_user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Populated on completion only.
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Populated on cancellation only.
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
