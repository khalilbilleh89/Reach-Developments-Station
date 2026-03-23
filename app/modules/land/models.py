"""
land.models

ORM models for the Land Underwriting domain.
Entities: LandParcel → LandAssumptions + LandValuation
          LandAssembly ←→ LandParcel (via LandAssemblyParcel join table)

Land parcels are independent pre-project entities. project_id is optional:
a parcel can exist before any project is created and can be linked to a
project later in the development lifecycle.

Land assemblies aggregate multiple parcels into a combined development site.
Parcel records remain canonical; assembly stores a recomputable aggregate
snapshot derived from them.
"""

from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.project import LandParcelStatus, LandScenarioType

if TYPE_CHECKING:
    from app.modules.projects.models import Project


class LandParcel(Base, TimestampMixin):
    """Physical land parcel — independent of project hierarchy.

    project_id is optional. A parcel may exist as a standalone pre-project
    record (parcel intake, zoning analysis, valuation) and be linked to a
    project at a later stage in the acquisition lifecycle.
    """

    __tablename__ = "land_parcels"
    __table_args__ = (
        UniqueConstraint("parcel_code", "project_id", name="uq_land_parcel_code_project"),
    )

    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    parcel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    parcel_code: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ---------------------------------------------------------------------------
    # Identity & cadastral reference
    # ---------------------------------------------------------------------------
    plot_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cadastral_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_link: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    municipality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    submarket: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ---------------------------------------------------------------------------
    # Physical / dimensional attributes
    # ---------------------------------------------------------------------------
    land_area_sqm: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    frontage_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    depth_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    buildable_area_sqm: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    sellable_area_sqm: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    coverage_ratio: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    density_ratio: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)

    front_setback_m: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    side_setback_m: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    rear_setback_m: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)

    zoning_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    permitted_far: Mapped[Optional[float]] = mapped_column(Numeric(6, 3), nullable=True)
    max_height_m: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    max_floors: Mapped[Optional[int]] = mapped_column(nullable=True)

    corner_plot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    utilities_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    access_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    utilities_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---------------------------------------------------------------------------
    # Acquisition economics
    # ---------------------------------------------------------------------------
    acquisition_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    transaction_cost: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    asking_price_per_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    supported_price_per_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)

    # ---------------------------------------------------------------------------
    # Governance / provenance
    # ---------------------------------------------------------------------------
    assumption_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=LandParcelStatus.DRAFT.value
    )

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="parcels")
    assumptions: Mapped[List["LandAssumptions"]] = relationship(
        "LandAssumptions", back_populates="parcel", cascade="all, delete-orphan"
    )
    valuations: Mapped[List["LandValuation"]] = relationship(
        "LandValuation", back_populates="parcel", cascade="all, delete-orphan"
    )
    assembly_memberships: Mapped[List["LandAssemblyParcel"]] = relationship(
        "LandAssemblyParcel", back_populates="parcel", cascade="all, delete-orphan"
    )


class LandAssumptions(Base, TimestampMixin):
    """Development planning assumptions for a land parcel."""

    __tablename__ = "land_assumptions"

    parcel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("land_parcels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_use: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expected_sellable_ratio: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)

    expected_buildable_area_sqm: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    expected_sellable_area_sqm: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    parking_ratio: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    service_area_ratio: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    parcel: Mapped["LandParcel"] = relationship("LandParcel", back_populates="assumptions")


class LandValuation(Base, TimestampMixin):
    """Valuation scenario for a land parcel."""

    __tablename__ = "land_valuations"

    parcel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("land_parcels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=LandScenarioType.BASE.value
    )

    assumed_sale_price_per_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    assumed_cost_per_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)

    expected_gdv: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    expected_cost: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)

    residual_land_value: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    land_value_per_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    max_land_bid: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    residual_margin: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    valuation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valuation_inputs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    valuation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    parcel: Mapped["LandParcel"] = relationship("LandParcel", back_populates="valuations")


class LandAssembly(Base, TimestampMixin):
    """A named assembly of multiple land parcels evaluated as a combined development site.

    The assembly stores an aggregate snapshot of parcel metrics.  Snapshot fields
    (total_area_sqm, weighted_permitted_far, etc.) are derived by the
    aggregation engine and persisted for fast retrieval.  They can be recomputed
    at any time from the canonical parcel source records.
    """

    __tablename__ = "land_assemblies"

    assembly_name: Mapped[str] = mapped_column(String(255), nullable=False)
    assembly_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=LandParcelStatus.DRAFT.value
    )

    # ---------------------------------------------------------------------------
    # Aggregated snapshot fields  (computed by aggregation engine, stored here)
    # ---------------------------------------------------------------------------
    parcel_count: Mapped[int] = mapped_column(nullable=False, default=0)
    total_area_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_frontage_m: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    total_acquisition_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    total_transaction_cost: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    effective_land_basis: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    weighted_permitted_far: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    dominant_zoning_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mixed_zoning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_utilities: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_corner_plot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assembly_results_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    assembly_parcels: Mapped[List["LandAssemblyParcel"]] = relationship(
        "LandAssemblyParcel", back_populates="assembly", cascade="all, delete-orphan"
    )


class LandAssemblyParcel(Base, TimestampMixin):
    """Join table recording which parcels belong to which assembly.

    Constraints
    -----------
    - A parcel may appear in at most one assembly at a time
      (unique constraint on parcel_id).
    - The same parcel cannot appear twice in the same assembly
      (unique constraint on assembly_id + parcel_id).
    """

    __tablename__ = "land_assembly_parcels"
    __table_args__ = (
        UniqueConstraint("assembly_id", "parcel_id", name="uq_assembly_parcel"),
        UniqueConstraint("parcel_id", name="uq_parcel_single_assembly"),
    )

    assembly_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("land_assemblies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("land_parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    assembly: Mapped["LandAssembly"] = relationship(
        "LandAssembly", back_populates="assembly_parcels"
    )
    parcel: Mapped["LandParcel"] = relationship(
        "LandParcel", back_populates="assembly_memberships"
    )
