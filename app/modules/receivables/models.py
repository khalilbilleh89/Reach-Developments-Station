"""
receivables.models

ORM model for Receivable — one record per payment installment line.

A receivable tracks a single collectible financial obligation linked to a
specific installment.  The lifecycle moves from pending → due → overdue →
partially_paid → paid (or cancelled when the contract is cancelled).

Balance consistency rule:
  balance_due = amount_due - amount_paid
  This is maintained by the service layer, not as a DB expression.
"""

from datetime import date
from typing import Any, Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants.currency import DEFAULT_CURRENCY
from app.db.base import Base, TimestampMixin


class Receivable(Base, TimestampMixin):
    """Single collectible financial obligation linked to a payment installment."""

    __tablename__ = "receivables"
    __allow_unmapped__ = True

    contract_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sales_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_plan_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("payment_plan_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    installment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("payment_schedules.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    receivable_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_due: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    amount_paid: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
    balance_due: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default=DEFAULT_CURRENCY
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    contract: Any = relationship(
        "SalesContract",
        foreign_keys=[contract_id],
        lazy="select",
    )
    installment: Any = relationship(
        "PaymentSchedule",
        foreign_keys=[installment_id],
        lazy="select",
    )
