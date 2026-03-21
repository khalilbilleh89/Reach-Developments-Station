"""
collections.models

ORM models for collections:

PaymentReceipt — records an actual cash/bank receipt applied against a specific
  payment schedule line belonging to a sales contract.

CollectionsAlert — an alert generated when an installment becomes significantly
  overdue.  Alerts are resolved when the obligation is settled.

One contract can have many receipts.
One payment schedule line can have many receipts when partial payments are allowed.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.shared.enums.finance import AlertSeverity, AlertType, ReceiptStatus


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


class CollectionsAlert(Base, TimestampMixin):
    """Alert generated when an installment becomes significantly overdue.

    Alerts are deduplication-safe: the combination of (contract_id,
    installment_id, alert_type) should be unique for active (unresolved)
    alerts.  The application layer enforces this to avoid duplicate alerts
    for the same overdue event.
    """

    __tablename__ = "collections_alerts"

    contract_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sales_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("contract_payment_schedule.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AlertType.OVERDUE_7_DAYS.value,
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AlertSeverity.WARNING.value,
        index=True,
    )
    days_overdue: Mapped[int] = mapped_column(nullable=False, default=0)
    outstanding_balance: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
