"""
finance.portfolio_summary_service

Aggregates financial metrics across all projects to produce a single
executive-level portfolio financial summary.

Responsibilities:
  - Compute total recognized and deferred revenue from all contracts.
  - Compute total receivables exposure and overdue percentage.
  - Extract next-calendar-month expected cashflow from the forecast engine.
  - Produce per-project breakdown: recognized revenue, receivables exposure,
    and collection rate.

All computation is read-only; no records are created or mutated.
This service delegates data-loading to the existing financial engines and
performs portfolio-level aggregation on top of their outputs.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.finance.cashflow_service import CashflowForecastService
from app.modules.finance.constants import RECEIVABLE_STATUSES
from app.modules.finance.date_utils import next_month_key
from app.modules.finance.revenue_recognition import (
    ContractRevenueData,
    calculate_contract_revenue_recognition,
)
from app.modules.finance.schemas import (
    PortfolioFinancialSummaryResponse,
    ProjectFinancialSummaryEntry,
)
from app.modules.finance.service import (
    CollectionsAgingService,
    RevenueRecognitionService,
)
from app.modules.projects.models import Project
from app.modules.sales.models import ContractPaymentSchedule, SalesContract
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.sales import ContractPaymentStatus


def _next_month_key() -> str:
    """Return the YYYY-MM key for the calendar month after today.

    Delegates to the shared ``next_month_key`` helper in
    ``app.modules.finance.date_utils``.  Kept here for backward
    compatibility with existing tests that monkeypatch this name.
    """
    return next_month_key()


class PortfolioSummaryService:
    """Produces a consolidated financial summary for the entire portfolio.

    Internally delegates to:
      - RevenueRecognitionService  — recognized / deferred revenue
      - CollectionsAgingService    — total and overdue receivables
      - CashflowForecastService    — next-month expected cashflow

    All queries are executed in a single database session and are read-only.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._revenue_svc = RevenueRecognitionService(db)
        self._aging_svc = CollectionsAgingService(db)
        self._forecast_svc = CashflowForecastService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_portfolio_summary(self) -> PortfolioFinancialSummaryResponse:
        """Return the consolidated portfolio financial summary.

        Aggregates data from the revenue recognition, receivables aging,
        and cashflow forecasting engines.  Monetary totals are grouped by
        currency so consumers receive denomination-safe payloads.
        """
        # --- Revenue (grouped by currency) ---
        revenue_recognized_grouped, revenue_deferred_grouped, revenue_currencies = (
            self._get_recognized_revenue_grouped()
        )

        # --- Receivables aging (grouped by currency) ---
        aging_overview = self._aging_svc.get_portfolio_aging()
        receivables_grouped, overdue_grouped = self._get_receivables_grouped()

        # --- Overdue percentage: only valid when single-currency ---
        all_currencies = sorted(
            set(revenue_currencies)
            | set(receivables_grouped.keys())
            | set(overdue_grouped.keys())
        )
        if len(all_currencies) <= 1 and aging_overview.total_outstanding > 0:
            total_overdue = sum(overdue_grouped.values())
            total_outstanding = sum(receivables_grouped.values())
            overdue_pct: Optional[float] = round(
                min(total_overdue / total_outstanding * 100, 100.0), 4
            ) if total_outstanding > 0 else 0.0
        elif len(all_currencies) <= 1:
            overdue_pct = 0.0
        else:
            # Multi-currency: pct across different denominations is invalid
            overdue_pct = None

        # --- Cashflow forecast — next calendar month (grouped by currency) ---
        cashflow = self._forecast_svc.get_portfolio_forecast()
        next_month = _next_month_key()
        forecast_grouped: Dict[str, float] = {}
        for pf in cashflow.project_forecasts:
            project_currency = pf.currency
            for entry in pf.monthly_entries:
                if entry.month == next_month:
                    forecast_grouped[project_currency] = (
                        forecast_grouped.get(project_currency, 0.0) + entry.expected_collections
                    )
                    break

        # --- Per-project breakdown ---
        project_summaries = self._build_project_summaries()
        project_count = self._count_projects_with_contracts()

        return PortfolioFinancialSummaryResponse(
            total_revenue_recognized=revenue_recognized_grouped,
            total_deferred_revenue=revenue_deferred_grouped,
            total_receivables=receivables_grouped,
            overdue_receivables=overdue_grouped,
            overdue_receivables_pct=overdue_pct,
            forecast_next_month=forecast_grouped,
            project_count=project_count,
            project_summaries=project_summaries,
            currencies=all_currencies,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_projects_with_contracts(self) -> int:
        """Return count of distinct projects that have at least one contract."""
        revenue_overview = self._revenue_svc.get_total_recognized_revenue()
        return revenue_overview.project_count

    def _get_recognized_revenue_grouped(
        self,
    ) -> tuple[Dict[str, float], Dict[str, float], list[str]]:
        """Return (recognized_by_currency, deferred_by_currency, all_currencies).

        Executes a single JOIN query and groups recognition results by
        contract currency to produce denomination-safe aggregates.
        """
        rows = (
            self.db.query(SalesContract, Phase.project_id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .all()
        )

        if not rows:
            return {}, {}, []

        contract_ids = [c.id for c, _ in rows]
        paid_map = self._sum_paid_installments_bulk(contract_ids)

        recognized_by_currency: Dict[str, float] = {}
        deferred_by_currency: Dict[str, float] = {}

        for contract, _ in rows:
            currency = getattr(contract, "currency", None) or "AED"
            paid = paid_map.get(contract.id, 0.0)
            cdata = ContractRevenueData(
                contract_id=contract.id,
                contract_total=float(contract.contract_price),
                paid_amount=paid,
            )
            crec = calculate_contract_revenue_recognition(cdata)
            recognized_by_currency[currency] = round(
                recognized_by_currency.get(currency, 0.0) + crec.recognized_revenue, 2
            )
            deferred_by_currency[currency] = round(
                deferred_by_currency.get(currency, 0.0) + crec.deferred_revenue, 2
            )

        all_currencies = sorted(set(recognized_by_currency) | set(deferred_by_currency))
        return recognized_by_currency, deferred_by_currency, all_currencies

    def _get_receivables_grouped(
        self,
    ) -> tuple[Dict[str, float], Dict[str, float]]:
        """Return (total_receivables_by_currency, overdue_receivables_by_currency).

        Uses a single grouped SQL query via the outstanding installments join chain.
        """
        rows = (
            self.db.query(
                ContractPaymentSchedule.currency,
                func.sum(ContractPaymentSchedule.amount),
            )
            .join(
                SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(ContractPaymentSchedule.status.in_(RECEIVABLE_STATUSES))
            .group_by(ContractPaymentSchedule.currency)
            .all()
        )
        receivables: Dict[str, float] = {
            currency: round(float(total), 2)
            for currency, total in rows
            if total is not None
        }

        from datetime import date as _date
        today = _date.today()

        overdue_rows = (
            self.db.query(
                ContractPaymentSchedule.currency,
                func.sum(ContractPaymentSchedule.amount),
            )
            .join(
                SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                ContractPaymentSchedule.status.in_(RECEIVABLE_STATUSES),
                ContractPaymentSchedule.due_date < today,
            )
            .group_by(ContractPaymentSchedule.currency)
            .all()
        )
        overdue: Dict[str, float] = {
            currency: round(float(total), 2)
            for currency, total in overdue_rows
            if total is not None
        }

        return receivables, overdue

    def _build_project_summaries(self) -> List[ProjectFinancialSummaryEntry]:
        """Return per-project financial metrics using bulk SQL queries.

        Executes three queries regardless of project count to avoid N+1
        round-trips.

        Per-project recognized revenue is computed by summing the per-contract
        clamped recognition results — NOT by clamping once on the project-level
        aggregate. This correctly handles the case where one contract is
        overpaid and another is unpaid within the same project.
        """
        # 1. Fetch all contracts with their project association.
        rows = (
            self.db.query(SalesContract, Phase.project_id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .all()
        )

        if not rows:
            return []

        # 2. Group contracts by project.
        project_contracts: dict[str, list] = {}
        for contract, project_id in rows:
            pid = str(project_id)
            if pid not in project_contracts:
                project_contracts[pid] = []
            project_contracts[pid].append(contract)

        # 3. Bulk query paid installment sums (single grouped query).
        all_contract_ids = [c.id for c, _ in rows]
        paid_map = self._sum_paid_installments_bulk(all_contract_ids)

        # 4. Bulk query outstanding receivables per project (single grouped query).
        receivables_map = self._sum_outstanding_by_project()

        # 5. Bulk query project base_currency (single query).
        project_ids_list = list(project_contracts.keys())
        currency_map = {
            str(p.id): p.base_currency
            for p in self.db.query(Project).filter(
                Project.id.in_(project_ids_list)
            ).all()
        }

        # 6. Build per-project entries.
        entries: List[ProjectFinancialSummaryEntry] = []
        for project_id, contracts in sorted(project_contracts.items()):
            total_contract_value = round(
                sum(float(c.contract_price) for c in contracts), 2
            )

            # Sum per-contract clamped recognition so that an overpaid contract
            # cannot inflate the recognized total at the expense of an unpaid one.
            project_recognized = 0.0
            for contract in contracts:
                paid = paid_map.get(contract.id, 0.0)
                cdata = ContractRevenueData(
                    contract_id=contract.id,
                    contract_total=float(contract.contract_price),
                    paid_amount=paid,
                )
                crec = calculate_contract_revenue_recognition(cdata)
                project_recognized += crec.recognized_revenue

            recognized_revenue = round(project_recognized, 2)

            receivables_exposure = round(receivables_map.get(project_id, 0.0), 2)

            if total_contract_value > 0:
                collection_rate = round(
                    min(recognized_revenue / total_contract_value, 1.0),
                    6,
                )
            else:
                collection_rate = 0.0

            entries.append(
                ProjectFinancialSummaryEntry(
                    project_id=project_id,
                    recognized_revenue=recognized_revenue,
                    receivables_exposure=receivables_exposure,
                    collection_rate=collection_rate,
                    currency=currency_map.get(project_id, "AED"),
                )
            )

        return entries

    def _sum_paid_installments_bulk(self, contract_ids: list) -> dict:
        """Return mapping of contract_id → total paid amount (single query)."""
        if not contract_ids:
            return {}
        rows = (
            self.db.query(
                ContractPaymentSchedule.contract_id,
                func.sum(ContractPaymentSchedule.amount),
            )
            .filter(
                ContractPaymentSchedule.contract_id.in_(contract_ids),
                ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value,
            )
            .group_by(ContractPaymentSchedule.contract_id)
            .all()
        )
        return {str(cid): float(total) for cid, total in rows}

    def _sum_outstanding_by_project(self) -> dict:
        """Return mapping of project_id → total outstanding amount (single query).

        Anchored on ContractPaymentSchedule and joined forward through the
        contract → unit → floor → building → phase chain, mirroring the
        pattern used in CashflowForecastService._load_all_project_installments()
        and CollectionsAgingService to eliminate join ambiguity.
        """
        rows = (
            self.db.query(
                Phase.project_id,
                func.sum(ContractPaymentSchedule.amount),
            )
            .select_from(ContractPaymentSchedule)
            .join(
                SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(ContractPaymentSchedule.status.in_(RECEIVABLE_STATUSES))
            .group_by(Phase.project_id)
            .all()
        )
        return {str(pid): float(total) for pid, total in rows}
