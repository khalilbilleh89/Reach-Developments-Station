"""
pricing.models

ORM models for pricing data tied to units.

UnitPricingAttributes — attribute-based pricing engine inputs (per-sqm, premiums).
UnitPricing          — formal per-unit pricing record (base_price, adjustment, final_price).
PricingHistory       — immutable audit log of every state change on a pricing record.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants.currency import DEFAULT_CURRENCY
from app.db.base import Base, TimestampMixin

# ---------------------------------------------------------------------------
# Pricing change type constants
# ---------------------------------------------------------------------------

CHANGE_TYPE_INITIAL = "INITIAL"
CHANGE_TYPE_MANUAL_UPDATE = "MANUAL_UPDATE"
CHANGE_TYPE_PREMIUM_RECALC = "PREMIUM_RECALC"
CHANGE_TYPE_OVERRIDE = "OVERRIDE"
CHANGE_TYPE_APPROVAL = "APPROVAL"
CHANGE_TYPE_ARCHIVE = "ARCHIVE"


class UnitPricingAttributes(Base, TimestampMixin):
    """Pricing attributes for an individual unit.

    Feeds the pricing engine to produce a deterministic final unit price.
    Final price is never stored here — it is always calculated on demand.
    """

    __tablename__ = "unit_pricing_attributes"

    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    base_price_per_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    floor_premium: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    view_premium: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    corner_premium: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    size_adjustment: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    custom_adjustment: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)


class UnitPricing(Base, TimestampMixin):
    """Formal per-unit pricing record.

    Stores a structured commercial price attached to a unit:
      final_price = base_price + manual_adjustment

    final_price is always computed in the service layer, never trusted
    from direct client submission.

    Multiple records per unit are allowed to support pricing history.
    Only one record per unit should have a non-archived status at any time;
    this invariant is enforced by the service layer.
    """

    __tablename__ = "unit_pricing"

    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    manual_adjustment: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
    final_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default=DEFAULT_CURRENCY
    )
    pricing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approval_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    override_requested_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    override_approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class PricingHistory(Base, TimestampMixin):
    """Immutable audit log for pricing record state changes.

    Each row captures a snapshot of the pricing record's state at the moment
    of a specific change event.  Rows are append-only — they are never updated
    or deleted after creation.

    ``change_type`` distinguishes the reason for the snapshot:
      INITIAL       — first pricing record created for a unit.
      MANUAL_UPDATE — structural fields updated (base_price, notes, currency).
      PREMIUM_RECALC — price recalculated from updated engine attributes.
      OVERRIDE      — governed manual_adjustment override applied.
      APPROVAL      — pricing record approved.
      ARCHIVE       — pricing record archived (superseded by a new record).
    """

    __tablename__ = "pricing_history"

    pricing_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("unit_pricing.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    base_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    manual_adjustment: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    final_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    pricing_status: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    override_requested_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    override_approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
