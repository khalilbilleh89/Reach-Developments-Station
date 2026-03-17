"""
units.models

ORM model for the Unit entity.
Unit is the inventory atom of the system — the leaf in the development hierarchy:
Project → Phase → Building → Floor → Unit
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.project import UnitStatus

if TYPE_CHECKING:
    from app.modules.floors.models import Floor


class Unit(Base, TimestampMixin):
    """Inventory unit belonging to a floor."""

    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("floor_id", "unit_number", name="uq_unit_floor_number"),
    )

    floor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("floors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_number: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=UnitStatus.AVAILABLE.value,
    )
    internal_area: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    balcony_area: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    terrace_area: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    roof_garden_area: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    front_garden_area: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    gross_area: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Apartment-specific attributes (Layer A — Unit Master Attributes)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floor_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    livable_area: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    has_roof_garden: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    floor: Mapped["Floor"] = relationship("Floor", back_populates="units")
