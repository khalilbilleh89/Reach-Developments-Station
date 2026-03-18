"""
construction.models

ORM models for the Construction domain.

ConstructionScope  — tracks the construction scope for a project, phase, or building.
ConstructionMilestone — individual delivery milestones within a scope.

Hierarchy positioning:
  Project (optional) → Phase (optional) → Building (optional)
  At least one of project_id / phase_id / building_id must be set.
"""

from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.construction import ConstructionStatus, MilestoneStatus

if TYPE_CHECKING:
    pass  # future cross-module relationships


class ConstructionScope(Base, TimestampMixin):
    """Construction scope record linked to a project, phase, and/or building.

    Uniqueness per link combination is enforced in PostgreSQL via partial unique
    indexes in migration 0026 (one per NULL-pattern), because a composite
    UNIQUE constraint does not prevent duplicates when any column is NULL.
    """

    __tablename__ = "construction_scopes"

    project_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    phase_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("phases.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    building_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ConstructionStatus.PLANNED.value,
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    target_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    milestones: Mapped[List["ConstructionMilestone"]] = relationship(
        "ConstructionMilestone",
        back_populates="scope",
        cascade="all, delete-orphan",
        order_by="ConstructionMilestone.sequence",
    )


class ConstructionMilestone(Base, TimestampMixin):
    """Delivery milestone within a construction scope."""

    __tablename__ = "construction_milestones"
    __table_args__ = (
        UniqueConstraint("scope_id", "sequence", name="uq_milestone_scope_sequence"),
    )

    scope_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("construction_scopes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MilestoneStatus.PENDING.value,
    )
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    scope: Mapped["ConstructionScope"] = relationship(
        "ConstructionScope", back_populates="milestones"
    )
