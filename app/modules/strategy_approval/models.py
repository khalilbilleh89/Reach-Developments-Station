"""
strategy_approval.models

ORM model for the StrategyApproval entity (PR-V7-08).

Persists the approval state for a project strategy recommendation.  A snapshot
of the strategy and execution package is captured at the time the approval
request is created so that the decision record is self-contained even when the
underlying recommendation changes later.

State machine
-------------
  pending → approved  (via approve endpoint)
  pending → rejected  (via reject endpoint)

Reverse transitions are forbidden and enforced in the service layer.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class StrategyApproval(Base, TimestampMixin):
    """Approval record for a project strategy recommendation.

    One record is created per approval request.  The status field tracks
    the current state (pending | approved | rejected).  Snapshots of the
    strategy and execution package are stored verbatim so that the decision
    audit trail is self-contained and immutable.
    """

    __tablename__ = "strategy_approvals"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # JSON snapshots of the recommendation at the time the request was created.
    # Stored verbatim — never recomputed or mutated after creation.
    strategy_snapshot: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
    )
    execution_package_snapshot: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Approval state: pending | approved | rejected
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )

    # Populated on approval only.
    approved_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Populated on rejection only.
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
