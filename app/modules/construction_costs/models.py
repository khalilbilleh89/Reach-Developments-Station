"""
construction_costs.models

ORM model for Construction Cost Records.

ConstructionCostRecord — a first-class, project-owned operational record
capturing a single cost line item (by category, source, and stage) against
a project.  Records are the canonical source-of-truth for actual construction
cost data; they do NOT embed formula results or aggregated financial outputs.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.shared.enums.construction_costs import CostCategory, CostSource, CostStage


class ConstructionCostRecord(Base, TimestampMixin):
    """Project-owned construction cost line item record.

    Each record captures a single cost entry for a project, classified by
    category (e.g. hard_cost, soft_cost), source (e.g. estimate, contract),
    and stage (e.g. tender, construction).

    Records are never orphaned — they are CASCADE-deleted when the parent
    project is removed.  Soft-deletion is supported via ``is_active`` so that
    records can be archived without permanent data loss.
    """

    __tablename__ = "construction_cost_records"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    cost_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CostCategory.HARD_COST.value,
        index=True,
    )
    cost_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CostSource.ESTIMATE.value,
    )
    cost_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CostStage.CONSTRUCTION.value,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="AED")
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
