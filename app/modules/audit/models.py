"""Append-only audit history.

There is no update path and no delete path, in the API or in the service layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: Where the event came from. ``bootstrap`` is the one-off CLI that creates the
#: first administrator, which has no authenticated actor.
AUDIT_SOURCE_API = "api"
AUDIT_SOURCE_BOOTSTRAP = "bootstrap"


class AuditEvent(Base):
    """One recorded governance change.

    Written in the same transaction as the change it describes: if the change
    rolls back, so does its audit row, and neither can exist without the other.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    #: Null for bootstrap and other system-originated events. RESTRICT because
    #: an audit trail that loses its actor is not an audit trail.
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Deliberately not a foreign key: audit outlives and spans every domain.
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=AUDIT_SOURCE_API)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_action", "action"),
    )
