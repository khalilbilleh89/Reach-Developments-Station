"""
portfolio.repository

Read-only data access for portfolio-level aggregation.

All methods query existing source-of-truth tables using the SQLAlchemy ORM.
No write operations are permitted in this module.

Cross-module joins are performed inline here because the portfolio layer is
an aggregation-only consumer and does not own any domain records.
"""

from typing import Any, Dict, List

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
