"""
floors.models

ORM model for the Floor entity.
Floor is a child of Building in the development hierarchy:
Project → Phase → Building → Floor → Unit
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.project import FloorStatus

if TYPE_CHECKING:
    from app.modules.buildings.models import Building
    from app.modules.units.models import Unit


class Floor(Base, TimestampMixin):
    """Floor belonging to a building."""

    __tablename__ = "floors"
    __table_args__ = (
        UniqueConstraint("building_id", "code", name="uq_floor_building_code"),
        UniqueConstraint(
            "building_id", "sequence_number", name="uq_floor_building_sequence"
        ),
    )

    building_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    level_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=FloorStatus.PLANNED.value,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    building: Mapped["Building"] = relationship("Building", back_populates="floors")
    units: Mapped[List["Unit"]] = relationship(
        "Unit", back_populates="floor", cascade="all, delete-orphan"
    )
