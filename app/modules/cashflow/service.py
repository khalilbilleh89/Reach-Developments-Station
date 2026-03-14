"""
cashflow.service

Application-layer orchestration for the Cashflow Forecasting domain.

Core rules
----------
1. Project must exist before a forecast can be created.
2. Forecast window (start_date, end_date) must be valid (end > start).
3. Period buckets are generated deterministically from the window and
   period_type — the same assumptions always produce the same buckets.
4. forecast_basis controls how expected_inflows are computed per period:

   scheduled_collections
       expected_inflows = scheduled due amounts in the period.

   actual_plus_scheduled
       For periods that end on or before today (realized):
           actual_inflows = actual receipts in that period.
           expected_inflows = scheduled due amounts in that period.
       For future periods:
           actual_inflows = 0.
           expected_inflows = scheduled due amounts in that period.

   blended
       expected_inflows = scheduled_due * collection_factor.
       actual_inflows from receipts (same as actual_plus_scheduled).

5. Per-period calculation:
       net_cashflow    = (actual_inflows or expected_inflows) - expected_outflows
       closing_balance = opening_balance + net_cashflow

6. Saved forecasts are reproducible from their assumptions_json.

Explicitly Forbidden
--------------------
* Does NOT alter payment plan schedules.
* Does NOT write to collections (PaymentReceipt).
* Does NOT write to finance summaries.
* Does NOT implement full GL/ERP accounting.
* Does NOT implement NPV/IRR recalculation.
"""

import json
from datetime import date, datetime, timezone
from typing import List, Optional

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.cashflow.models import CashflowForecast, CashflowForecastPeriod
from app.modules.cashflow.repository import CashflowRepository
from app.modules.cashflow.schemas import (
    CashflowForecastCreate,
    CashflowForecastListResponse,
    CashflowForecastPeriodResponse,
    CashflowForecastResponse,
    CashflowForecastSummaryResponse,
)
from app.modules.projects.models import Project
from app.shared.enums.cashflow import (
    CashflowForecastBasis,
    CashflowForecastStatus,
    CashflowPeriodType,
)


