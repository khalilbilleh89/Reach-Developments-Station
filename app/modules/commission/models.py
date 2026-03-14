"""
commission.models

ORM models for the Commission domain.

Entities
--------
CommissionPlan      — Reusable commission configuration for a project/channel.
CommissionSlab      — Tier rules: value ranges and per-party allocation pcts.
CommissionPayout    — Payout calculation event for a single sale contract.
CommissionPayoutLine — Per-party allocation record within a payout.

Design contract
---------------
This module reads commercial truth (SalesContract.contract_price) and records
payout results.  It does NOT modify sales contracts, pricing, collections, or
finance summary records.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.shared.enums.commission import (
    CalculationMode,
    CommissionPartyType,
    CommissionPayoutStatus,
)


class CommissionPlan(Base, TimestampMixin):
    """Reusable commission configuration attached to a project."""

    __tablename__ = "commission_plans"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    pool_percentage: Mapped[float] = mapped_column(
        Numeric(8, 4), nullable=False
    )
    calculation_mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CalculationMode.MARGINAL.value,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    effective_from: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CommissionSlab(Base, TimestampMixin):
    """Tier rule for a commission plan.

    Each slab covers [range_from, range_to) of the contract value.
    range_to=None means the slab is open-ended (no upper limit).
    The sum of all party percentages per slab must equal 100.
    """

    __tablename__ = "commission_slabs"

    commission_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("commission_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    range_from: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    range_to: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    sales_rep_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    team_lead_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    manager_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    broker_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    platform_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "commission_plan_id", "sequence", name="uq_commission_slabs_plan_sequence"
        ),
    )


class CommissionPayout(Base, TimestampMixin):
    """Payout calculation event for a single sale contract.

    Once approved, this record becomes immutable.
    """

    __tablename__ = "commission_payouts"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sale_contract_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sales_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commission_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("commission_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    gross_sale_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    commission_pool_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    calculation_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CommissionPayoutStatus.DRAFT.value,
    )
    calculated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)


class CommissionPayoutLine(Base, TimestampMixin):
    """Per-party allocation record within a commission payout."""

    __tablename__ = "commission_payout_lines"

    commission_payout_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("commission_payouts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    party_type: Mapped[str] = mapped_column(String(50), nullable=False)
    party_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    slab_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("commission_slabs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    percentage: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    units_covered: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
