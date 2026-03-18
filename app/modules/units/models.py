"""
units.models

ORM model for the Unit entity.
Unit is the inventory atom of the system — the leaf in the development hierarchy:
Project → Phase → Building → Floor → Unit

Also contains the UnitDynamicAttributeValue model that bridges project-defined
attribute options to individual units (PR-033).
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.project import UnitStatus

if TYPE_CHECKING:
    from app.modules.floors.models import Floor
    from app.modules.projects.models import ProjectAttributeDefinition, ProjectAttributeOption


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
    dynamic_attribute_values: Mapped[List["UnitDynamicAttributeValue"]] = relationship(
        "UnitDynamicAttributeValue",
        back_populates="unit",
        cascade="all, delete-orphan",
    )


class UnitDynamicAttributeValue(Base, TimestampMixin):
    """Stores a unit's selected value for a project-defined attribute definition.

    Bridges the gap between project-level attribute options (PR-032) and
    individual units. One row per unit per attribute definition, enforced via
    a unique constraint on (unit_id, definition_id).

    Initial supported use case: project-defined view_type selection.
    """

    __tablename__ = "unit_dynamic_attribute_values"
    __table_args__ = (
        UniqueConstraint(
            "unit_id", "definition_id", name="uq_udav_unit_definition"
        ),
    )

    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    definition_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project_attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project_attribute_options.id", ondelete="CASCADE"),
        nullable=False,
    )

    unit: Mapped["Unit"] = relationship("Unit", back_populates="dynamic_attribute_values")
    definition: Mapped["ProjectAttributeDefinition"] = relationship(
        "ProjectAttributeDefinition"
    )
    option: Mapped["ProjectAttributeOption"] = relationship("ProjectAttributeOption")
