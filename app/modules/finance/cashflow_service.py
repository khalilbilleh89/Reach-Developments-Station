"""
finance.cashflow_service

Service layer for cashflow forecasting engines.

Responsibilities:
  - Load payment schedule records from the database.
  - Map database rows to engine input objects.
  - Delegate all calculations to the dedicated engines.
  - Return structured response schemas.

Two forecast surfaces are served by this class:

Legacy simple forecast  (get_project_forecast / get_portfolio_forecast)
    Loads only PENDING/OVERDUE installments and delegates to
    cashflow_forecast_engine.  Preserves backward-compatible API contract
    for existing /finance/cashflow/forecast endpoints.

Comprehensive forecast  (get_contract_forecast_v2 / get_project_forecast_v2 /
                         get_portfolio_forecast_v2)
    Loads all non-cancelled installments and delegates to cashflow_engine.
    Supports date windows, collection-probability assumptions, and
    overdue carry-forward logic for the PR-33 endpoints.

All operations are read-only; no records are created or mutated.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.finance.cashflow_engine import (
    CashflowForecastResult,
    ForecastAssumptions,
    InstallmentRecord,
    PortfolioCashflowResult,
    compute_contract_forecast,
    compute_portfolio_forecast,
    compute_project_forecast,
)
from app.modules.finance.cashflow_forecast_engine import (
    InstallmentLine,
    build_portfolio_forecast,
    build_project_forecast,
)
from app.modules.finance.schemas import (
    CashflowForecastAssumptions,
    CashflowForecastSummaryResponse,
    CashflowPeriodRow,
    ContractCashflowForecastResponse,
    MonthlyForecastEntryResponse,
    PortfolioCashflowForecastResponse,
    PortfolioCashflowForecastV2Response,
    ProjectCashflowForecastResponse,
    ProjectCashflowForecastV2Response,
)
from app.modules.projects.models import Project
from app.modules.sales.models import ContractPaymentSchedule, SalesContract
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.sales import ContractPaymentStatus

_logger = get_logger("reach_developments.finance.cashflow_service")

# Statuses that represent collectible outstanding obligations (legacy engine).
_FORECAST_STATUSES = [
    ContractPaymentStatus.PENDING.value,
    ContractPaymentStatus.OVERDUE.value,
]

# Statuses to include for the comprehensive forecast (all non-cancelled).
_ALL_ACTIVE_STATUSES = [
    ContractPaymentStatus.PENDING.value,
    ContractPaymentStatus.OVERDUE.value,
    ContractPaymentStatus.PAID.value,
]


class CashflowForecastService:
    """Generates forward-looking cashflow projections from installment schedules.

    Legacy forecast model:
        expected_collections = SUM(outstanding installment amounts)
        grouped by calendar month of the installment due_date.

    Comprehensive forecast model (PR-33):
        scheduled_amount  = contractual due amount per period
        collected_amount  = amount already settled
        expected_amount   = outstanding × collection_probability
        variance          = expected − scheduled
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Legacy simple forecast endpoints (backward-compatible)
    # ------------------------------------------------------------------

    def get_project_forecast(self, project_id: str) -> ProjectCashflowForecastResponse:
        """Return the monthly cashflow forecast for a single project.

        Raises ResourceNotFoundError if the project does not exist.
        """
        self._require_project(project_id)
        installments = self._load_project_installments_legacy(project_id)
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
        project_installments = self._load_all_project_installments_legacy()
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
    # Comprehensive forecast  (PR-33)
    # ------------------------------------------------------------------

    def get_contract_forecast_v2(
        self,
        contract_id: str,
        start_date: date,
        end_date: date,
        assumptions_schema: Optional[CashflowForecastAssumptions] = None,
    ) -> ContractCashflowForecastResponse:
        """Return the comprehensive cashflow forecast for a single contract.

        Parameters
        ----------
        contract_id:
            Identifier of the sales contract.
        start_date:
            Inclusive start of the forecast window.
        end_date:
            Inclusive end of the forecast window (must be >= start_date).
        assumptions_schema:
            Optional forecast assumption overrides.  Defaults to deterministic
            100% collection with overdue carry-forward enabled.

        Raises
        ------
        ResourceNotFoundError
            When the contract does not exist.
        ValidationError
            When start_date is after end_date.
        """
        self._validate_date_window(start_date, end_date)
        self._require_contract(contract_id)

        assumptions = _schema_to_assumptions(assumptions_schema)
        installments = self._load_contract_installments(contract_id)
        result = compute_contract_forecast(
            contract_id,
            installments,
            start_date,
            end_date,
            assumptions,
        )

        _logger.debug(
            "Contract cashflow forecast computed: contract=%s periods=%d",
            contract_id,
            len(result.periods),
        )
        return _result_to_contract_response(result, assumptions_schema or CashflowForecastAssumptions())

    def get_project_forecast_v2(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
        assumptions_schema: Optional[CashflowForecastAssumptions] = None,
    ) -> ProjectCashflowForecastV2Response:
        """Return the comprehensive cashflow forecast for a single project.

        Raises
        ------
        ResourceNotFoundError
            When the project does not exist.
        ValidationError
            When start_date is after end_date.
        """
        self._validate_date_window(start_date, end_date)
        self._require_project(project_id)

        assumptions = _schema_to_assumptions(assumptions_schema)
        installments = self._load_project_installments_full(project_id)
        result = compute_project_forecast(project_id, installments, start_date, end_date, assumptions)

        _logger.debug(
            "Project cashflow forecast computed: project=%s periods=%d",
            project_id,
            len(result.periods),
        )
        return _result_to_project_response(result, assumptions_schema or CashflowForecastAssumptions())

    def get_portfolio_forecast_v2(
        self,
        start_date: date,
        end_date: date,
        assumptions_schema: Optional[CashflowForecastAssumptions] = None,
    ) -> PortfolioCashflowForecastV2Response:
        """Return the comprehensive cashflow forecast across the entire portfolio.

        Raises
        ------
        ValidationError
            When start_date is after end_date.
        """
        self._validate_date_window(start_date, end_date)

        assumptions = _schema_to_assumptions(assumptions_schema)
        project_installments = self._load_all_project_installments_full()
        result = compute_portfolio_forecast(project_installments, start_date, end_date, assumptions)

        _logger.debug(
            "Portfolio cashflow forecast computed: projects=%d periods=%d",
            len(result.project_forecasts),
            len(result.periods),
        )
        return _result_to_portfolio_response(result, assumptions_schema or CashflowForecastAssumptions())

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_date_window(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise ValidationError(
                "start_date must not be after end_date.",
                details={"start_date": str(start_date), "end_date": str(end_date)},
            )

    def _require_project(self, project_id: str) -> Project:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")
        return project

    def _require_contract(self, contract_id: str) -> SalesContract:
        contract = (
            self.db.query(SalesContract)
            .filter(SalesContract.id == contract_id)
            .first()
        )
        if not contract:
            raise ResourceNotFoundError(f"Contract '{contract_id}' not found.")
        return contract

    # ------------------------------------------------------------------
    # DB loading helpers — legacy engine (PENDING + OVERDUE only)
    # ------------------------------------------------------------------

    def _load_project_installments_legacy(self, project_id: str) -> List[InstallmentLine]:
        """Return outstanding installment lines for a single project (legacy engine)."""
        rows = (
            self.db.query(
                ContractPaymentSchedule.contract_id,
                ContractPaymentSchedule.due_date,
                ContractPaymentSchedule.amount,
                ContractPaymentSchedule.status,
            )
            .join(SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id)
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

    def _load_all_project_installments_legacy(self) -> Dict[str, List[InstallmentLine]]:
        """Return outstanding installment lines grouped by project_id (legacy engine)."""
        rows = (
            self.db.query(
                Phase.project_id,
                ContractPaymentSchedule.contract_id,
                ContractPaymentSchedule.due_date,
                ContractPaymentSchedule.amount,
                ContractPaymentSchedule.status,
            )
            .join(SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(ContractPaymentSchedule.status.in_(_FORECAST_STATUSES))
            .all()
        )

        grouped: Dict[str, List[InstallmentLine]] = {}
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

    # ------------------------------------------------------------------
    # DB loading helpers — comprehensive engine (all non-cancelled)
    # ------------------------------------------------------------------

    def _load_contract_installments(self, contract_id: str) -> List[InstallmentRecord]:
        """Return all non-cancelled installment records for a single contract.

        Queries directly on ContractPaymentSchedule filtered by contract_id
        without the Unit→Floor→Building→Phase join chain, since no hierarchy
        data is needed for a contract-scoped forecast.
        """
        rows = (
            self.db.query(
                ContractPaymentSchedule.contract_id,
                ContractPaymentSchedule.due_date,
                ContractPaymentSchedule.amount,
                ContractPaymentSchedule.status,
            )
            .filter(
                ContractPaymentSchedule.contract_id == contract_id,
                ContractPaymentSchedule.status.in_(_ALL_ACTIVE_STATUSES),
            )
            .all()
        )
        return [_row_to_record(r, project_id=None) for r in rows]

    def _load_project_installments_full(self, project_id: str) -> List[InstallmentRecord]:
        """Return all non-cancelled installment records for a single project."""
        rows = (
            self.db.query(
                ContractPaymentSchedule.contract_id,
                ContractPaymentSchedule.due_date,
                ContractPaymentSchedule.amount,
                ContractPaymentSchedule.status,
                Phase.project_id,
            )
            .join(SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                ContractPaymentSchedule.status.in_(_ALL_ACTIVE_STATUSES),
            )
            .all()
        )
        return [_row_to_record(r, project_id=project_id) for r in rows]

    def _load_all_project_installments_full(self) -> Dict[str, List[InstallmentRecord]]:
        """Return all non-cancelled installment records grouped by project_id."""
        rows = (
            self.db.query(
                Phase.project_id,
                ContractPaymentSchedule.contract_id,
                ContractPaymentSchedule.due_date,
                ContractPaymentSchedule.amount,
                ContractPaymentSchedule.status,
            )
            .join(SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(ContractPaymentSchedule.status.in_(_ALL_ACTIVE_STATUSES))
            .all()
        )

        grouped: Dict[str, List[InstallmentRecord]] = {}
        for r in rows:
            pid = str(r.project_id)
            if pid not in grouped:
                grouped[pid] = []
            grouped[pid].append(_row_to_record(r, project_id=pid))
        return grouped


# ---------------------------------------------------------------------------
# Private conversion helpers
# ---------------------------------------------------------------------------


def _row_to_record(row: object, project_id: Optional[str]) -> InstallmentRecord:
    """Convert a DB row tuple to an InstallmentRecord for the comprehensive engine."""
    status = str(row.status)
    is_paid = status == ContractPaymentStatus.PAID.value
    amount = float(row.amount)
    return InstallmentRecord(
        contract_id=str(row.contract_id),
        project_id=project_id or "",
        due_date=row.due_date,
        scheduled_amount=amount,
        collected_amount=amount if is_paid else 0.0,
        status=status,
    )


def _schema_to_assumptions(
    schema: Optional[CashflowForecastAssumptions],
) -> ForecastAssumptions:
    """Convert a Pydantic assumptions schema to the engine ForecastAssumptions dataclass."""
    if schema is None:
        return ForecastAssumptions()
    return ForecastAssumptions(
        collection_probability=schema.collection_probability,
        carry_forward_overdue=schema.carry_forward_overdue,
        include_paid_in_schedule=schema.include_paid_in_schedule,
    )


def _period_to_row(period: object) -> CashflowPeriodRow:
    """Convert a CashflowPeriodResult to the Pydantic CashflowPeriodRow schema."""
    return CashflowPeriodRow(
        period_start=period.period_start,
        period_end=period.period_end,
        period_label=period.period_label,
        scheduled_amount=period.scheduled_amount,
        collected_amount=period.collected_amount,
        expected_amount=period.expected_amount,
        variance_to_schedule=period.variance_to_schedule,
        cumulative_expected_amount=period.cumulative_expected_amount,
        installment_count=period.installment_count,
    )


def _summary_to_response(summary: object) -> CashflowForecastSummaryResponse:
    return CashflowForecastSummaryResponse(
        scheduled_total=summary.scheduled_total,
        collected_total=summary.collected_total,
        expected_total=summary.expected_total,
        variance_to_schedule=summary.variance_to_schedule,
    )


def _result_to_contract_response(
    result: CashflowForecastResult,
    assumptions_schema: CashflowForecastAssumptions,
) -> ContractCashflowForecastResponse:
    return ContractCashflowForecastResponse(
        scope_type=result.scope_type,
        contract_id=result.scope_id,
        start_date=result.start_date,
        end_date=result.end_date,
        granularity=result.granularity,
        assumptions=assumptions_schema,
        summary=_summary_to_response(result.summary),
        periods=[_period_to_row(p) for p in result.periods],
    )


def _result_to_project_response(
    result: CashflowForecastResult,
    assumptions_schema: CashflowForecastAssumptions,
) -> ProjectCashflowForecastV2Response:
    return ProjectCashflowForecastV2Response(
        scope_type=result.scope_type,
        project_id=result.scope_id,
        start_date=result.start_date,
        end_date=result.end_date,
        granularity=result.granularity,
        assumptions=assumptions_schema,
        summary=_summary_to_response(result.summary),
        periods=[_period_to_row(p) for p in result.periods],
    )


def _result_to_portfolio_response(
    result: PortfolioCashflowResult,
    assumptions_schema: CashflowForecastAssumptions,
) -> PortfolioCashflowForecastV2Response:
    project_responses = [
        _result_to_project_response(pf, assumptions_schema)
        for pf in result.project_forecasts
    ]
    return PortfolioCashflowForecastV2Response(
        scope_type=result.scope_type,
        start_date=result.start_date,
        end_date=result.end_date,
        granularity=result.granularity,
        assumptions=assumptions_schema,
        summary=_summary_to_response(result.summary),
        periods=[_period_to_row(p) for p in result.periods],
        project_forecasts=project_responses,
    )
