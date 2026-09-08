"""Commission entitlement and beneficiary distribution records."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, RATE, Base, in_list

COMMISSION_STATUSES = ("draft", "released", "reversed")


class CommissionGrant(Base):
    __tablename__ = "commission_grants"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    sold_price_snapshot: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    commissionable_base_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    granted_rate_fraction: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    commission_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    notes: Mapped[str | None] = mapped_column(String(2000))
    prepared_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["unit_id", "project_id"], ["units.id", "units.project_id"], ondelete="RESTRICT"
        ),
        UniqueConstraint("id", "project_id", name="commission_project"),
        CheckConstraint("sold_price_snapshot > 0", name="sold_price_positive"),
        CheckConstraint(
            "commissionable_base_amount > 0 AND commissionable_base_amount <= sold_price_snapshot",
            name="base_range",
        ),
        CheckConstraint(
            "granted_rate_fraction > 0 AND granted_rate_fraction <= 1", name="rate_range"
        ),
        CheckConstraint("commission_total > 0", name="total_positive"),
        CheckConstraint(in_list("status", COMMISSION_STATUSES), name="status_ok"),
        CheckConstraint(
            "status <> 'released' OR (released_at IS NOT NULL AND released_by_user_id IS NOT NULL)",
            name="released_has_actor",
        ),
        CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL "
            "AND reversed_by_user_id IS NOT NULL AND reversal_reason IS NOT NULL)",
            name="reversed_has_actor",
        ),
        CheckConstraint(
            "released_by_user_id IS NULL OR released_by_user_id <> prepared_by_user_id",
            name="checker_differs",
        ),
        Index(
            "uq_commission_live_sale",
            "sale_contract_id",
            unique=True,
            postgresql_where=text("status IN ('draft', 'released')"),
        ),
    )


class CommissionAllocation(Base):
    __tablename__ = "commission_allocations"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    commission_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    beneficiary_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rate_fraction: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    calculated_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["commission_id", "project_id"],
            ["commission_grants.id", "commission_grants.project_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("commission_id", "sequence", name="uq_commission_allocation_sequence"),
        CheckConstraint("length(trim(beneficiary_name)) > 0", name="beneficiary_present"),
        CheckConstraint("rate_fraction > 0 AND rate_fraction <= 1", name="rate_range"),
        CheckConstraint("calculated_amount > 0", name="amount_positive"),
        CheckConstraint("sequence > 0", name="sequence_positive"),
    )
