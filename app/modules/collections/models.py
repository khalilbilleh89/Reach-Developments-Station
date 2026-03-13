"""
collections.models

ORM model for PaymentReceipt.

PaymentReceipt — records an actual cash/bank receipt applied against a specific
  payment schedule line belonging to a sales contract.

One contract can have many receipts.
One payment schedule line can have many receipts when partial payments are allowed.
"""

from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.shared.enums.finance import ReceiptStatus


class PaymentReceipt(Base, TimestampMixin):
    """Actual payment received against a scheduled installment."""

    __tablename__ = "payment_receipts"

    contract_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sales_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_schedule_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("payment_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_received: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default=None,
    )
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ReceiptStatus.RECORDED.value,
        index=True,
    )
