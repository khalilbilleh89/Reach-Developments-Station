"""
finance.treasury_monitoring_service

Aggregates liquidity and exposure metrics across the development portfolio
to provide a treasury-level monitoring snapshot.

Responsibilities:
  - Compute portfolio cash position from recognized revenue, grouped by currency.
  - Compute receivable exposure and overdue concentration, grouped by currency.
  - Rank projects by receivable exposure.
  - Extract next-calendar-month forecast inflow per project.
  - Derive the portfolio liquidity ratio (single-currency only).

All computation is read-only; no records are created or mutated.
This service delegates data-loading to the existing financial engines and
performs treasury-level aggregation on top of their outputs.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.finance.cashflow_service import CashflowForecastService
from app.modules.finance.date_utils import next_month_key
from app.modules.finance.schemas import (
    ProjectExposureEntry,
    TreasuryMonitoringResponse,
)
from app.modules.finance.service import (
    CollectionsAgingService,
    RevenueRecognitionService,
)


class TreasuryMonitoringService:
    """Produces a treasury-level monitoring snapshot for the entire portfolio.

    Internally delegates to:
      - RevenueRecognitionService  — recognized revenue (cash position proxy)
      - CollectionsAgingService    — total and overdue receivables
      - CashflowForecastService    — per-project next-month inflow forecast

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

    def get_treasury_monitoring(self) -> TreasuryMonitoringResponse:
        """Return the portfolio treasury monitoring snapshot.

        Aggregates data from the revenue recognition, receivables aging,
        and cashflow forecasting engines.  Monetary totals are grouped by
        currency so consumers receive denomination-safe payloads.

        ``liquidity_ratio`` is None when the portfolio spans more than one
        currency (the ratio is mathematically invalid across currencies).
        """
        # --- Cash position: total paid installments grouped by contract currency ---
        # Uses _get_cash_position_grouped() which queries paid installment sums
        # directly from ContractPaymentSchedule, grouped by SalesContract.currency.
        revenue_overview = self._revenue_svc.get_total_recognized_revenue()
        aging_overview = self._aging_svc.get_portfolio_aging()

        # Determine all currencies present in the portfolio
        currencies_set = set(revenue_overview.currencies) | set(aging_overview.currencies)
        all_currencies = sorted(currencies_set)

        # Build minimal cash_position dict
        if len(all_currencies) == 1:
            cash_position_grouped: Dict[str, float] = {
                all_currencies[0]: round(revenue_overview.total_recognized_revenue, 2)
            }
        elif len(all_currencies) > 1:
            # Multi-currency: distribute evenly is wrong — use AED default
            # Actual grouping requires querying recognized revenue per currency.
            # We use a helper from the portfolio summary service approach.
            cash_position_grouped = self._get_cash_position_grouped()
        else:
            cash_position_grouped = {}

        # --- Receivables aging grouped by currency ---
        receivables_grouped = self._get_receivables_grouped()
        overdue_grouped = self._get_overdue_grouped()

        # Refresh all_currencies after getting receivables
        all_currencies = sorted(
            set(cash_position_grouped.keys())
            | set(receivables_grouped.keys())
            | set(overdue_grouped.keys())
        )

        # --- Liquidity ratio: only valid for single-currency portfolio ---
        total_cash = sum(cash_position_grouped.values())
        total_receivables = sum(receivables_grouped.values())
        total_base = total_cash + total_receivables
        if len(all_currencies) <= 1 and total_base > 0:
            liquidity_ratio: Optional[float] = round(
                min(total_cash / total_base, 1.0), 6
            )
        elif len(all_currencies) <= 1:
            liquidity_ratio = 0.0
        else:
            # Multi-currency: ratio is mathematically invalid
            liquidity_ratio = None

        # --- Cashflow forecast — next calendar month grouped by currency ---
        cashflow = self._forecast_svc.get_portfolio_forecast()
        next_month = next_month_key()
        forecast_grouped: Dict[str, float] = {}
        for pf in cashflow.project_forecasts:
            project_currency = pf.currency
            for entry in pf.monthly_entries:
                if entry.month == next_month:
                    forecast_grouped[project_currency] = (
                        forecast_grouped.get(project_currency, 0.0) + entry.expected_collections
                    )
                    break

        # --- Per-project exposure entries ---
        portfolio_receivables = round(total_receivables, 2)
        project_exposures = self._build_project_exposures(
            cashflow, next_month, portfolio_receivables
        )

        return TreasuryMonitoringResponse(
            cash_position=cash_position_grouped,
            receivables_exposure=receivables_grouped,
            overdue_receivables=overdue_grouped,
            liquidity_ratio=liquidity_ratio,
            forecast_next_month=forecast_grouped,
            project_count=revenue_overview.project_count,
            project_exposures=project_exposures,
            currencies=all_currencies,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_cash_position_grouped(self) -> Dict[str, float]:
        """Return recognized revenue (cash position proxy) grouped by contract currency.

        Computes: for each currency, sum the paid installment amounts on all
        contracts denominated in that currency (same logic as recognized revenue
        but grouped by currency).
        """
        from sqlalchemy import func as _func
        from app.modules.sales.models import ContractPaymentSchedule, SalesContract
        from app.modules.units.models import Unit
        from app.modules.floors.models import Floor
        from app.modules.buildings.models import Building
        from app.modules.phases.models import Phase
        from app.shared.enums.sales import ContractPaymentStatus

        rows = (
            self.db.query(
                SalesContract.currency,
                _func.coalesce(_func.sum(ContractPaymentSchedule.amount), 0),
            )
            .join(
                ContractPaymentSchedule,
                ContractPaymentSchedule.contract_id == SalesContract.id,
            )
            .filter(ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value)
            .group_by(SalesContract.currency)
            .all()
        )
        return {currency: round(float(total), 2) for currency, total in rows}

    def _get_receivables_grouped(self) -> Dict[str, float]:
        """Return total outstanding receivables grouped by installment currency."""
        from sqlalchemy import func as _func
        from app.modules.finance.constants import RECEIVABLE_STATUSES
        from app.modules.sales.models import ContractPaymentSchedule, SalesContract
        from app.modules.units.models import Unit
        from app.modules.floors.models import Floor
        from app.modules.buildings.models import Building
        from app.modules.phases.models import Phase

        rows = (
            self.db.query(
                ContractPaymentSchedule.currency,
                _func.sum(ContractPaymentSchedule.amount),
            )
            .join(
                SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id
            )
            .filter(ContractPaymentSchedule.status.in_(RECEIVABLE_STATUSES))
            .group_by(ContractPaymentSchedule.currency)
            .all()
        )
        return {
            currency: round(float(total), 2)
            for currency, total in rows
            if total is not None
        }

    def _get_overdue_grouped(self) -> Dict[str, float]:
        """Return overdue receivables grouped by installment currency."""
        from datetime import date as _date
        from sqlalchemy import func as _func
        from app.modules.finance.constants import RECEIVABLE_STATUSES
        from app.modules.sales.models import ContractPaymentSchedule, SalesContract

        today = _date.today()
        rows = (
            self.db.query(
                ContractPaymentSchedule.currency,
                _func.sum(ContractPaymentSchedule.amount),
            )
            .join(
                SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id
            )
            .filter(
                ContractPaymentSchedule.status.in_(RECEIVABLE_STATUSES),
                ContractPaymentSchedule.due_date < today,
            )
            .group_by(ContractPaymentSchedule.currency)
            .all()
        )
        return {
            currency: round(float(total), 2)
            for currency, total in rows
            if total is not None
        }

    def _build_project_exposures(
        self,
        cashflow,
        next_month: str,
        total_receivables_exposure: float,
    ) -> List[ProjectExposureEntry]:
        """Return per-project exposure entries sorted by receivable exposure descending.

        Uses the project-level cashflow forecast (already computed) to derive
        per-project forecast inflows, and re-uses the aging service for
        per-project receivable exposure totals.
        """
        # Build a mapping of project_id → next-month forecast inflow
        project_inflow: dict[str, float] = {}
        for pf in cashflow.project_forecasts:
            inflow = 0.0
            for entry in pf.monthly_entries:
                if entry.month == next_month:
                    inflow = entry.expected_collections
                    break
            project_inflow[pf.project_id] = inflow

        if not project_inflow and total_receivables_exposure == 0.0:
            return []

        # Derive per-project receivable exposure via the aging service
        # (it already queries the same outstanding-installment dataset).
        project_receivables = self._aging_svc.get_project_receivables_map()

        # Union of all project ids seen in either exposure or forecast maps.
        all_project_ids = set(project_receivables.keys()) | set(project_inflow.keys())

        if not all_project_ids:
            return []

        entries: List[ProjectExposureEntry] = []
        for project_id in all_project_ids:
            exposure = round(project_receivables.get(project_id, 0.0), 2)
            if total_receivables_exposure > 0:
                exposure_pct = round(
                    min(exposure / total_receivables_exposure * 100, 100.0),
                    4,
                )
            else:
                exposure_pct = 0.0
            entries.append(
                ProjectExposureEntry(
                    project_id=project_id,
                    receivable_exposure=exposure,
                    exposure_percentage=exposure_pct,
                    forecast_inflow=round(project_inflow.get(project_id, 0.0), 2),
                )
            )

        # Sort by receivable exposure descending (highest risk first).
        entries.sort(key=lambda e: e.receivable_exposure, reverse=True)
        return entries
