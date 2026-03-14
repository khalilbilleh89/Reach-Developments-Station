"""
cashflow.repository

Pure database-access layer for the Cashflow Forecasting domain.

Responsibilities
----------------
* CRUD and list queries for CashflowForecast and CashflowForecastPeriod.
* SQL-level aggregations for actual collections and scheduled receivables
  scoped to a project and date range.

Transaction design
------------------
* `stage_forecast()` — adds forecast to session and flushes to obtain its ID,
  but does NOT commit.  The service controls the transaction boundary.
* `stage_period_rows()` — bulk-adds period rows to the session, does NOT commit.
* `commit()` — commits the current transaction.  Called once by the service
  after both header and period rows are staged, making creation atomic.
* `rollback()` — rolls back the current transaction on failure.

Aggregation design
------------------
* `get_actual_collections_by_date()` and `get_scheduled_amounts_by_date()` each
  execute a single GROUP-BY query over the full forecast window and return a
  date → amount dict.  The service maps these into period buckets in memory,
  replacing N×2 per-bucket scalar queries with 2 queries total.
* `sum_scheduled_amounts_before()` / `sum_collected_amounts_before()` supply the
  historical totals needed to seed the running overdue calculation.

Design contract
---------------
* No business forecasting rules here — all logic lives in service.py.
* Does NOT mutate payment plans, collections, finance summaries, or sales
  contracts.
"""

from datetime import date
from typing import Dict, List, Optional

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
    # Transaction control
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """Commit the current transaction."""
        self.db.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self.db.rollback()

    # ------------------------------------------------------------------
    # CashflowForecast
    # ------------------------------------------------------------------

    def stage_forecast(self, forecast: CashflowForecast) -> CashflowForecast:
        """Add forecast to session and flush to obtain a DB-assigned ID.

        Does NOT commit — the service controls the transaction boundary so
        that both the forecast header and its period rows are committed
        atomically in a single transaction.
        """
        self.db.add(forecast)
        self.db.flush()
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

    def stage_period_rows(self, periods: List[CashflowForecastPeriod]) -> None:
        """Bulk-add all period rows to the session.

        Does NOT commit — the service calls commit() once after both the
        forecast header and period rows are staged.
        """
        self.db.add_all(periods)

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
    # Bulk aggregations — actual collections for full window
    # ------------------------------------------------------------------

    def get_actual_collections_by_date(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
    ) -> Dict[date, float]:
        """Return {receipt_date: total_received} for recorded receipts in [start_date, end_date).

        Single GROUP-BY query over the full window.  The caller maps results
        into period buckets in Python, avoiding per-bucket scalar queries.
        """
        rows = (
            self.db.query(
                PaymentReceipt.receipt_date,
                func.sum(PaymentReceipt.amount_received),
            )
            .join(SalesContract, PaymentReceipt.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                PaymentReceipt.status == ReceiptStatus.RECORDED.value,
                PaymentReceipt.receipt_date >= start_date,
                PaymentReceipt.receipt_date < end_date,
            )
            .group_by(PaymentReceipt.receipt_date)
            .all()
        )
        return {row[0]: float(row[1]) for row in rows}

    # ------------------------------------------------------------------
    # Bulk aggregations — scheduled receivables for full window
    # ------------------------------------------------------------------

    def get_scheduled_amounts_by_date(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
    ) -> Dict[date, float]:
        """Return {due_date: total_due} for scheduled installments in [start_date, end_date).

        Single GROUP-BY query over the full window.  The caller maps results
        into period buckets in Python, avoiding per-bucket scalar queries.
        """
        rows = (
            self.db.query(
                PaymentSchedule.due_date,
                func.sum(PaymentSchedule.due_amount),
            )
            .join(SalesContract, PaymentSchedule.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                PaymentSchedule.due_date >= start_date,
                PaymentSchedule.due_date < end_date,
            )
            .group_by(PaymentSchedule.due_date)
            .all()
        )
        return {row[0]: float(row[1]) for row in rows}

    # ------------------------------------------------------------------
    # Historical totals — seed for running overdue calculation
    # ------------------------------------------------------------------

    def sum_scheduled_amounts_before(
        self, project_id: str, as_of_date: date
    ) -> float:
        """Return total scheduled due amounts with due_date < as_of_date."""
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
                PaymentSchedule.due_date < as_of_date,
            )
            .scalar()
        )
        return float(result)

    def sum_collected_amounts_before(
        self, project_id: str, as_of_date: date
    ) -> float:
        """Return total recorded receipts with receipt_date < as_of_date."""
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
                PaymentReceipt.receipt_date < as_of_date,
            )
            .scalar()
        )
        return float(result)

