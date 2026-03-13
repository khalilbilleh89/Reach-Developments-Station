"""
finance.repository

Read-only database aggregation layer for the finance summary module.

Responsibilities:
  - Aggregate contract values per project
  - Aggregate collected receipts per project
  - Count units by status per project

No records are created, updated, or deleted here.
All queries use grouped database aggregation (not Python loops).
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.collections.models import PaymentReceipt
from app.modules.sales.models import SalesContract
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.finance import ReceiptStatus
from app.shared.enums.project import UnitStatus


class FinanceSummaryRepository:
    """Read-only aggregation queries for project-level financial metrics."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Unit counts
    # ------------------------------------------------------------------

    def count_units_by_project(self, project_id: str) -> int:
        """Return the total number of units in the project hierarchy."""
        return (
            self.db.query(func.count(Unit.id))
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .scalar()
            or 0
        )

    def count_units_sold_by_project(self, project_id: str) -> int:
        """Return the number of units with status UNDER_CONTRACT or REGISTERED."""
        sold_statuses = (UnitStatus.UNDER_CONTRACT.value, UnitStatus.REGISTERED.value)
        return (
            self.db.query(func.count(Unit.id))
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                Unit.status.in_(sold_statuses),
            )
            .scalar()
            or 0
        )

    def count_units_available_by_project(self, project_id: str) -> int:
        """Return the number of units with status AVAILABLE."""
        return (
            self.db.query(func.count(Unit.id))
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                Unit.status == UnitStatus.AVAILABLE.value,
            )
            .scalar()
            or 0
        )

    # ------------------------------------------------------------------
    # Revenue aggregation
    # ------------------------------------------------------------------

    def sum_contract_value_by_project(self, project_id: str) -> float:
        """Return SUM(contract_price) for all contracts on units in the project."""
        result = (
            self.db.query(func.coalesce(func.sum(SalesContract.contract_price), 0))
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .scalar()
        )
        return float(result)

    def sum_collected_by_project(self, project_id: str) -> float:
        """Return SUM(amount_received) for all recorded receipts on project contracts."""
        result = (
            self.db.query(func.coalesce(func.sum(PaymentReceipt.amount_received), 0))
            .join(SalesContract, PaymentReceipt.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                PaymentReceipt.status == ReceiptStatus.RECORDED.value,
            )
            .scalar()
        )
        return float(result)

    def average_contract_price_by_project(self, project_id: str) -> float:
        """Return AVG(contract_price) for contracts on units in the project."""
        result = (
            self.db.query(func.avg(SalesContract.contract_price))
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .scalar()
        )
        return float(result) if result is not None else 0.0
