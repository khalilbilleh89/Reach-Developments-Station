"""
feasibility.models

ORM models for the Feasibility Engine domain.
Entities: FeasibilityRun → FeasibilityAssumptions + FeasibilityResult

FeasibilityRun is a pre-project entity. project_id is optional: a run can
represent a standalone pre-project scenario and be linked to a project later
in the development lifecycle.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.finance import FeasibilityDecision, FeasibilityRiskLevel, FeasibilityScenarioType, FeasibilityViabilityStatus

if TYPE_CHECKING:
    from app.modules.projects.models import Project


class FeasibilityRun(Base, TimestampMixin):
    """One feasibility scenario — independent of project hierarchy.

    project_id is optional. A run may exist as a standalone pre-project
    scenario and be linked to a project after the acquisition decision is made.
    """

    __tablename__ = "feasibility_runs"

    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scenario_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=FeasibilityScenarioType.BASE.value
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="feasibility_runs")
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
    irr: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    equity_multiple: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    break_even_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    break_even_units: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    scenario_outputs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    viability_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payback_period: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)

    run: Mapped["FeasibilityRun"] = relationship("FeasibilityRun", back_populates="result")

