"""
feasibility.models

ORM models for the Feasibility Engine domain.
Entities: FeasibilityRun → FeasibilityAssumptions + FeasibilityResult
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.finance import FeasibilityScenarioType

if TYPE_CHECKING:
    from app.modules.projects.models import Project


class FeasibilityRun(Base, TimestampMixin):
    """One feasibility scenario linked to a development project."""

    __tablename__ = "feasibility_runs"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=FeasibilityScenarioType.BASE.value
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="feasibility_runs")
    assumptions: Mapped[Optional["FeasibilityAssumptions"]] = relationship(
        "FeasibilityAssumptions",
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )
    result: Mapped[Optional["FeasibilityResult"]] = relationship(
        "FeasibilityResult",
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )


class FeasibilityAssumptions(Base, TimestampMixin):
    """Structured input assumptions for a feasibility run."""

    __tablename__ = "feasibility_assumptions"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("feasibility_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    sellable_area_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    avg_sale_price_per_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    construction_cost_per_sqm: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    soft_cost_ratio: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    finance_cost_ratio: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    sales_cost_ratio: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    development_period_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run: Mapped["FeasibilityRun"] = relationship("FeasibilityRun", back_populates="assumptions")


class FeasibilityResult(Base, TimestampMixin):
    """Deterministic calculated outputs for a feasibility run."""

    __tablename__ = "feasibility_results"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("feasibility_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    gdv: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    construction_cost: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    soft_cost: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    finance_cost: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    sales_cost: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    total_cost: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    developer_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    profit_margin: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    irr_estimate: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)

    run: Mapped["FeasibilityRun"] = relationship("FeasibilityRun", back_populates="result")

