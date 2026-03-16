"""
pricing_attributes.models

ORM model for qualitative unit pricing attributes.

UnitQualitativeAttributes captures qualitative and commercial characteristics
that influence unit pricing decisions:
  - view_type: city, sea, park, interior
  - corner_unit: whether the unit is on a building corner
  - floor_premium_category: standard, premium, penthouse
  - orientation: cardinal direction (N, S, E, W)
  - outdoor_area_premium: terrace/balcony premium treatment
  - upgrade_flag: finish upgrades or premium interior
  - notes: optional analyst commentary

These attributes do not drive automatic pricing calculations — they provide
structured qualitative context for pricing decisions and future automation.
"""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UnitQualitativeAttributes(Base, TimestampMixin):
    """Qualitative pricing attributes for an individual unit.

    Provides structured context for pricing decisions beyond numerical premiums.
    One record per unit — enforced by the unique constraint on unit_id.
    """

    __tablename__ = "unit_qualitative_attributes"

    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    view_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    corner_unit: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    floor_premium_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    orientation: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    outdoor_area_premium: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    upgrade_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
