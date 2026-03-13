"""
land.models

ORM models for the Land Underwriting domain.
Entities: LandParcel → LandAssumptions + LandValuation
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.project import LandParcelStatus, LandScenarioType

if TYPE_CHECKING:
    from app.modules.projects.models import Project


class LandParcel(Base, TimestampMixin):
    """Physical land parcel linked to a development project."""

    __tablename__ = "land_parcels"
    __table_args__ = (
        UniqueConstraint("parcel_code", "project_id", name="uq_land_parcel_code_project"),
    )

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parcel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    parcel_code: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    land_area_sqm: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    frontage_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    depth_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    zoning_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    permitted_far: Mapped[Optional[float]] = mapped_column(Numeric(6, 3), nullable=True)
    max_height_m: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    max_floors: Mapped[Optional[int]] = mapped_column(nullable=True)

    corner_plot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    utilities_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=LandParcelStatus.DRAFT.value
    )

    project: Mapped["Project"] = relationship("Project", back_populates="parcels")
    assumptions: Mapped[List["LandAssumptions"]] = relationship(
        "LandAssumptions", back_populates="parcel", cascade="all, delete-orphan"
    )
    valuations: Mapped[List["LandValuation"]] = relationship(
        "LandValuation", back_populates="parcel", cascade="all, delete-orphan"
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

    valuation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    parcel: Mapped["LandParcel"] = relationship("LandParcel", back_populates="valuations")
