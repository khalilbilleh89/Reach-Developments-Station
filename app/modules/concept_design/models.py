"""
concept_design.models

ORM models for the Concept Design module.

Entities:
  ConceptOption      — one concept design option (physical program) linked to
                       a project and/or scenario context.
  ConceptUnitMixLine — a normalised unit-type row inside a concept option,
                       representing one band of the residential/commercial mix.

PR-CONCEPT-052, PR-CONCEPT-054
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass  # future cross-module type hints go here


class ConceptOption(Base, TimestampMixin):
    """One concept design option (scheme) for a development.

    project_id and scenario_id are both optional so that a concept option
    can be created before a formal project record exists, mirroring the
    pattern established by FeasibilityRun.
    """

    __tablename__ = "concept_options"

    project_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    scenario_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("scenarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Physical program inputs (manually supplied or estimated at concept stage)
    site_area: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    gross_floor_area: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    building_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floor_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Promotion metadata — PR-CONCEPT-054
    is_promoted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    promoted_project_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )
    promotion_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    mix_lines: Mapped[List["ConceptUnitMixLine"]] = relationship(
        "ConceptUnitMixLine",
        back_populates="concept_option",
        cascade="all, delete-orphan",
        order_by="ConceptUnitMixLine.unit_type",
    )


class ConceptUnitMixLine(Base, TimestampMixin):
    """A single unit-type row inside a concept option's residential/commercial mix.

    All aggregate area and count metrics for the parent ConceptOption are
    derived from these lines by the concept engine — they are never stored
    directly on ConceptOption to keep the data normalised and auditable.
    """

    __tablename__ = "concept_unit_mix_lines"

    concept_option_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("concept_options.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_type: Mapped[str] = mapped_column(String(100), nullable=False)
    units_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_internal_area: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    avg_sellable_area: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    mix_percentage: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)

    concept_option: Mapped["ConceptOption"] = relationship(
        "ConceptOption", back_populates="mix_lines"
    )
