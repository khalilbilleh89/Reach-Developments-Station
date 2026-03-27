"""
feasibility_feedback.repository

Read-only data access for project-level sales absorption and collection
feedback aggregation.

All methods query existing source-of-truth tables using the SQLAlchemy ORM.
No write operations are permitted in this module.

Cross-module joins follow the canonical hierarchy:
  Unit → Floor → Building → Phase → Project
"""

from typing import Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.feasibility.models import FeasibilityRun
from app.modules.phases.models import Phase
from app.modules.projects.models import Project
from app.modules.receivables.models import Receivable
from app.modules.sales.models import SalesContract
from app.modules.units.models import Unit
from app.modules.buildings.models import Building
from app.modules.floors.models import Floor


class FeasibilityFeedbackRepository:
    """Read-only repository for project-level absorption and collection feedback."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Project lookup
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> Optional[Project]:
        """Return the Project record or None if it does not exist."""
        return self.db.query(Project).filter(Project.id == project_id).first()

    # ------------------------------------------------------------------
    # Unit-level helpers
    # ------------------------------------------------------------------

    def count_units_by_status_for_project(self, project_id: str) -> Dict[str, int]:
        """Return unit status counts scoped to a single project.

        Returns a dict mapping status string → count.
        """
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

    def sum_contracted_revenue_for_project(self, project_id: str) -> float:
        """Contracted revenue for a single project (non-cancelled contracts)."""
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

    def sum_collected_cash_for_project(self, project_id: str) -> float:
        """Cash collected (amount_paid) for a single project."""
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
        """Outstanding balance (balance_due, non-paid/cancelled) for a single project."""
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

    def sum_overdue_balance_for_project(self, project_id: str) -> float:
        """Sum of balance_due for overdue receivables scoped to a single project."""
        result = (
            self.db.query(func.sum(Receivable.balance_due))
            .join(SalesContract, Receivable.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .filter(Receivable.status == "overdue")
            .scalar()
        )
        return float(result) if result is not None else 0.0

    # ------------------------------------------------------------------
    # Feasibility lineage helpers
    # ------------------------------------------------------------------

    def get_latest_feasibility_run_for_project(
        self, project_id: str
    ) -> Optional[FeasibilityRun]:
        """Return the most recently created feasibility run for this project, or None."""
        return (
            self.db.query(FeasibilityRun)
            .filter(FeasibilityRun.project_id == project_id)
            .order_by(FeasibilityRun.created_at.desc())
            .first()
        )
