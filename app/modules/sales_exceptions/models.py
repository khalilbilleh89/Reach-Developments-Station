"""
sales_exceptions.models

ORM model for the SalesException entity.

Records pricing exceptions such as discounts, price overrides, incentive
packages, payment concessions, and marketing promotions.  The model is
read-only with respect to the pricing engine — it observes and logs, never
mutates contract financials.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.shared.enums.sales_exceptions import ApprovalStatus, ExceptionType


class SalesException(Base, TimestampMixin):
    """A single pricing exception request for a unit.

    Captures the discount or incentive negotiated outside the base pricing
    engine so that finance can measure margin impact at project level.
    """

    __tablename__ = "sales_exceptions"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sale_contract_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("sales_contracts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    exception_type: Mapped[str] = mapped_column(String(50), nullable=False)

    base_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    requested_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    discount_percentage: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    incentive_value: Mapped[Optional[float]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    incentive_description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    approval_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ApprovalStatus.PENDING.value,
    )
    requested_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
