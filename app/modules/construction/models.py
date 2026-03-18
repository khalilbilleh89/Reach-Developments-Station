"""
construction.models

ORM models for the Construction domain.

ConstructionScope          — tracks the construction scope for a project, phase, or building.
ConstructionMilestone      — individual delivery milestones within a scope (Contractor side).
ConstructionEngineeringItem — engineering tasks / deliverables within a scope (Engineering side).
ConstructionProgressUpdate  — periodic progress report entries linked to a milestone.
ConstructionCostItem        — cost line items tracked at the scope level (budget/committed/actual).

Hierarchy positioning:
  Project (optional) → Phase (optional) → Building (optional)
  At least one of project_id / phase_id / building_id must be set.

  ConstructionScope
    ├── ConstructionEngineeringItem  (Engineering workspace)
    ├── ConstructionCostItem         (Cost tracking workspace)
    └── ConstructionMilestone        (Contractor workspace)
         └── ConstructionProgressUpdate  (Progress history)
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.construction import ConstructionStatus, EngineeringStatus, MilestoneStatus

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
    engineering_items: Mapped[List["ConstructionEngineeringItem"]] = relationship(
        "ConstructionEngineeringItem",
        back_populates="scope",
        cascade="all, delete-orphan",
        order_by="ConstructionEngineeringItem.created_at",
    )
    cost_items: Mapped[List["ConstructionCostItem"]] = relationship(
        "ConstructionCostItem",
        back_populates="scope",
        cascade="all, delete-orphan",
        order_by="ConstructionCostItem.created_at",
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
    progress_updates: Mapped[List["ConstructionProgressUpdate"]] = relationship(
        "ConstructionProgressUpdate",
        back_populates="milestone",
        cascade="all, delete-orphan",
        order_by="ConstructionProgressUpdate.reported_at",
    )


class ConstructionProgressUpdate(Base, TimestampMixin):
    """Periodic progress report entry linked to a construction milestone.

    Records the percent complete, a status note, and who reported it.
    Multiple updates per milestone build up a progress history.
    """

    __tablename__ = "construction_progress_updates"

    milestone_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("construction_milestones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    status_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reported_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    milestone: Mapped["ConstructionMilestone"] = relationship(
        "ConstructionMilestone", back_populates="progress_updates"
    )


class ConstructionEngineeringItem(Base, TimestampMixin):
    """Engineering task or deliverable within a construction scope.

    Represents the Engineering workspace: technical coordination, consultant
    deliverables, and consultant cost tracking.
    """

    __tablename__ = "construction_engineering_items"

    scope_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("construction_scopes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=EngineeringStatus.PENDING.value,
    )
    item_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    consultant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    consultant_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    scope: Mapped["ConstructionScope"] = relationship(
        "ConstructionScope", back_populates="engineering_items"
    )


class ConstructionCostItem(Base, TimestampMixin):
    """Cost line item within a construction scope.

    Captures budget, committed, and actual amounts for a cost line,
    allowing scope-level financial execution tracking.
    Variance is derived at the service/response layer, not stored.
    """

    __tablename__ = "construction_cost_items"
    __table_args__ = (
        Index("ix_construction_cost_items_scope_id", "scope_id"),
        Index("ix_construction_cost_items_cost_category", "cost_category"),
        Index(
            "ix_construction_cost_items_scope_cost_date",
            "scope_id",
            "cost_date",
        ),
    )

    scope_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("construction_scopes.id", ondelete="CASCADE"),
        nullable=False,
    )

    cost_category: Mapped[str] = mapped_column(String(50), nullable=False)
    cost_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    vendor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    budget_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    committed_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    actual_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )

    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="AED")
    cost_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    scope: Mapped["ConstructionScope"] = relationship(
        "ConstructionScope", back_populates="cost_items"
    )
