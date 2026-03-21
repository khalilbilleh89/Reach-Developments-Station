"""
finance.service

Service layer for project-level financial summary computation.

Business rules enforced here:
  - Project must exist before any aggregation is attempted.
  - All aggregation is read-only; no records are created or mutated.
  - total_receivable = max(0, total_contract_value - total_collected)
    Clamped to zero to remain non-negative when receipts exceed contract
    value (e.g. due to rounding or adjusted contracts).
  - collection_ratio = min(total_collected / total_contract_value, 1.0)
    Clamped to 1.0 so over-collection never produces a ratio > 1.
    Defaults to 0.0 when total_contract_value is zero.
  - units_available is derived from the unit status counts, not from
    total_units - units_sold, so that reserved units are excluded from
    both buckets consistently.
"""

from typing import List

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.finance.repository import FinanceSummaryRepository
from app.modules.finance.revenue_recognition import (
    ContractRevenueData,
    calculate_contract_revenue_recognition,
)
from app.modules.finance.schemas import (
    PortfolioRevenueOverviewResponse,
    ProjectFinanceSummaryResponse,
    ProjectRevenueSummaryResponse,
    RevenueRecognitionResponse,
)
from app.modules.projects.models import Project
from app.modules.sales.models import ContractPaymentSchedule, SalesContract
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.sales import ContractPaymentStatus


class FinanceSummaryService:
    """Computes aggregated financial metrics for a project."""

    def __init__(self, db: Session) -> None:
        self.repo = FinanceSummaryRepository(db)
        self.db = db

    def get_project_summary(self, project_id: str) -> ProjectFinanceSummaryResponse:
        """Return the aggregated financial summary for a project.

        Raises HTTP 404 if the project does not exist.
        All derived monetary values are clamped to prevent invalid schema
        states when accounting data contains over-collection or rounding.
        """
        self._require_project(project_id)

        unit_counts = self.repo.get_unit_counts_by_project(project_id)
        contract_agg = self.repo.get_contract_aggregates_by_project(project_id)
        total_collected = round(self.repo.sum_collected_by_project(project_id), 2)

        total_contract_value = round(contract_agg.total_value, 2)
        total_receivable = round(max(0.0, total_contract_value - total_collected), 2)

        if total_contract_value > 0:
            collection_ratio = round(
                min(total_collected / total_contract_value, 1.0), 6
            )
        else:
            collection_ratio = 0.0

        average_unit_price = round(contract_agg.average_price, 2)

        return ProjectFinanceSummaryResponse(
            project_id=project_id,
            total_units=unit_counts.total,
            units_sold=unit_counts.sold,
            units_available=unit_counts.available,
            total_contract_value=total_contract_value,
            total_collected=total_collected,
            total_receivable=total_receivable,
            collection_ratio=collection_ratio,
            average_unit_price=average_unit_price,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str) -> Project:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id!r} not found.",
            )
        return project


# ---------------------------------------------------------------------------
# Revenue Recognition Service
# ---------------------------------------------------------------------------


class RevenueRecognitionService:
    """Computes recognized and deferred revenue from payment schedule data.

    Recognition model: cash-based.
      recognized_revenue = SUM(amount) for installments with status='paid'
      deferred_revenue   = contract_total − recognized_revenue

    All computations are read-only; no records are created or mutated.
    Recognition values are never stored persistently — they are computed
    on every request from current payment schedule state.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_contract_revenue(self, contract_id: str) -> RevenueRecognitionResponse:
        """Return revenue recognition data for a single contract.

        Raises HTTP 404 if the contract does not exist.
        """
        contract = (
            self.db.query(SalesContract)
            .filter(SalesContract.id == contract_id)
            .first()
        )
        if not contract:
            raise HTTPException(
                status_code=404,
                detail=f"Contract {contract_id!r} not found.",
            )
        paid_amount = self._sum_paid_installments(contract_id)
        data = ContractRevenueData(
            contract_id=contract_id,
            contract_total=float(contract.contract_price),
            paid_amount=paid_amount,
        )
        return calculate_contract_revenue_recognition(data)

    def get_project_revenue(self, project_id: str) -> ProjectRevenueSummaryResponse:
        """Return aggregated revenue recognition for all contracts in a project.

        Raises HTTP 404 if the project does not exist.
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id!r} not found.",
            )

        contracts = self._get_project_contracts(project_id)
        contract_details: List[RevenueRecognitionResponse] = []

        for contract in contracts:
            paid_amount = self._sum_paid_installments(contract.id)
            data = ContractRevenueData(
                contract_id=contract.id,
                contract_total=float(contract.contract_price),
                paid_amount=paid_amount,
            )
            contract_details.append(calculate_contract_revenue_recognition(data))

        total_contract_value = round(
            sum(r.contract_total for r in contract_details), 2
        )
        total_recognized = round(
            sum(r.recognized_revenue for r in contract_details), 2
        )
        total_deferred = round(
            sum(r.deferred_revenue for r in contract_details), 2
        )

        if total_contract_value > 0:
            overall_pct = round(
                min(total_recognized / total_contract_value * 100, 100.0), 4
            )
        else:
            overall_pct = 0.0

        return ProjectRevenueSummaryResponse(
            project_id=project_id,
            total_contract_value=total_contract_value,
            total_recognized_revenue=total_recognized,
            total_deferred_revenue=total_deferred,
            overall_recognition_percentage=overall_pct,
            contract_count=len(contract_details),
            contracts=contract_details,
        )

    def get_total_recognized_revenue(self) -> PortfolioRevenueOverviewResponse:
        """Return portfolio-wide revenue recognition overview.

        Aggregates across all contracts in all projects.
        """
        # Fetch all contracts with their project_id in a single JOIN query to
        # avoid N+1 round-trips through the unit hierarchy.
        rows = (
            self.db.query(SalesContract, Phase.project_id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .all()
        )

        total_contract_value = 0.0
        total_recognized = 0.0
        total_deferred = 0.0
        project_ids: set[str] = set()

        for contract, project_id in rows:
            paid_amount = self._sum_paid_installments(contract.id)
            data = ContractRevenueData(
                contract_id=contract.id,
                contract_total=float(contract.contract_price),
                paid_amount=paid_amount,
            )
            result = calculate_contract_revenue_recognition(data)
            total_contract_value += result.contract_total
            total_recognized += result.recognized_revenue
            total_deferred += result.deferred_revenue
            project_ids.add(project_id)

        total_contract_value = round(total_contract_value, 2)
        total_recognized = round(total_recognized, 2)
        total_deferred = round(total_deferred, 2)

        if total_contract_value > 0:
            overall_pct = round(
                min(total_recognized / total_contract_value * 100, 100.0), 4
            )
        else:
            overall_pct = 0.0

        return PortfolioRevenueOverviewResponse(
            total_contract_value=total_contract_value,
            total_recognized_revenue=total_recognized,
            total_deferred_revenue=total_deferred,
            overall_recognition_percentage=overall_pct,
            project_count=len(project_ids),
            contract_count=len(rows),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sum_paid_installments(self, contract_id: str) -> float:
        """Return SUM(amount) for all paid installments of a contract."""
        result = (
            self.db.query(func.coalesce(func.sum(ContractPaymentSchedule.amount), 0))
            .filter(
                ContractPaymentSchedule.contract_id == contract_id,
                ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value,
            )
            .scalar()
        )
        return float(result)

    def _get_project_contracts(self, project_id: str) -> list:
        """Return all SalesContracts belonging to a project."""
        return (
            self.db.query(SalesContract)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .all()
        )
