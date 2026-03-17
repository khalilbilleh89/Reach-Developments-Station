"""
projects.models

ORM model for the Project entity.
Project is the top-level container in the development hierarchy:
Project → Phase → Building → Floor → Unit

Also contains project-level attribute definition models:
  ProjectAttributeDefinition — a named, typed attribute set owned by a project
  ProjectAttributeOption     — an allowed selectable value within a definition
"""

from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
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
    attribute_definitions: Mapped[List["ProjectAttributeDefinition"]] = relationship(
        "ProjectAttributeDefinition", back_populates="project", cascade="all, delete-orphan"
    )


class ProjectAttributeDefinition(Base, TimestampMixin):
    """A named, typed attribute set that belongs to a project.

    Each project can own multiple attribute definitions (e.g. view_type).
    Only one definition per key is allowed per project (regardless of is_active).
    """

    __tablename__ = "project_attribute_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_pad_project_key"),
    )

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    input_type: Mapped[str] = mapped_column(String(50), nullable=False, default="select")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project: Mapped["Project"] = relationship("Project", back_populates="attribute_definitions")
    options: Mapped[List["ProjectAttributeOption"]] = relationship(
        "ProjectAttributeOption", back_populates="definition", cascade="all, delete-orphan"
    )


class ProjectAttributeOption(Base, TimestampMixin):
    """An allowed selectable value within a project attribute definition.

    E.g. for a view_type definition: Sea View, Marina View, Internal View.
    """

    __tablename__ = "project_attribute_options"
    __table_args__ = (
        UniqueConstraint("definition_id", "value", name="uq_pao_definition_value"),
        UniqueConstraint("definition_id", "label", name="uq_pao_definition_label"),
    )

    definition_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project_attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    definition: Mapped["ProjectAttributeDefinition"] = relationship(
        "ProjectAttributeDefinition", back_populates="options"
    )