class CashflowService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CashflowRepository(db)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str) -> Project:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return project

    def _require_forecast(self, forecast_id: str) -> CashflowForecast:
        forecast = self.repo.get_forecast_by_id(forecast_id)
        if forecast is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CashflowForecast '{forecast_id}' not found.",
            )
        return forecast

    @staticmethod
    def _generate_period_buckets(
        start_date: date,
        end_date: date,
        period_type: CashflowPeriodType,
    ) -> List[tuple[date, date]]:
        """Return list of (period_start, period_end) tuples covering [start_date, end_date)."""
        buckets: List[tuple[date, date]] = []
        current = start_date
        while current < end_date:
            if period_type == CashflowPeriodType.MONTHLY:
                next_period = current + relativedelta(months=1)
            else:
                # quarterly
                next_period = current + relativedelta(months=3)
            bucket_end = min(next_period, end_date)
            buckets.append((current, bucket_end))
            current = next_period
            if current >= end_date:
                break
        return buckets

    # ------------------------------------------------------------------
    # Create forecast
    # ------------------------------------------------------------------

    def create_forecast(self, data: CashflowForecastCreate) -> CashflowForecastResponse:
        """Generate a new cashflow forecast for a project.

        Steps:
        1. Validate project exists.
        2. Build period buckets from window and period_type.
        3. For each bucket, query DB for actual collections + scheduled due amounts.
        4. Compute expected_inflows per basis mode.
        5. Apply optional outflow schedule.
        6. Accumulate opening/closing balances.
        7. Persist forecast + period rows.
        """
        self._require_project(data.project_id)

        today = date.today()
        outflow_schedule = data.expected_outflows_schedule or {}

        # Build period buckets
        buckets = self._generate_period_buckets(
            data.start_date, data.end_date, data.period_type
        )

        if not buckets:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Forecast window produces no periods. Check start_date and end_date.",
            )

        # Persist the forecast header first so we have a FK for period rows
        assumptions = {
            "forecast_basis": data.forecast_basis.value,
            "period_type": data.period_type.value,
            "opening_balance": data.opening_balance,
            "collection_factor": data.collection_factor,
            "expected_outflows_schedule": outflow_schedule,
        }

        forecast = CashflowForecast(
            project_id=data.project_id,
            forecast_name=data.forecast_name,
            forecast_basis=data.forecast_basis.value,
            start_date=data.start_date,
            end_date=data.end_date,
            period_type=data.period_type.value,
            status=CashflowForecastStatus.GENERATED.value,
            opening_balance=data.opening_balance,
            collection_factor=data.collection_factor,
            assumptions_json=json.dumps(assumptions),
            generated_at=datetime.now(timezone.utc),
            generated_by=data.generated_by,
            notes=data.notes,
        )
        forecast = self.repo.create_forecast(forecast)

        # Generate period rows
        period_rows: List[CashflowForecastPeriod] = []
        running_balance = data.opening_balance

        for seq, (p_start, p_end) in enumerate(buckets, start=1):
            # Actual inflows: recorded receipts in this period
            actual_inflows = self.repo.sum_actual_collections_by_period(
                data.project_id, p_start, p_end
            )

            # Scheduled due amounts in this period
            scheduled_due = self.repo.sum_scheduled_receivables_by_period(
                data.project_id, p_start, p_end
            )

            # Expected inflows depend on forecast basis
            if data.forecast_basis == CashflowForecastBasis.SCHEDULED_COLLECTIONS:
                expected_inflows = scheduled_due
                actual_inflows = 0.0

            elif data.forecast_basis == CashflowForecastBasis.ACTUAL_PLUS_SCHEDULED:
                # Use actual if period is in the past, scheduled for future
                expected_inflows = scheduled_due

            elif data.forecast_basis == CashflowForecastBasis.BLENDED:
                factor = data.collection_factor or 1.0
                expected_inflows = scheduled_due * factor
                # actual_inflows already queried

            else:
                expected_inflows = scheduled_due

            # Outflows: look up in schedule by period_start ISO string
            expected_outflows = float(
                outflow_schedule.get(p_start.isoformat(), 0.0)
            )

            # Receivables due in this period = scheduled due amounts
            receivables_due = scheduled_due

            # Overdue receivables: accumulated at period_start
            receivables_overdue = self.repo.sum_overdue_receivables(
                data.project_id, p_start
            )

            # Effective inflow used for the balance calculation:
            #   scheduled_collections — use expected (no actuals)
            #   actual_plus_scheduled — use actuals for realized periods,
            #                           expected for future periods
            #   blended               — use actuals where available, else expected
            if data.forecast_basis == CashflowForecastBasis.SCHEDULED_COLLECTIONS:
                effective_inflow = expected_inflows
            elif data.forecast_basis == CashflowForecastBasis.ACTUAL_PLUS_SCHEDULED:
                effective_inflow = actual_inflows if p_end <= today else expected_inflows
            else:
                # blended: prefer actuals when they exist, otherwise use scaled expected
                effective_inflow = actual_inflows if actual_inflows > 0 else expected_inflows
            net_cashflow = effective_inflow - expected_outflows
            closing_balance = running_balance + net_cashflow

            period_rows.append(
                CashflowForecastPeriod(
                    cashflow_forecast_id=forecast.id,
                    sequence=seq,
                    period_start=p_start,
                    period_end=p_end,
                    opening_balance=running_balance,
                    expected_inflows=expected_inflows,
                    actual_inflows=actual_inflows,
                    expected_outflows=expected_outflows,
                    net_cashflow=net_cashflow,
                    closing_balance=closing_balance,
                    receivables_due=receivables_due,
                    receivables_overdue=receivables_overdue,
                )
            )

            running_balance = closing_balance

        self.repo.create_period_rows(period_rows)

        return CashflowForecastResponse.model_validate(forecast)

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    def get_forecast(self, forecast_id: str) -> CashflowForecastResponse:
        forecast = self._require_forecast(forecast_id)
        return CashflowForecastResponse.model_validate(forecast)

    def list_forecasts_by_project(
        self, project_id: str, skip: int = 0, limit: int = 100
    ) -> CashflowForecastListResponse:
        self._require_project(project_id)
        items = self.repo.list_forecasts_by_project(project_id, skip=skip, limit=limit)
        total = self.repo.count_forecasts_by_project(project_id)
        return CashflowForecastListResponse(
            total=total,
            items=[CashflowForecastResponse.model_validate(f) for f in items],
        )

    def list_forecast_periods(
        self, forecast_id: str
    ) -> List[CashflowForecastPeriodResponse]:
        self._require_forecast(forecast_id)
        periods = self.repo.list_periods_by_forecast(forecast_id)
        return [CashflowForecastPeriodResponse.model_validate(p) for p in periods]

    # ------------------------------------------------------------------
    # Project-level summary
    # ------------------------------------------------------------------

    def get_project_cashflow_summary(
        self, project_id: str
    ) -> CashflowForecastSummaryResponse:
        self._require_project(project_id)
        total = self.repo.count_forecasts_by_project(project_id)
        latest = self.repo.get_latest_forecast_by_project(project_id)

        if latest is None:
            return CashflowForecastSummaryResponse(
                project_id=project_id,
                total_forecasts=total,
                latest_forecast_id=None,
                latest_forecast_name=None,
                latest_generated_at=None,
                total_expected_inflows=0.0,
                total_actual_inflows=0.0,
                total_expected_outflows=0.0,
                total_net_cashflow=0.0,
                closing_balance=0.0,
            )

        # Aggregate latest forecast periods
        periods = self.repo.list_periods_by_forecast(latest.id)
        total_expected_inflows = sum(float(p.expected_inflows) for p in periods)
        total_actual_inflows = sum(float(p.actual_inflows) for p in periods)
        total_expected_outflows = sum(float(p.expected_outflows) for p in periods)
        total_net_cashflow = sum(float(p.net_cashflow) for p in periods)
        closing_balance = float(periods[-1].closing_balance) if periods else 0.0

        return CashflowForecastSummaryResponse(
            project_id=project_id,
            total_forecasts=total,
            latest_forecast_id=latest.id,
            latest_forecast_name=latest.forecast_name,
            latest_generated_at=latest.generated_at,
            total_expected_inflows=total_expected_inflows,
            total_actual_inflows=total_actual_inflows,
            total_expected_outflows=total_expected_outflows,
            total_net_cashflow=total_net_cashflow,
            closing_balance=closing_balance,
        )
