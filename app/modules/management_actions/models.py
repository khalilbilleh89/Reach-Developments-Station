"""The action register and its append-only attributed change history."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, in_list

STATUSES = ("open", "in_progress", "completed", "cancelled")
SOURCES = ("manual", "portfolio_risk", "portfolio_outlook")


class ManagementAction(Base):
    __tablename__ = "management_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="open")
    source_type: Mapped[str] = mapped_column(String(24), default="manual")
    source_code: Mapped[str | None] = mapped_column(String(80))
    source_key: Mapped[str | None] = mapped_column(String(300))
    source_observation_date: Mapped[date | None] = mapped_column(Date)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="title_present"),
        CheckConstraint(in_list("status", STATUSES), name="status_ok"),
        CheckConstraint(in_list("source_type", SOURCES), name="source_ok"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(source_type = 'manual' AND source_code IS NULL AND source_key IS NULL "
            "AND source_observation_date IS NULL) OR (source_type <> 'manual' "
            "AND source_code IS NOT NULL AND source_key IS NOT NULL AND "
            "source_observation_date IS NOT NULL)",
            name="source_provenance",
        ),
        CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)", name="completion_state"
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancellation_state"
        ),
        Index("ix_ma_project_status_due", "project_id", "status", "due_date"),
        Index("ix_ma_owner_status_due", "owner_user_id", "status", "due_date"),
        Index("ix_ma_project_source", "project_id", "source_type", "source_key"),
    )


class ManagementActionHistory(Base):
    __tablename__ = "management_action_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("management_actions.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    event_type: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str | None] = mapped_column(String(2000))
    changes: Mapped[dict] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint("action_id", "version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            in_list("event_type", ("created", "updated", "status_changed", "reopened")),
            name="event_ok",
        ),
    )
