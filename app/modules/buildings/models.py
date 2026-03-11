"""
buildings.models

ORM model for the Building entity.
Building is a child of Phase in the development hierarchy:
Project → Phase → Building → Floor → Unit
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.project import BuildingStatus

if TYPE_CHECKING:
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase


class Building(Base, TimestampMixin):
    """Building belonging to a development phase."""

    __tablename__ = "buildings"
    __table_args__ = (
        UniqueConstraint("phase_id", "code", name="uq_building_phase_code"),
    )

    phase_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("phases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    floors_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=BuildingStatus.PLANNED.value,
    )

    phase: Mapped["Phase"] = relationship("Phase", back_populates="buildings")
    floors: Mapped[List["Floor"]] = relationship("Floor", back_populates="building", cascade="all, delete-orphan")
