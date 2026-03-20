"""
phases.models

ORM model for the Phase entity.
Phase is a child of Project in the development hierarchy:
Project → Phase → Building → Floor → Unit
"""

from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.project import PhaseStatus, PhaseType

if TYPE_CHECKING:
    from app.modules.buildings.models import Building
    from app.modules.projects.models import Project


class Phase(Base, TimestampMixin):
    """Development phase belonging to a project."""

    __tablename__ = "phases"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence", name="uq_phase_project_sequence"),
    )

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_type: Mapped[Optional[PhaseType]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=PhaseStatus.PLANNED.value,
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="phases")
    buildings: Mapped[List["Building"]] = relationship("Building", back_populates="phase", cascade="all, delete-orphan")
