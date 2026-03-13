"""
projects.models

ORM model for the Project entity.
Project is the top-level container in the development hierarchy:
Project → Phase → Building → Floor → Unit
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.project import ProjectStatus

if TYPE_CHECKING:
    from app.modules.land.models import LandParcel
    from app.modules.phases.models import Phase


class Project(Base, TimestampMixin):
    """Top-level real estate development project container."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ProjectStatus.PIPELINE.value,
    )

    phases: Mapped[List["Phase"]] = relationship("Phase", back_populates="project", cascade="all, delete-orphan")
    parcels: Mapped[List["LandParcel"]] = relationship("LandParcel", back_populates="project", cascade="all, delete-orphan")
