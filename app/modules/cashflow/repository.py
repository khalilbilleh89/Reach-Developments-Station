"""
cashflow.repository

Pure database-access layer for the Cashflow Forecasting domain.

Responsibilities
----------------
* CRUD and list queries for CashflowForecast and CashflowForecastPeriod.
* SQL-level aggregations for actual collections and scheduled receivables
  scoped to a project and date range.

Design contract
---------------
* No business forecasting rules here — all logic lives in service.py.
* Does NOT mutate payment plans, collections, finance summaries, or sales
  contracts.
"""

from datetime import date
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.cashflow.models import CashflowForecast, CashflowForecastPeriod
from app.modules.collections.models import PaymentReceipt
from app.modules.payment_plans.models import PaymentSchedule
from app.modules.sales.models import SalesContract
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.finance import ReceiptStatus


class CashflowRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # CashflowForecast
    # ------------------------------------------------------------------

    def create_forecast(self, forecast: CashflowForecast) -> CashflowForecast:
        self.db.add(forecast)
        self.db.commit()
        self.db.refresh(forecast)
        return forecast

    def save_forecast(self, forecast: CashflowForecast) -> CashflowForecast:
        self.db.commit()
        self.db.refresh(forecast)
        return forecast

    def get_forecast_by_id(self, forecast_id: str) -> Optional[CashflowForecast]:
        return (
            self.db.query(CashflowForecast)
            .filter(CashflowForecast.id == forecast_id)
            .first()
        )

    def list_forecasts_by_project(
        self, project_id: str, skip: int = 0, limit: int = 100
    ) -> List[CashflowForecast]:
        return (
            self.db.query(CashflowForecast)
            .filter(CashflowForecast.project_id == project_id)
            .order_by(CashflowForecast.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_forecasts_by_project(self, project_id: str) -> int:
        return (
            self.db.query(CashflowForecast)
            .filter(CashflowForecast.project_id == project_id)
            .count()
        )

    def get_latest_forecast_by_project(
        self, project_id: str
    ) -> Optional[CashflowForecast]:
        return (
            self.db.query(CashflowForecast)
            .filter(CashflowForecast.project_id == project_id)
            .order_by(CashflowForecast.created_at.desc())
            .first()
        )

    # ------------------------------------------------------------------
    # CashflowForecastPeriod
    # ------------------------------------------------------------------

    def create_period_rows(
        self, periods: List[CashflowForecastPeriod]
    ) -> List[CashflowForecastPeriod]:
        for period in periods:
            self.db.add(period)
        self.db.commit()
        for period in periods:
            self.db.refresh(period)
        return periods

    def list_periods_by_forecast(
        self, forecast_id: str
    ) -> List[CashflowForecastPeriod]:
        return (
            self.db.query(CashflowForecastPeriod)
            .filter(CashflowForecastPeriod.cashflow_forecast_id == forecast_id)
            .order_by(CashflowForecastPeriod.sequence.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # Aggregations — actual collections by period
    # ------------------------------------------------------------------

    def sum_actual_collections_by_period(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
    ) -> float:
        """Return total recorded receipts for a project within [period_start, period_end).

        Joins through the contract → unit → floor → building → phase → project
        hierarchy and filters by receipt_date within the period window.
        """
        result = (
            self.db.query(
                func.coalesce(func.sum(PaymentReceipt.amount_received), 0)
            )
            .join(SalesContract, PaymentReceipt.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                PaymentReceipt.status == ReceiptStatus.RECORDED.value,
                PaymentReceipt.receipt_date >= period_start,
                PaymentReceipt.receipt_date < period_end,
            )
            .scalar()
        )
        return float(result)

    # ------------------------------------------------------------------
    # Aggregations — scheduled receivables by period
    # ------------------------------------------------------------------

    def sum_scheduled_receivables_by_period(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
    ) -> float:
        """Return total scheduled due amounts for a project within [period_start, period_end).

        Joins through payment_schedule → contract → unit → … → project hierarchy
        and filters by due_date within the period window.
        """
        result = (
            self.db.query(
                func.coalesce(func.sum(PaymentSchedule.due_amount), 0)
            )
            .join(SalesContract, PaymentSchedule.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                PaymentSchedule.due_date >= period_start,
                PaymentSchedule.due_date < period_end,
            )
            .scalar()
        )
        return float(result)

    def sum_overdue_receivables(
        self,
        project_id: str,
        as_of_date: date,
    ) -> float:
        """Return total scheduled due amounts that are past due (due_date < as_of_date)
        and have not been fully collected.

        For simplicity, this sums all scheduled amounts due before as_of_date
        and subtracts recorded receipts up to as_of_date.
        """
        scheduled = (
            self.db.query(
                func.coalesce(func.sum(PaymentSchedule.due_amount), 0)
            )
            .join(SalesContract, PaymentSchedule.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                PaymentSchedule.due_date < as_of_date,
            )
            .scalar()
        )
        collected = (
            self.db.query(
                func.coalesce(func.sum(PaymentReceipt.amount_received), 0)
            )
            .join(SalesContract, PaymentReceipt.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                PaymentReceipt.status == ReceiptStatus.RECORDED.value,
                PaymentReceipt.receipt_date < as_of_date,
            )
            .scalar()
        )
        overdue = float(scheduled) - float(collected)
        return max(overdue, 0.0)
