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

from datetime import date
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.finance.cashflow_service import CashflowForecastService
from app.modules.finance.constants import RECEIVABLE_STATUSES
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
from app.modules.sales.models import ContractPaymentSchedule, SalesContract
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.sales import ContractPaymentStatus


def _next_month_key() -> str:
    """Return the YYYY-MM key for the calendar month after today."""
    today = date.today()
    if today.month == 12:
        return f"{today.year + 1:04d}-01"
    return f"{today.year:04d}-{today.month + 1:02d}"


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
        and cashflow forecasting engines.  All derived values are clamped
        and rounded to prevent invalid schema states.
        """
        # --- Revenue ---
        revenue_overview = self._revenue_svc.get_total_recognized_revenue()

        # --- Receivables aging ---
        aging_overview = self._aging_svc.get_portfolio_aging()

        overdue_amount = round(
            sum(
                b.amount for b in aging_overview.aging_buckets if b.bucket != "current"
            ),
            2,
        )
        if aging_overview.total_outstanding > 0:
            overdue_pct = round(
                min(overdue_amount / aging_overview.total_outstanding * 100, 100.0),
                4,
            )
        else:
            overdue_pct = 0.0

        # --- Cashflow forecast — next calendar month ---
        cashflow = self._forecast_svc.get_portfolio_forecast()
        next_month = _next_month_key()
        forecast_next_month = 0.0
        for entry in cashflow.monthly_entries:
            if entry.month == next_month:
                forecast_next_month = entry.expected_collections
                break

        # --- Per-project breakdown ---
        project_summaries = self._build_project_summaries()

        return PortfolioFinancialSummaryResponse(
            total_revenue_recognized=revenue_overview.total_recognized_revenue,
            total_deferred_revenue=revenue_overview.total_deferred_revenue,
            total_receivables=aging_overview.total_outstanding,
            overdue_receivables=overdue_amount,
            overdue_receivables_pct=overdue_pct,
            forecast_next_month=forecast_next_month,
            project_count=revenue_overview.project_count,
            project_summaries=project_summaries,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

        # 5. Build per-project entries.
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
