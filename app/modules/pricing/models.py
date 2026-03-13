"""
pricing.models

ORM model for pricing attributes tied to units.
"""

from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String
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
