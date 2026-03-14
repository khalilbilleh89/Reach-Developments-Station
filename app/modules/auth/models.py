"""
auth.models

ORM models for authentication: User, Role, UserRole.
"""

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Role(Base, TimestampMixin):
    """Application role (e.g. admin, sales_agent, finance_user)."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role")


class User(Base, TimestampMixin):
    """Platform user account."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user")


class UserRole(Base, TimestampMixin):
    """Many-to-many join between User and Role."""

    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="user_roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")
