"""Per-person register state: saved views and display preferences.

Nothing here is business data. A saved view is the filters and sort a person
wants back on a register; a preference is how they like a register drawn. Both
belong to one user, are read by that user alone, and carry no figure.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, in_list

#: Row densities a register may be drawn at (design system E4).
REGISTER_DENSITIES = ("comfortable", "compact")


class UserSavedView(Base):
    """A named set of filters and a sort on one register, owned by one person."""

    __tablename__ = "user_saved_views"
    __table_args__ = (
        UniqueConstraint("user_id", "screen", "name", name="uq_user_saved_views_user_screen_name"),
        CheckConstraint("length(trim(screen)) > 0", name="ck_user_saved_views_screen_present"),
        CheckConstraint("length(trim(name)) > 0", name="ck_user_saved_views_name_present"),
        Index("ix_user_saved_views_user_id_screen", "user_id", "screen"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    #: Which register the view belongs to: "collections", "inventory_stock".
    screen: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    #: The register's own filter state, as the screen defines it. Opaque here.
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    #: "column" or "-column"; absent means the register's default order.
    sort: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class UserPreference(Base):
    """How one person likes their registers drawn. One row per person."""

    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint(
            in_list("register_density", REGISTER_DENSITIES),
            name="ck_user_preferences_valid_register_density",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    register_density: Mapped[str] = mapped_column(
        String(16), nullable=False, default="comfortable", server_default=text("'comfortable'")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
