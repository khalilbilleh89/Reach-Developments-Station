"""Project-owned training metadata and retained material bytes."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectTraining(Base):
    __tablename__ = "project_training"
    __table_args__ = (
        CheckConstraint("kind IN ('video', 'document')", name="asset_kind"),
        CheckConstraint(
            "(external_url IS NOT NULL AND data IS NULL AND filename IS NULL "
            "AND media_type IS NULL AND sha256 IS NULL AND byte_count = 0) OR "
            "(external_url IS NULL AND data IS NOT NULL AND filename IS NOT NULL "
            "AND media_type IS NOT NULL AND sha256 IS NOT NULL "
            "AND byte_count > 0 AND byte_count <= 52428800)",
            name="asset_payload",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    execution_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(
        String(4000), nullable=False, default="", server_default=""
    )
    external_url: Mapped[str | None] = mapped_column(String(2000))
    filename: Mapped[str | None] = mapped_column(String(200))
    media_type: Mapped[str | None] = mapped_column(String(80))
    byte_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sha256: Mapped[str | None] = mapped_column(String(64))
    data: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
