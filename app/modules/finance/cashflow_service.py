"""
finance.cashflow_service

Service layer for the cashflow forecasting engine.

Responsibilities:
  - Load PENDING and OVERDUE installment schedules from the database.
  - Map database rows to InstallmentLine objects for the engine.
  - Delegate forecast calculation to cashflow_forecast_engine.
  - Return structured response schemas.

All operations are read-only; no records are created or mutated.
"""

from __future__ import annotations

from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.finance.cashflow_forecast_engine import (
    InstallmentLine,
    build_portfolio_forecast,
    build_project_forecast,
)
from app.modules.finance.schemas import (
    MonthlyForecastEntryResponse,
    PortfolioCashflowForecastResponse,
    ProjectCashflowForecastResponse,
)
from app.modules.projects.models import Project
from app.modules.sales.models import ContractPaymentSchedule, SalesContract
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.sales import ContractPaymentStatus

# Statuses that represent collectible outstanding obligations.
_FORECAST_STATUSES = [
    ContractPaymentStatus.PENDING.value,
    ContractPaymentStatus.OVERDUE.value,
]


class CashflowForecastService:
    """Generates forward-looking cashflow projections from installment schedules.

    Forecast model: expected_collections = SUM(outstanding installment amounts)
    grouped by calendar month of the installment due_date.

    Only PENDING and OVERDUE installments are included.
    PAID and CANCELLED installments are excluded.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_project_forecast(self, project_id: str) -> ProjectCashflowForecastResponse:
        """Return the monthly cashflow forecast for a single project.

        Raises HTTP 404 if the project does not exist.
        """
        self._require_project(project_id)
        installments = self._load_project_installments(project_id)
        result = build_project_forecast(project_id, installments)

        return ProjectCashflowForecastResponse(
            project_id=result.project_id,
            total_expected=result.total_expected,
            monthly_entries=[
                MonthlyForecastEntryResponse(
                    month=e.month,
                    expected_collections=e.expected_collections,
                    installment_count=e.installment_count,
                )
                for e in result.monthly_entries
            ],
        )

    def get_portfolio_forecast(self) -> PortfolioCashflowForecastResponse:
        """Return the monthly cashflow forecast aggregated across all projects."""
        project_installments = self._load_all_project_installments()
        result = build_portfolio_forecast(project_installments)

        project_responses = [
            ProjectCashflowForecastResponse(
                project_id=pf.project_id,
                total_expected=pf.total_expected,
                monthly_entries=[
                    MonthlyForecastEntryResponse(
                        month=e.month,
                        expected_collections=e.expected_collections,
                        installment_count=e.installment_count,
                    )
                    for e in pf.monthly_entries
                ],
            )
            for pf in result.project_forecasts
        ]

        return PortfolioCashflowForecastResponse(
            total_expected=result.total_expected,
            project_count=len(project_responses),
            monthly_entries=[
                MonthlyForecastEntryResponse(
                    month=e.month,
                    expected_collections=e.expected_collections,
                    installment_count=e.installment_count,
                )
                for e in result.monthly_entries
            ],
            project_forecasts=project_responses,
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

    def _load_project_installments(self, project_id: str) -> List[InstallmentLine]:
        """Return outstanding installment lines for a single project."""
        rows = (
            self.db.query(
                ContractPaymentSchedule.contract_id,
                ContractPaymentSchedule.due_date,
                ContractPaymentSchedule.amount,
                ContractPaymentSchedule.status,
            )
            .join(
                SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                ContractPaymentSchedule.status.in_(_FORECAST_STATUSES),
            )
            .all()
        )
        return [
            InstallmentLine(
                contract_id=str(r.contract_id),
                project_id=project_id,
                due_date=r.due_date,
                amount=float(r.amount),
                status=str(r.status),
            )
            for r in rows
        ]

    def _load_all_project_installments(
        self,
    ) -> dict[str, List[InstallmentLine]]:
        """Return outstanding installment lines grouped by project_id."""
        rows = (
            self.db.query(
                Phase.project_id,
                ContractPaymentSchedule.contract_id,
                ContractPaymentSchedule.due_date,
                ContractPaymentSchedule.amount,
                ContractPaymentSchedule.status,
            )
            .join(
                SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(ContractPaymentSchedule.status.in_(_FORECAST_STATUSES))
            .all()
        )

        grouped: dict[str, List[InstallmentLine]] = {}
        for r in rows:
            pid = str(r.project_id)
            if pid not in grouped:
                grouped[pid] = []
            grouped[pid].append(
                InstallmentLine(
                    contract_id=str(r.contract_id),
                    project_id=pid,
                    due_date=r.due_date,
                    amount=float(r.amount),
                    status=str(r.status),
                )
            )
        return grouped
