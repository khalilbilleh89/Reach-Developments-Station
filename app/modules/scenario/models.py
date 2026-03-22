"""
scenario.models

ORM models for the Scenario Engine domain.
Entities: Scenario → ScenarioVersion

A Scenario is a pre-project or pre-decision development option that can be
created against land, feasibility, or concept planning contexts.  Scenarios
are versioned so that every change is auditable.  Only one version per
scenario can hold approved status at any given time.

Architecture rule: all scenario state must be managed centrally here.
Module-specific code must never create private scenario records.
"""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants.scenario import DEFAULT_SCENARIO_SOURCE_TYPE, DEFAULT_SCENARIO_STATUS
from app.db.base import Base, TimestampMixin


class Scenario(Base, TimestampMixin):
    """A named development option that can be evaluated, duplicated, and approved.

    source_type identifies which planning layer owns this option (land,
    feasibility, concept, etc.).  project_id and land_id are optional
    foreign-key-style references; they are stored as plain strings to avoid
    cross-module ORM coupling.

    base_scenario_id records the lineage when a scenario is duplicated.
    """

    __tablename__ = "scenarios"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=DEFAULT_SCENARIO_STATUS)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default=DEFAULT_SCENARIO_SOURCE_TYPE)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    land_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    base_scenario_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Self-referential relationship for duplication lineage
    base_scenario: Mapped[Optional["Scenario"]] = relationship(
        "Scenario",
        foreign_keys=[base_scenario_id],
        remote_side="Scenario.id",
        back_populates="derived_scenarios",
    )
    derived_scenarios: Mapped[list["Scenario"]] = relationship(
        "Scenario",
        foreign_keys=[base_scenario_id],
        back_populates="base_scenario",
    )
    versions: Mapped[list["ScenarioVersion"]] = relationship(
        "ScenarioVersion",
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioVersion.version_number",
    )


class ScenarioVersion(Base, TimestampMixin):
    """An immutable snapshot of assumptions and comparison metrics for a scenario.

    version_number starts at 1 and increments on every new version.
    assumptions_json holds the full set of planning assumptions captured at
    the time of versioning.  comparison_metrics_json holds KPI outputs (e.g.
    from the Calculation Engine) for side-by-side scenario comparison.
    is_approved is True for the single version that has been formally approved.
    """

    __tablename__ = "scenario_versions"
    __table_args__ = (
        # Guarantee unique version numbers per scenario regardless of concurrency.
        UniqueConstraint("scenario_id", "version_number", name="uq_scenario_versions_scenario_id_version_number"),
    )

    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assumptions_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    comparison_metrics_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="versions")
