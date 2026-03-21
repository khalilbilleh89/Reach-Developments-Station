"""
finance.treasury_monitoring_service

Aggregates liquidity and exposure metrics across the development portfolio
to provide a treasury-level monitoring snapshot.

Responsibilities:
  - Compute portfolio cash position from recognized revenue.
  - Compute receivable exposure and overdue concentration.
  - Rank projects by receivable exposure.
  - Extract next-calendar-month forecast inflow per project.
  - Derive the portfolio liquidity ratio.

All computation is read-only; no records are created or mutated.
This service delegates data-loading to the existing financial engines and
performs treasury-level aggregation on top of their outputs.
"""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.modules.finance.cashflow_service import CashflowForecastService
from app.modules.finance.portfolio_summary_service import _next_month_key
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
        and cashflow forecasting engines.  All derived values are clamped
        and rounded to prevent invalid schema states.
        """
        # --- Cash position: total recognized revenue across the portfolio ---
        revenue_overview = self._revenue_svc.get_total_recognized_revenue()
        cash_position = round(revenue_overview.total_recognized_revenue, 2)

        # --- Receivables aging ---
        aging_overview = self._aging_svc.get_portfolio_aging()
        receivables_exposure = round(aging_overview.total_outstanding, 2)

        overdue_receivables = round(
            sum(
                b.amount for b in aging_overview.aging_buckets if b.bucket != "current"
            ),
            2,
        )

        # --- Liquidity ratio: collected fraction of total expected cash ---
        total_base = cash_position + receivables_exposure
        if total_base > 0:
            liquidity_ratio = round(
                min(cash_position / total_base, 1.0),
                6,
            )
        else:
            liquidity_ratio = 0.0

        # --- Cashflow forecast — next calendar month ---
        cashflow = self._forecast_svc.get_portfolio_forecast()
        next_month = _next_month_key()
        forecast_next_month = 0.0
        for entry in cashflow.monthly_entries:
            if entry.month == next_month:
                forecast_next_month = entry.expected_collections
                break

        # --- Per-project exposure entries ---
        project_exposures = self._build_project_exposures(
            cashflow, next_month, receivables_exposure
        )

        return TreasuryMonitoringResponse(
            cash_position=cash_position,
            receivables_exposure=receivables_exposure,
            overdue_receivables=overdue_receivables,
            liquidity_ratio=liquidity_ratio,
            forecast_next_month=forecast_next_month,
            project_count=revenue_overview.project_count,
            project_exposures=project_exposures,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
