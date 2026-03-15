"""
projects.models

ORM model for the Project entity.
Project is the top-level container in the development hierarchy:
Project → Phase → Building → Floor → Unit
"""

from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.project import ProjectStatus

if TYPE_CHECKING:
    from app.modules.feasibility.models import FeasibilityRun
    from app.modules.land.models import LandParcel
    from app.modules.phases.models import Phase


class Project(Base, TimestampMixin):
    """Top-level real estate development project container."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    developer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    target_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ProjectStatus.PIPELINE.value,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    phases: Mapped[List["Phase"]] = relationship("Phase", back_populates="project", cascade="all, delete-orphan")
    parcels: Mapped[List["LandParcel"]] = relationship("LandParcel", back_populates="project", cascade="all, delete-orphan")
    feasibility_runs: Mapped[List["FeasibilityRun"]] = relationship("FeasibilityRun", back_populates="project", cascade="all, delete-orphan")
