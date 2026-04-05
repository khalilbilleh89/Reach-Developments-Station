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
from app.core.constants.currency import DEFAULT_CURRENCY
from app.modules.finance.cashflow_engine import (
    CashflowForecastResult,
    ForecastAssumptions,
    InstallmentRecord,
    PortfolioCashflowResult,
    compute_contract_forecast,
    compute_portfolio_forecast,
    compute_project_forecast,
)
from app.modules.finance.construction_cashflow_engine import (
    ConstructionCostRecord,
    ConstructionForecastAssumptions,
    compute_phase_construction_cashflow,
    compute_portfolio_construction_cashflow,
    compute_project_construction_cashflow,
)
from app.modules.finance.construction_financing_engine import (
    ConstructionFinancingAssumptions,
    compute_phase_construction_financing,
    compute_portfolio_construction_financing,
    compute_project_construction_financing,
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
    ConstructionCashflowPeriodRow,
    ConstructionCashflowSummaryResponse,
    ConstructionDrawPeriodRow,
    ConstructionDrawScheduleSummaryResponse,
    ConstructionFinancingAssumptionsSchema,
    ConstructionForecastAssumptionsSchema,
    ContractCashflowForecastResponse,
    MonthlyForecastEntryResponse,
    PhaseConstructionCashflowResponse,
    PhaseConstructionFinancingResponse,
    PortfolioCashflowForecastResponse,
    PortfolioCashflowForecastV2Response,
    PortfolioConstructionCashflowResponse,
    PortfolioConstructionFinancingResponse,
    ProjectCashflowForecastResponse,
    ProjectCashflowForecastV2Response,
    ProjectConstructionCashflowResponse,
    ProjectConstructionFinancingResponse,
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
        project = self._require_project(project_id)
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
            currency=project.base_currency,
        )

    def get_portfolio_forecast(self) -> PortfolioCashflowForecastResponse:
        """Return the monthly cashflow forecast aggregated across all projects."""
        project_installments = self._load_all_project_installments_legacy()
        result = build_portfolio_forecast(project_installments)

        # Build a map of project_id → base_currency for per-project cards
        project_ids = list(project_installments.keys())
        currency_map: dict[str, str] = {}
        if project_ids:
            projects = self.db.query(Project).filter(Project.id.in_(project_ids)).all()
            currency_map = {p.id: p.base_currency for p in projects}

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
                currency=currency_map.get(pf.project_id, DEFAULT_CURRENCY),
            )
            for pf in result.project_forecasts
        ]

        all_currencies = sorted({pf.currency for pf in project_responses})

        # Group total_expected by currency using per-project totals
        total_expected_grouped: Dict[str, float] = {}
        for pf in project_responses:
            total_expected_grouped[pf.currency] = round(
                total_expected_grouped.get(pf.currency, 0.0) + pf.total_expected, 2
            )

        return PortfolioCashflowForecastResponse(
            total_expected=total_expected_grouped,
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
            currencies=all_currencies,
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
        contract = self._require_contract(contract_id)

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
        return _result_to_contract_response(
            result,
            assumptions_schema or CashflowForecastAssumptions(),
            currency=contract.currency,
        )

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
        project = self._require_project(project_id)

        assumptions = _schema_to_assumptions(assumptions_schema)
        installments = self._load_project_installments_full(project_id)
        result = compute_project_forecast(project_id, installments, start_date, end_date, assumptions)

        _logger.debug(
            "Project cashflow forecast computed: project=%s periods=%d",
            project_id,
            len(result.periods),
        )
        return _result_to_project_response(
            result,
            assumptions_schema or CashflowForecastAssumptions(),
            currency=project.base_currency,
        )

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

        # Build currency map for per-project cards
        project_ids_list = list(project_installments.keys())
        currency_map: dict[str, str] = {}
        if project_ids_list:
            projects_list = self.db.query(Project).filter(Project.id.in_(project_ids_list)).all()
            currency_map = {p.id: p.base_currency for p in projects_list}

        _logger.debug(
            "Portfolio cashflow forecast computed: projects=%d periods=%d",
            len(result.project_forecasts),
            len(result.periods),
        )
        return _result_to_portfolio_response(
            result,
            assumptions_schema or CashflowForecastAssumptions(),
            project_currencies=currency_map,
        )

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

    # ------------------------------------------------------------------
    # Construction cashflow forecast  (PR-FIN-034)
    # ------------------------------------------------------------------

    def get_project_construction_forecast(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
        assumptions_schema: Optional[ConstructionForecastAssumptionsSchema] = None,
    ) -> ProjectConstructionCashflowResponse:
        """Return the construction cashflow forecast for a single project.

        Raises
        ------
        ResourceNotFoundError
            When the project does not exist.
        ValidationError
            When start_date is after end_date.
        """
        self._validate_date_window(start_date, end_date)
        self._require_project(project_id)

        assumptions = _schema_to_construction_assumptions(assumptions_schema)
        cost_records = self._load_project_construction_costs(project_id)
        result = compute_project_construction_cashflow(
            project_id, cost_records, start_date, end_date, assumptions
        )

        _logger.debug(
            "Project construction cashflow forecast computed: project_id=%s periods=%d",
            project_id,
            len(result.periods),
        )
        return _construction_result_to_project_response(
            result, assumptions_schema or ConstructionForecastAssumptionsSchema()
        )

    def get_phase_construction_forecast(
        self,
        phase_id: str,
        start_date: date,
        end_date: date,
        assumptions_schema: Optional[ConstructionForecastAssumptionsSchema] = None,
    ) -> PhaseConstructionCashflowResponse:
        """Return the construction cashflow forecast for a single phase.

        Raises
        ------
        ResourceNotFoundError
            When the phase does not exist.
        ValidationError
            When start_date is after end_date.
        """
        self._validate_date_window(start_date, end_date)
        self._require_phase(phase_id)

        assumptions = _schema_to_construction_assumptions(assumptions_schema)
        cost_records = self._load_phase_construction_costs(phase_id)
        result = compute_phase_construction_cashflow(
            phase_id, cost_records, start_date, end_date, assumptions
        )

        _logger.debug(
            "Phase construction cashflow forecast computed: phase_id=%s periods=%d",
            phase_id,
            len(result.periods),
        )
        return _construction_result_to_phase_response(
            result, assumptions_schema or ConstructionForecastAssumptionsSchema()
        )

    def get_portfolio_construction_forecast(
        self,
        start_date: date,
        end_date: date,
        assumptions_schema: Optional[ConstructionForecastAssumptionsSchema] = None,
    ) -> PortfolioConstructionCashflowResponse:
        """Return the construction cashflow forecast across the entire portfolio.

        Raises
        ------
        ValidationError
            When start_date is after end_date.
        """
        self._validate_date_window(start_date, end_date)

        assumptions = _schema_to_construction_assumptions(assumptions_schema)
        project_cost_records = self._load_all_project_construction_costs()
        result = compute_portfolio_construction_cashflow(
            project_cost_records, start_date, end_date, assumptions
        )

        _logger.debug(
            "Portfolio construction cashflow forecast computed: projects=%d periods=%d",
            len(result.project_forecasts),
            len(result.periods),
        )
        return _construction_result_to_portfolio_response(
            result, assumptions_schema or ConstructionForecastAssumptionsSchema()
        )

    # ------------------------------------------------------------------
    # Construction financing  (PR-FIN-036)
    # ------------------------------------------------------------------

    def compute_project_construction_financing(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
        cashflow_assumptions_schema: Optional[ConstructionForecastAssumptionsSchema] = None,
        financing_assumptions_schema: Optional[ConstructionFinancingAssumptionsSchema] = None,
    ) -> ProjectConstructionFinancingResponse:
        """Return the construction financing draw schedule for a single project.

        Derives the draw schedule from the project's construction cashflow
        forecast and the supplied capital stack assumptions.

        Raises
        ------
        ResourceNotFoundError
            When the project does not exist.
        ValidationError
            When start_date is after end_date.
        """
        self._validate_date_window(start_date, end_date)
        self._require_project(project_id)

        cashflow_assumptions = _schema_to_construction_assumptions(cashflow_assumptions_schema)
        cost_records = self._load_project_construction_costs(project_id)
        cashflow_result = compute_project_construction_cashflow(
            project_id, cost_records, start_date, end_date, cashflow_assumptions
        )

        financing_assumptions = _schema_to_financing_assumptions(financing_assumptions_schema)
        result = compute_project_construction_financing(
            project_id, cashflow_result.periods, financing_assumptions
        )

        _logger.debug(
            "Project construction financing computed: project_id=%s periods=%d",
            project_id,
            len(result.periods),
        )
        return _financing_result_to_project_response(
            result,
            project_id,
            financing_assumptions_schema or ConstructionFinancingAssumptionsSchema(),
        )

    def compute_phase_construction_financing(
        self,
        phase_id: str,
        start_date: date,
        end_date: date,
        cashflow_assumptions_schema: Optional[ConstructionForecastAssumptionsSchema] = None,
        financing_assumptions_schema: Optional[ConstructionFinancingAssumptionsSchema] = None,
    ) -> PhaseConstructionFinancingResponse:
        """Return the construction financing draw schedule for a single phase.

        Raises
        ------
        ResourceNotFoundError
            When the phase does not exist.
        ValidationError
            When start_date is after end_date.
        """
        self._validate_date_window(start_date, end_date)
        self._require_phase(phase_id)

        cashflow_assumptions = _schema_to_construction_assumptions(cashflow_assumptions_schema)
        cost_records = self._load_phase_construction_costs(phase_id)
        cashflow_result = compute_phase_construction_cashflow(
            phase_id, cost_records, start_date, end_date, cashflow_assumptions
        )

        financing_assumptions = _schema_to_financing_assumptions(financing_assumptions_schema)
        result = compute_phase_construction_financing(
            phase_id, cashflow_result.periods, financing_assumptions
        )

        _logger.debug(
            "Phase construction financing computed: phase_id=%s periods=%d",
            phase_id,
            len(result.periods),
        )
        return _financing_result_to_phase_response(
            result,
            phase_id,
            financing_assumptions_schema or ConstructionFinancingAssumptionsSchema(),
        )

    def compute_portfolio_construction_financing(
        self,
        start_date: date,
        end_date: date,
        cashflow_assumptions_schema: Optional[ConstructionForecastAssumptionsSchema] = None,
        financing_assumptions_schema: Optional[ConstructionFinancingAssumptionsSchema] = None,
    ) -> PortfolioConstructionFinancingResponse:
        """Return the construction financing draw schedule across the entire portfolio.

        Raises
        ------
        ValidationError
            When start_date is after end_date.
        """
        self._validate_date_window(start_date, end_date)

        cashflow_assumptions = _schema_to_construction_assumptions(cashflow_assumptions_schema)
        project_cost_records = self._load_all_project_construction_costs()

        # Compute per-project cashflow periods first.
        project_cashflow_periods = {
            pid: compute_project_construction_cashflow(
                pid, records, start_date, end_date, cashflow_assumptions
            ).periods
            for pid, records in project_cost_records.items()
        }

        financing_assumptions = _schema_to_financing_assumptions(financing_assumptions_schema)
        result = compute_portfolio_construction_financing(
            project_cashflow_periods, financing_assumptions
        )

        _logger.debug(
            "Portfolio construction financing computed: projects=%d periods=%d",
            len(result.project_results),
            len(result.periods),
        )
        return _financing_result_to_portfolio_response(
            result, financing_assumptions_schema or ConstructionFinancingAssumptionsSchema()
        )

    # ------------------------------------------------------------------
    # Construction cost loading helpers  (PR-FIN-034)
    # These return empty lists until a construction cost model is added.
    # The engine is fully functional with real data once the model exists.
    # ------------------------------------------------------------------

    def _load_project_construction_costs(
        self, project_id: str
    ) -> List[ConstructionCostRecord]:
        """Load construction cost records for a single project.

        Returns an empty list until the ConstructionCost model is introduced.
        """
        return []

    def _load_phase_construction_costs(
        self, phase_id: str
    ) -> List[ConstructionCostRecord]:
        """Load construction cost records for a single phase.

        Returns an empty list until the ConstructionCost model is introduced.
        """
        return []

    def _load_all_project_construction_costs(
        self,
    ) -> Dict[str, List[ConstructionCostRecord]]:
        """Load construction cost records grouped by project_id.

        Returns an empty dict until the ConstructionCost model is introduced.
        """
        return {}

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

    def _require_phase(self, phase_id: str) -> Phase:
        phase = self.db.query(Phase).filter(Phase.id == phase_id).first()
        if not phase:
            raise ResourceNotFoundError(f"Phase '{phase_id}' not found.")
        return phase

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


def _summary_to_response(
    summary: object, currency: Optional[str] = None
) -> CashflowForecastSummaryResponse:
    return CashflowForecastSummaryResponse(
        scheduled_total=summary.scheduled_total,
        collected_total=summary.collected_total,
        expected_total=summary.expected_total,
        variance_to_schedule=summary.variance_to_schedule,
        currency=currency,
    )


def _result_to_contract_response(
    result: CashflowForecastResult,
    assumptions_schema: CashflowForecastAssumptions,
    currency: Optional[str] = None,
) -> ContractCashflowForecastResponse:
    return ContractCashflowForecastResponse(
        scope_type=result.scope_type,
        contract_id=result.scope_id,
        start_date=result.start_date,
        end_date=result.end_date,
        granularity=result.granularity,
        assumptions=assumptions_schema,
        summary=_summary_to_response(result.summary, currency=currency),
        periods=[_period_to_row(p) for p in result.periods],
        currency=currency or DEFAULT_CURRENCY,
    )


def _result_to_project_response(
    result: CashflowForecastResult,
    assumptions_schema: CashflowForecastAssumptions,
    currency: Optional[str] = None,
) -> ProjectCashflowForecastV2Response:
    return ProjectCashflowForecastV2Response(
        scope_type=result.scope_type,
        project_id=result.scope_id,
        start_date=result.start_date,
        end_date=result.end_date,
        granularity=result.granularity,
        assumptions=assumptions_schema,
        summary=_summary_to_response(result.summary, currency=currency),
        periods=[_period_to_row(p) for p in result.periods],
        currency=currency or DEFAULT_CURRENCY,
    )


def _result_to_portfolio_response(
    result: PortfolioCashflowResult,
    assumptions_schema: CashflowForecastAssumptions,
    project_currencies: Optional[dict] = None,
) -> PortfolioCashflowForecastV2Response:
    pmap = project_currencies or {}
    project_responses = [
        _result_to_project_response(pf, assumptions_schema, currency=pmap.get(pf.scope_id))
        for pf in result.project_forecasts
    ]
    all_currencies = sorted({pr.currency for pr in project_responses})
    return PortfolioCashflowForecastV2Response(
        scope_type=result.scope_type,
        start_date=result.start_date,
        end_date=result.end_date,
        granularity=result.granularity,
        assumptions=assumptions_schema,
        summary=_summary_to_response(result.summary, currency=None),
        periods=[_period_to_row(p) for p in result.periods],
        project_forecasts=project_responses,
        currencies=all_currencies,
    )


# ---------------------------------------------------------------------------
# Construction cashflow helpers  (PR-FIN-034)
# ---------------------------------------------------------------------------


def _schema_to_construction_assumptions(
    schema: Optional[ConstructionForecastAssumptionsSchema],
) -> ConstructionForecastAssumptions:
    """Convert Pydantic assumptions schema to the engine ConstructionForecastAssumptions."""
    if schema is None:
        return ConstructionForecastAssumptions()
    return ConstructionForecastAssumptions(
        execution_probability=schema.execution_probability,
        cost_spread_method=schema.spread_method,
        include_committed=schema.include_committed,
    )


def _construction_period_to_row(period: object) -> ConstructionCashflowPeriodRow:
    """Convert a ConstructionCashflowPeriodResult to the Pydantic schema row."""
    return ConstructionCashflowPeriodRow(
        period_label=period.period_label,
        planned_cost=period.planned_cost,
        committed_cost=period.committed_cost,
        expected_cost=period.expected_cost,
        variance_to_plan=period.variance_to_plan,
        cumulative_cost=period.cumulative_cost,
        cost_item_count=period.cost_item_count,
    )


def _construction_summary_to_response(summary: object) -> ConstructionCashflowSummaryResponse:
    return ConstructionCashflowSummaryResponse(
        planned_total=summary.planned_total,
        committed_total=summary.committed_total,
        expected_total=summary.expected_total,
        variance_to_plan=summary.variance_to_plan,
    )


def _construction_result_to_project_response(
    result: object,
    assumptions_schema: ConstructionForecastAssumptionsSchema,
) -> ProjectConstructionCashflowResponse:
    return ProjectConstructionCashflowResponse(
        scope_type=result.scope_type,
        project_id=result.scope_id,
        start_date=result.start_date,
        end_date=result.end_date,
        granularity=result.granularity,
        assumptions=assumptions_schema,
        summary=_construction_summary_to_response(result.summary),
        periods=[_construction_period_to_row(p) for p in result.periods],
    )


def _construction_result_to_phase_response(
    result: object,
    assumptions_schema: ConstructionForecastAssumptionsSchema,
) -> PhaseConstructionCashflowResponse:
    return PhaseConstructionCashflowResponse(
        scope_type=result.scope_type,
        phase_id=result.scope_id,
        start_date=result.start_date,
        end_date=result.end_date,
        granularity=result.granularity,
        assumptions=assumptions_schema,
        summary=_construction_summary_to_response(result.summary),
        periods=[_construction_period_to_row(p) for p in result.periods],
    )


def _construction_result_to_portfolio_response(
    result: object,
    assumptions_schema: ConstructionForecastAssumptionsSchema,
) -> PortfolioConstructionCashflowResponse:
    project_responses = [
        _construction_result_to_project_response(pf, assumptions_schema)
        for pf in result.project_forecasts
    ]
    return PortfolioConstructionCashflowResponse(
        scope_type=result.scope_type,
        start_date=result.start_date,
        end_date=result.end_date,
        granularity=result.granularity,
        assumptions=assumptions_schema,
        summary=_construction_summary_to_response(result.summary),
        periods=[_construction_period_to_row(p) for p in result.periods],
        project_forecasts=project_responses,
    )


# ---------------------------------------------------------------------------
# Construction financing helpers  (PR-FIN-036)
# ---------------------------------------------------------------------------


def _schema_to_financing_assumptions(
    schema: Optional[ConstructionFinancingAssumptionsSchema],
) -> ConstructionFinancingAssumptions:
    """Convert Pydantic financing schema to engine ConstructionFinancingAssumptions."""
    if schema is None:
        return ConstructionFinancingAssumptions()
    return ConstructionFinancingAssumptions(
        debt_ratio=schema.debt_ratio,
        equity_ratio=schema.equity_ratio,
        loan_draw_method=schema.loan_draw_method,
        equity_injection_method=schema.equity_injection_method,
        financing_start_offset=schema.financing_start_offset,
        financing_probability=schema.financing_probability,
    )


def _financing_draw_period_to_row(period: object) -> ConstructionDrawPeriodRow:
    """Convert a ConstructionDrawPeriodResult to the Pydantic schema row."""
    return ConstructionDrawPeriodRow(
        period_label=period.period_label,
        period_cost=period.period_cost,
        debt_draw=period.debt_draw,
        equity_contribution=period.equity_contribution,
        cumulative_debt=period.cumulative_debt,
        cumulative_equity=period.cumulative_equity,
    )


def _financing_summary_to_response(summary: object) -> ConstructionDrawScheduleSummaryResponse:
    return ConstructionDrawScheduleSummaryResponse(
        total_cost=summary.total_cost,
        total_debt=summary.total_debt,
        total_equity=summary.total_equity,
        debt_to_cost_ratio=summary.debt_to_cost_ratio,
        equity_to_cost_ratio=summary.equity_to_cost_ratio,
    )


def _financing_result_to_project_response(
    result: object,
    project_id: str,
    assumptions_schema: ConstructionFinancingAssumptionsSchema,
) -> ProjectConstructionFinancingResponse:
    return ProjectConstructionFinancingResponse(
        scope_type=result.scope_type,
        project_id=project_id,
        assumptions=assumptions_schema,
        summary=_financing_summary_to_response(result.summary),
        periods=[_financing_draw_period_to_row(p) for p in result.periods],
    )


def _financing_result_to_phase_response(
    result: object,
    phase_id: str,
    assumptions_schema: ConstructionFinancingAssumptionsSchema,
) -> PhaseConstructionFinancingResponse:
    return PhaseConstructionFinancingResponse(
        scope_type=result.scope_type,
        phase_id=phase_id,
        assumptions=assumptions_schema,
        summary=_financing_summary_to_response(result.summary),
        periods=[_financing_draw_period_to_row(p) for p in result.periods],
    )


def _financing_result_to_portfolio_response(
    result: object,
    assumptions_schema: ConstructionFinancingAssumptionsSchema,
) -> PortfolioConstructionFinancingResponse:
    project_responses = [
        _financing_result_to_project_response(pr, pr.scope_id, assumptions_schema)
        for pr in result.project_results
    ]
    return PortfolioConstructionFinancingResponse(
        scope_type=result.scope_type,
        assumptions=assumptions_schema,
        summary=_financing_summary_to_response(result.summary),
        periods=[_financing_draw_period_to_row(p) for p in result.periods],
        project_results=project_responses,
    )
