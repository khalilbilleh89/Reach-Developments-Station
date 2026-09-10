"""One historical document and its immutable authorization scope."""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Snapshot(Base):
    __tablename__ = "management_report_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope_type: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    label: Mapped[str | None] = mapped_column(String(200))
    as_of_date: Mapped[date] = mapped_column(Date)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    creator_display_name: Mapped[str] = mapped_column(String(200))
    schema_version: Mapped[int] = mapped_column(Integer)
    project_count: Mapped[int] = mapped_column(Integer)
    incomplete_project_count: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint("scope_type IN ('portfolio', 'project')", name="scope_ok"),
        CheckConstraint(
            "(scope_type = 'project') = (project_id IS NOT NULL)", name="project_scope"
        ),
        CheckConstraint("schema_version > 0", name="schema_positive"),
        CheckConstraint(
            "project_count > 0 AND incomplete_project_count BETWEEN 0 AND project_count",
            name="counts_ok",
        ),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="hash_sha256"),
        CheckConstraint("as_of_date = (captured_at AT TIME ZONE 'UTC')::date", name="capture_date"),
        Index("ix_mrs_scope_captured", "scope_type", "captured_at", "id"),
        Index("ix_mrs_project_captured", "project_id", "captured_at", "id"),
        Index("ix_mrs_captured", "captured_at", "id"),
    )


class SnapshotProject(Base):
    __tablename__ = "management_report_snapshot_projects"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("management_report_snapshots.id", ondelete="RESTRICT"), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), primary_key=True
    )
    __table_args__ = (Index("ix_mrsp_project_snapshot", "project_id", "snapshot_id"),)
