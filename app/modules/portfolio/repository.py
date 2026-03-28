"""
portfolio.repository

Read-only data access for portfolio-level aggregation.

All methods query existing source-of-truth tables using the SQLAlchemy ORM.
No write operations are permitted in this module.

Cross-module joins are performed inline here because the portfolio layer is
an aggregation-only consumer and does not own any domain records.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.feasibility.models import FeasibilityRun
from app.modules.phases.models import Phase
from app.modules.projects.models import Project
from app.modules.receivables.models import Receivable
from app.modules.sales.models import SalesContract
from app.modules.scenario.models import Scenario
from app.modules.units.models import Unit
from app.modules.buildings.models import Building
from app.modules.floors.models import Floor
from app.modules.tender_comparison.models import (
    ConstructionCostComparisonLine,
    ConstructionCostComparisonSet,
)


class PortfolioRepository:
    """Read-only repository for portfolio aggregation queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Project-level helpers
    # ------------------------------------------------------------------

    def count_projects(self) -> int:
        """Return total number of projects."""
        return self.db.query(func.count(Project.id)).scalar() or 0

    def count_active_projects(self) -> int:
        """Return number of projects with status 'active'."""
        return (
            self.db.query(func.count(Project.id))
            .filter(Project.status == "active")
            .scalar()
            or 0
        )

    def list_projects(self) -> List[Project]:
        """Return all projects ordered by name."""
        return self.db.query(Project).order_by(Project.name).all()

    # ------------------------------------------------------------------
    # Unit-level helpers
    # ------------------------------------------------------------------

    def count_units_by_status(self) -> Dict[str, int]:
        """Return a mapping of unit_status → count across the whole portfolio."""
        rows = (
            self.db.query(Unit.status, func.count(Unit.id))
            .group_by(Unit.status)
            .all()
        )
        return {status: count for status, count in rows}

    def count_units_by_status_for_project(self, project_id: str) -> Dict[str, int]:
        """Return unit status counts scoped to a single project."""
        rows = (
            self.db.query(Unit.status, func.count(Unit.id))
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .group_by(Unit.status)
            .all()
        )
        return {status: count for status, count in rows}

    # ------------------------------------------------------------------
    # Sales / revenue helpers
    # ------------------------------------------------------------------

    def sum_contracted_revenue(self) -> float:
        """Sum of contract_price for all non-cancelled sales contracts."""
        result = (
            self.db.query(func.sum(SalesContract.contract_price))
            .filter(SalesContract.status.notin_(["cancelled"]))
            .scalar()
        )
        return float(result) if result is not None else 0.0

    def sum_contracted_revenue_for_project(self, project_id: str) -> float:
        """Contracted revenue for a single project."""
        result = (
            self.db.query(func.sum(SalesContract.contract_price))
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .filter(SalesContract.status.notin_(["cancelled"]))
            .scalar()
        )
        return float(result) if result is not None else 0.0

    # ------------------------------------------------------------------
    # Collections / receivables helpers
    # ------------------------------------------------------------------

    def sum_collected_cash(self) -> float:
        """Sum of amount_paid across all receivables (portfolio-wide)."""
        result = self.db.query(func.sum(Receivable.amount_paid)).scalar()
        return float(result) if result is not None else 0.0

    def sum_outstanding_balance(self) -> float:
        """Sum of balance_due across all non-paid receivables (portfolio-wide)."""
        result = (
            self.db.query(func.sum(Receivable.balance_due))
            .filter(Receivable.status.notin_(["paid", "cancelled"]))
            .scalar()
        )
        return float(result) if result is not None else 0.0

    def sum_collected_cash_for_project(self, project_id: str) -> float:
        """Cash collected for a single project."""
        result = (
            self.db.query(func.sum(Receivable.amount_paid))
            .join(SalesContract, Receivable.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .scalar()
        )
        return float(result) if result is not None else 0.0

    def sum_outstanding_balance_for_project(self, project_id: str) -> float:
        """Outstanding balance for a single project."""
        result = (
            self.db.query(func.sum(Receivable.balance_due))
            .join(SalesContract, Receivable.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .filter(Receivable.status.notin_(["paid", "cancelled"]))
            .scalar()
        )
        return float(result) if result is not None else 0.0

    def count_receivables(self) -> int:
        """Total receivable records."""
        return self.db.query(func.count(Receivable.id)).scalar() or 0

    def count_overdue_receivables(self) -> int:
        """Receivables with status 'overdue'."""
        return (
            self.db.query(func.count(Receivable.id))
            .filter(Receivable.status == "overdue")
            .scalar()
            or 0
        )

    def sum_overdue_balance(self) -> float:
        """Sum of balance_due for overdue receivables."""
        result = (
            self.db.query(func.sum(Receivable.balance_due))
            .filter(Receivable.status == "overdue")
            .scalar()
        )
        return float(result) if result is not None else 0.0

    def count_overdue_receivables_for_project(self, project_id: str) -> int:
        """Count of overdue receivables for a single project."""
        return (
            self.db.query(func.count(Receivable.id))
            .join(SalesContract, Receivable.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .filter(Receivable.status == "overdue")
            .scalar()
            or 0
        )

    # ------------------------------------------------------------------
    # Pipeline helpers
    # ------------------------------------------------------------------

    def count_scenarios(self) -> int:
        """Total scenario records."""
        return self.db.query(func.count(Scenario.id)).scalar() or 0

    def count_active_scenarios(self) -> int:
        """Scenarios with status 'approved'."""
        return (
            self.db.query(func.count(Scenario.id))
            .filter(Scenario.status == "approved")
            .scalar()
            or 0
        )

    def count_feasibility_runs(self) -> int:
        """Total feasibility run records."""
        return self.db.query(func.count(FeasibilityRun.id)).scalar() or 0

    def count_calculated_feasibility_runs(self) -> int:
        """Feasibility runs with status 'calculated'."""
        return (
            self.db.query(func.count(FeasibilityRun.id))
            .filter(FeasibilityRun.status == "calculated")
            .scalar()
            or 0
        )

    def count_feasibility_runs_for_project(self, project_id: str) -> int:
        """Number of feasibility runs for a given project."""
        return (
            self.db.query(func.count(FeasibilityRun.id))
            .filter(FeasibilityRun.project_id == project_id)
            .scalar()
            or 0
        )

    def get_all_project_feasibility_run_counts(self) -> Dict[str, int]:
        """Return mapping of project_id → feasibility run count."""
        rows = (
            self.db.query(FeasibilityRun.project_id, func.count(FeasibilityRun.id))
            .filter(FeasibilityRun.project_id.isnot(None))
            .group_by(FeasibilityRun.project_id)
            .all()
        )
        return {project_id: count for project_id, count in rows}

    # ------------------------------------------------------------------
    # Bulk grouped per-project aggregations (avoids N+1 in _build_project_cards)
    # ------------------------------------------------------------------

    def get_unit_status_counts_by_project(self) -> Dict[str, Dict[str, int]]:
        """Return project_id → {status → unit_count} for all projects in one query."""
        rows = (
            self.db.query(Phase.project_id, Unit.status, func.count(Unit.id))
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .group_by(Phase.project_id, Unit.status)
            .all()
        )
        result: Dict[str, Dict[str, int]] = {}
        for project_id, status, count in rows:
            result.setdefault(project_id, {})[status] = count
        return result

    def get_contracted_revenue_by_project(self) -> Dict[str, float]:
        """Return project_id → contracted revenue for all projects in one query."""
        rows = (
            self.db.query(Phase.project_id, func.sum(SalesContract.contract_price))
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(SalesContract.status.notin_(["cancelled"]))
            .group_by(Phase.project_id)
            .all()
        )
        return {pid: float(total) for pid, total in rows if total is not None}

    def get_collected_cash_by_project(self) -> Dict[str, float]:
        """Return project_id → amount_paid sum for all projects in one query."""
        rows = (
            self.db.query(Phase.project_id, func.sum(Receivable.amount_paid))
            .join(SalesContract, Receivable.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .group_by(Phase.project_id)
            .all()
        )
        return {pid: float(total) for pid, total in rows if total is not None}

    def get_outstanding_balance_by_project(self) -> Dict[str, float]:
        """Return project_id → balance_due sum (non-paid/cancelled) for all projects in one query."""
        rows = (
            self.db.query(Phase.project_id, func.sum(Receivable.balance_due))
            .join(SalesContract, Receivable.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Receivable.status.notin_(["paid", "cancelled"]))
            .group_by(Phase.project_id)
            .all()
        )
        return {pid: float(total) for pid, total in rows if total is not None}

    def get_overdue_receivable_counts_by_project(self) -> Dict[str, int]:
        """Return project_id → overdue receivable count for all projects in one query."""
        rows = (
            self.db.query(Phase.project_id, func.count(Receivable.id))
            .join(SalesContract, Receivable.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Receivable.status == "overdue")
            .group_by(Phase.project_id)
            .all()
        )
        return {pid: count for pid, count in rows}

    # ------------------------------------------------------------------
    # Portfolio cost variance roll-up helpers (PR-V6-12)
    # ------------------------------------------------------------------

    def list_projects_with_active_comparison_sets(self) -> List[Project]:
        """Return projects that have at least one active comparison set, ordered by name."""
        from sqlalchemy import select

        subq = (
            select(ConstructionCostComparisonSet.project_id)
            .where(ConstructionCostComparisonSet.is_active.is_(True))
            .distinct()
        )
        return (
            self.db.query(Project)
            .filter(Project.id.in_(subq))
            .order_by(Project.name)
            .all()
        )

    def get_portfolio_variance_totals(
        self,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """Aggregate baseline, comparison, and variance totals across all active sets.

        Returns (total_baseline, total_comparison, total_variance) as Decimals.
        """
        row = (
            self.db.query(
                func.coalesce(func.sum(ConstructionCostComparisonLine.baseline_amount), 0),
                func.coalesce(func.sum(ConstructionCostComparisonLine.comparison_amount), 0),
                func.coalesce(func.sum(ConstructionCostComparisonLine.variance_amount), 0),
            )
            .join(
                ConstructionCostComparisonSet,
                ConstructionCostComparisonLine.comparison_set_id == ConstructionCostComparisonSet.id,
            )
            .filter(ConstructionCostComparisonSet.is_active.is_(True))
            .one()
        )
        return (
            Decimal(str(row[0])),
            Decimal(str(row[1])),
            Decimal(str(row[2])),
        )

    def get_variance_totals_by_project(
        self,
    ) -> Dict[str, Tuple[Decimal, Decimal, Decimal]]:
        """Return project_id → (baseline_total, comparison_total, variance_total)
        aggregated across all active comparison lines in one query.
        """
        rows = (
            self.db.query(
                ConstructionCostComparisonSet.project_id,
                func.coalesce(func.sum(ConstructionCostComparisonLine.baseline_amount), 0),
                func.coalesce(func.sum(ConstructionCostComparisonLine.comparison_amount), 0),
                func.coalesce(func.sum(ConstructionCostComparisonLine.variance_amount), 0),
            )
            .join(
                ConstructionCostComparisonSet,
                ConstructionCostComparisonLine.comparison_set_id == ConstructionCostComparisonSet.id,
            )
            .filter(ConstructionCostComparisonSet.is_active.is_(True))
            .group_by(ConstructionCostComparisonSet.project_id)
            .all()
        )
        return {
            project_id: (
                Decimal(str(baseline)),
                Decimal(str(comparison)),
                Decimal(str(variance)),
            )
            for project_id, baseline, comparison, variance in rows
        }

    def get_active_set_count_by_project(self) -> Dict[str, int]:
        """Return project_id → count of active comparison sets in one query."""
        rows = (
            self.db.query(
                ConstructionCostComparisonSet.project_id,
                func.count(ConstructionCostComparisonSet.id),
            )
            .filter(ConstructionCostComparisonSet.is_active.is_(True))
            .group_by(ConstructionCostComparisonSet.project_id)
            .all()
        )
        return {project_id: count for project_id, count in rows}

    def get_latest_comparison_stage_by_project(self) -> Dict[str, Optional[str]]:
        """Return project_id → comparison_stage of the most recently created active set.

        Uses a SQL-level subquery that selects the max(created_at) per project
        so only one row per project is fetched (no Python-side deduplication).
        """
        from sqlalchemy import select

        # Subquery: max created_at per project for active sets
        latest_ts_subq = (
            select(
                ConstructionCostComparisonSet.project_id,
                func.max(ConstructionCostComparisonSet.created_at).label("max_ts"),
            )
            .where(ConstructionCostComparisonSet.is_active.is_(True))
            .group_by(ConstructionCostComparisonSet.project_id)
            .subquery()
        )
        rows = (
            self.db.query(
                ConstructionCostComparisonSet.project_id,
                ConstructionCostComparisonSet.comparison_stage,
            )
            .join(
                latest_ts_subq,
                (ConstructionCostComparisonSet.project_id == latest_ts_subq.c.project_id)
                & (ConstructionCostComparisonSet.created_at == latest_ts_subq.c.max_ts),
            )
            .filter(ConstructionCostComparisonSet.is_active.is_(True))
            .all()
        )
        return {project_id: stage for project_id, stage in rows}
