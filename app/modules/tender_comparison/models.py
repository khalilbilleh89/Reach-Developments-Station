"""
tender_comparison.models

ORM models for the Tender Comparison & Cost Variance domain.

ConstructionCostComparisonSet — a project-owned container grouping a set of
baseline-to-comparison cost comparisons at a given stage (e.g.
baseline_vs_tender).

ConstructionCostComparisonLine — a single cost category comparison line within
a set, capturing baseline amount, comparison amount, and pre-computed variance
fields.  Lines are orphan-safe via CASCADE delete on the parent set.

Source construction cost records are NEVER mutated by this domain.

Baseline governance fields (added PR-V6-13):
  is_approved_baseline — True when this set is the official project baseline.
  approved_at          — Timestamp when baseline was last approved (UTC).
  approved_by_user_id  — ID of the user who approved the baseline.
  At most one set per project may have is_approved_baseline = True.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants.currency import DEFAULT_CURRENCY
from app.db.base import Base, TimestampMixin
from app.shared.enums.construction_costs import CostCategory
from app.shared.enums.tender_comparison import ComparisonStage, VarianceReason


class ConstructionCostComparisonSet(Base, TimestampMixin):
    """Project-owned comparison set grouping a baseline-to-comparison review.

    Each set represents one governed comparison event (e.g. baseline vs
    tender result) for a project.  Multiple active sets per project are
    supported to allow tracking multiple comparison points over time.

    Lines are CASCADE-deleted when the set is deleted.

    Baseline governance (PR-V6-13):
      At most one set per project may be the approved baseline at any time.
      Approving a set automatically deactivates the prior baseline for the
      same project.
    """

    __tablename__ = "construction_cost_comparison_sets"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    comparison_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ComparisonStage.BASELINE_VS_TENDER.value,
        index=True,
    )
    baseline_label: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Baseline"
    )
    comparison_label: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Tender"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)

    # ── Baseline governance fields ────────────────────────────────────────────
    is_approved_baseline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )

    lines: Mapped[List["ConstructionCostComparisonLine"]] = relationship(
        "ConstructionCostComparisonLine",
        back_populates="comparison_set",
        cascade="all, delete-orphan",
        order_by="ConstructionCostComparisonLine.created_at",
    )


class ConstructionCostComparisonLine(Base, TimestampMixin):
    """Single cost category comparison line within a comparison set.

    Stores the baseline and comparison amounts for one cost category entry.
    variance_amount and variance_pct are pre-computed on write by the service
    layer for efficient display and querying without repeated arithmetic.

    variance_amount = comparison_amount - baseline_amount
    variance_pct    = (variance_amount / baseline_amount) * 100 when baseline != 0
                      else None
    """

    __tablename__ = "construction_cost_comparison_lines"

    comparison_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("construction_cost_comparison_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cost_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CostCategory.HARD_COST.value,
        index=True,
    )
    baseline_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0.00")
    )
    comparison_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0.00")
    )
    variance_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0.00")
    )
    variance_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    variance_reason: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=VarianceReason.OTHER.value,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    comparison_set: Mapped["ConstructionCostComparisonSet"] = relationship(
        "ConstructionCostComparisonSet",
        back_populates="lines",
    )
