"""
reservations.models

ORM model for direct unit reservations.

UnitReservation captures a provisional hold placed on a unit by a sales agent
on behalf of a prospective buyer. Unlike the sales-module Reservation (which
requires a pre-registered Buyer entity), UnitReservation embeds customer contact
information directly, enabling fast, lightweight holds without a full buyer
registration workflow.

One ACTIVE reservation per unit is enforced at the service layer (and, on
PostgreSQL, at the database layer via a partial unique index).

Reservation lifecycle:
  active    → hold is in place; unit is not available to other buyers
  expired   → expiry timestamp has passed; hold has lapsed
  cancelled → hold was explicitly cancelled by the sales team
  converted → hold was converted into a formal sales contract
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants.currency import DEFAULT_CURRENCY
from app.db.base import Base, TimestampMixin


class UnitReservation(Base, TimestampMixin):
    """Direct reservation placed on a unit for a prospective buyer.

    Stores customer contact information inline rather than referencing a
    separate Buyer record, allowing reservations to be created without a full
    buyer-registration step.
    """

    __tablename__ = "unit_reservations"

    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Customer information stored inline (no Buyer FK required)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)

    # Pricing at the time of reservation
    reservation_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    reservation_fee: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
