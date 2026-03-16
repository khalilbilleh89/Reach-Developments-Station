"""
pricing.models

ORM models for pricing data tied to units.

UnitPricingAttributes — attribute-based pricing engine inputs (per-sqm, premiums).
UnitPricing          — formal per-unit pricing record (base_price, adjustment, final_price).
"""

from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


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

    One record per unit — enforced by the unique constraint on unit_id.
    """

    __tablename__ = "unit_pricing"

    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    base_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    manual_adjustment: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
    final_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="AED"
    )
    pricing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
