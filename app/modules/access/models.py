"""Identity, role and session tables."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

#: The fixed MVP role catalogue. These are system roles: there is no custom-role
#: builder and no permission table. Authorization is explicit role checks in
#: code until real domain actions exist to authorize.
SYSTEM_ROLES: tuple[tuple[str, str], ...] = (
    ("system_admin", "System Administrator"),
    ("project_manager", "Project Manager"),
    ("design_engineering", "Design / Engineering"),
    ("sales_operations", "Sales Operations"),
    ("sales_advisor", "Sales Advisor"),
    ("legal", "Legal"),
    ("collections", "Collections"),
    ("finance", "Finance"),
    ("approver_cfo", "Approver / CFO"),
    ("executive_viewer", "Executive Viewer"),
    ("auditor", "Auditor"),
)

ROLE_SYSTEM_ADMIN = "system_admin"
ROLE_AUDITOR = "auditor"


class User(Base):
    """An application identity. Not a CRM contact and not a person record."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        # The first administrator is created by nobody, so this is nullable and
        # RESTRICT: a creator is never removed out from under the record.
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    roles: Mapped[list[Role]] = relationship(secondary="user_roles", lazy="selectin")

    __table_args__ = (
        CheckConstraint("length(email) > 0", name="email_not_blank"),
        CheckConstraint("length(display_name) > 0", name="display_name_not_blank"),
    )

    @property
    def role_keys(self) -> frozenset[str]:
        """The role keys held by this user."""
        return frozenset(role.key for role in self.roles)


class Role(Base):
    """One of the fixed system roles. Seeded by migration; never created via API."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserRole(Base):
    """Association between a user and a fixed role."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # No UniqueConstraint here. The composite primary key above already
    # enforces one row per (user, role); declaring it twice made PostgreSQL keep
    # only the primary key and left `alembic check` reporting drift for ever.


class UserSession(Base):
    """A server-side opaque session.

    The raw token exists only in the browser cookie. This table stores its
    SHA-256 digest, so a database dump yields no usable session.
    """

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (CheckConstraint("expires_at > created_at", name="expires_after_created"),)
