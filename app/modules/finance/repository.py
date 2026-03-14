"""
finance.repository

Read-only database aggregation layer for the finance summary module.

Responsibilities:
  - Aggregate contract values per project
  - Aggregate collected receipts per project
  - Count units by status per project

No records are created, updated, or deleted here.
All queries use grouped database aggregation (not Python loops).

Query design — two consolidated queries replace five separate round-trips:
  1. get_unit_counts_by_project — one query for total / sold / available counts
     using conditional SUM(CASE WHEN ...) on the same JOIN chain.
  2. get_contract_aggregates_by_project — one query for SUM + AVG of contract
     prices on the same JOIN chain.
  The collected-receipts aggregate retains its own query because it starts
  from PaymentReceipt, a different base table.
"""

from typing import NamedTuple

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.modules.collections.models import PaymentReceipt
from app.modules.sales.models import SalesContract
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.finance import ReceiptStatus
from app.shared.enums.project import UnitStatus


class UnitCounts(NamedTuple):
    total: int
    sold: int
    available: int


class ContractAggregates(NamedTuple):
    total_value: float
    average_price: float


class FinanceSummaryRepository:
    """Read-only aggregation queries for project-level financial metrics."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Unit counts — single query with conditional aggregation
    # ------------------------------------------------------------------

    def get_unit_counts_by_project(self, project_id: str) -> UnitCounts:
        """Return total / sold / available unit counts in a single SQL query.

        Uses conditional SUM(CASE WHEN ...) so the hierarchy JOIN is executed
        only once instead of three times.
        """
        sold_statuses = (UnitStatus.UNDER_CONTRACT.value, UnitStatus.REGISTERED.value)
        row = (
            self.db.query(
                func.count(Unit.id),
                func.sum(case((Unit.status.in_(sold_statuses), 1), else_=0)),
                func.sum(case((Unit.status == UnitStatus.AVAILABLE.value, 1), else_=0)),
            )
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .one()
        )
        return UnitCounts(
            total=int(row[0] or 0),
            sold=int(row[1] or 0),
            available=int(row[2] or 0),
        )

    # ------------------------------------------------------------------
    # Contract aggregation — single query for SUM + AVG
    # ------------------------------------------------------------------

    def get_contract_aggregates_by_project(self, project_id: str) -> ContractAggregates:
        """Return SUM and AVG of contract_price in a single SQL query."""
        row = (
            self.db.query(
                func.coalesce(func.sum(SalesContract.contract_price), 0),
                func.avg(SalesContract.contract_price),
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .one()
        )
        return ContractAggregates(
            total_value=float(row[0]),
            average_price=float(row[1]) if row[1] is not None else 0.0,
        )

    # ------------------------------------------------------------------
    # Collections aggregation
    # ------------------------------------------------------------------

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
