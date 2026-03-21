"""
finance.project_financial_dashboard_service

Provides project-level financial dashboard aggregation.

Responsibilities:
  - Compose a full financial view for a single project using existing finance
    services and analytics fact tables.
  - Return project-level KPIs: recognized revenue, deferred revenue,
    receivables exposure, overdue receivables, overdue percentage,
    next-month forecast, and collection efficiency.
  - Return monthly revenue, collections, and receivables trends for the
    selected project filtered from the analytics fact tables.

All queries are read-only.  Operational finance engine logic is not modified.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.finance.cashflow_service import CashflowForecastService
from app.modules.finance.date_utils import next_month_key
from app.modules.finance.models import (
    FactCollections,
    FactReceivablesSnapshot,
    FactRevenue,
)
from app.modules.finance.schemas import (
    ProjectFinancialDashboardResponse,
    ProjectFinancialKPIResponse,
    ProjectFinancialTrendEntry,
)
from app.modules.finance.service import (
    CollectionsAgingService,
    RevenueRecognitionService,
)
from app.modules.projects.models import Project


class ProjectFinancialDashboardService:
    """Provides a complete financial dashboard view for a single project.

    Internally delegates to:
      - RevenueRecognitionService — recognized and deferred revenue
      - CollectionsAgingService   — receivables exposure and overdue breakdown
      - CashflowForecastService   — next-month projected cash inflow
      - Analytics fact tables     — monthly revenue, collections, and
                                     receivables trends; collection efficiency

    All operations are read-only.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._revenue_svc = RevenueRecognitionService(db)
        self._aging_svc = CollectionsAgingService(db)
        self._forecast_svc = CashflowForecastService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_project_financial_dashboard(
        self, project_id: str
    ) -> ProjectFinancialDashboardResponse:
        """Return the full financial dashboard payload for a single project.

        Raises HTTP 404 if the project does not exist.
        """
        # Validate project exists before doing any other work.
        self._require_project(project_id)

        return ProjectFinancialDashboardResponse(
            project_id=project_id,
            kpis=self.get_project_financial_kpis(project_id),
            revenue_trend=self.get_project_revenue_trend(project_id),
            collections_trend=self.get_project_collections_trend(project_id),
            receivables_trend=self.get_project_receivables_trend(project_id),
        )

    def get_project_financial_kpis(
        self, project_id: str
    ) -> ProjectFinancialKPIResponse:
        """Return top-level financial KPIs for a single project.

        Metrics:
          recognized_revenue    — SUM of recognized revenue from revenue engine
          deferred_revenue      — total_contract_value − recognized_revenue
          receivables_exposure  — total outstanding receivables from aging engine
          overdue_receivables   — sum of all non-current aging buckets
          overdue_percentage    — overdue_receivables / receivables_exposure × 100
          forecast_next_month   — next-calendar-month expected collections
          collection_efficiency — project fact_collections / fact_revenue (0 if no revenue)
        """
        # --- Revenue ---
        project_revenue = self._revenue_svc.get_project_revenue(project_id)
        recognized_revenue = round(project_revenue.total_recognized_revenue, 2)
        deferred_revenue = round(project_revenue.total_deferred_revenue, 2)

        # --- Receivables aging ---
        project_aging = self._aging_svc.get_project_aging(project_id)
        receivables_exposure = round(project_aging.total_outstanding, 2)

        overdue_receivables = round(
            sum(
                b.amount
                for b in project_aging.aging_buckets
                if b.bucket != "current"
            ),
            2,
        )

        if receivables_exposure > 0:
            overdue_percentage = round(
                min(overdue_receivables / receivables_exposure * 100, 100.0), 4
            )
        else:
            overdue_percentage = 0.0

        # --- Cashflow forecast — next calendar month ---
        project_forecast = self._forecast_svc.get_project_forecast(project_id)
        next_month = next_month_key()
        forecast_next_month = 0.0
        for entry in project_forecast.monthly_entries:
            if entry.month == next_month:
                forecast_next_month = entry.expected_collections
                break

        # --- Collection efficiency from fact tables ---
        project_total_revenue = float(
            self.db.query(func.sum(FactRevenue.recognized_revenue))
            .filter(FactRevenue.project_id == project_id)
            .scalar()
            or 0.0
        )
        project_total_collections = float(
            self.db.query(func.sum(FactCollections.amount))
            .filter(FactCollections.project_id == project_id)
            .scalar()
            or 0.0
        )
        collection_efficiency = (
            round(project_total_collections / project_total_revenue, 4)
            if project_total_revenue > 0
            else 0.0
        )

        return ProjectFinancialKPIResponse(
            recognized_revenue=recognized_revenue,
            deferred_revenue=deferred_revenue,
            receivables_exposure=receivables_exposure,
            overdue_receivables=overdue_receivables,
            overdue_percentage=overdue_percentage,
            forecast_next_month=forecast_next_month,
            collection_efficiency=collection_efficiency,
        )

    def get_project_revenue_trend(
        self, project_id: str
    ) -> list[ProjectFinancialTrendEntry]:
        """Return monthly recognized revenue trend for the selected project.

        Source: fact_revenue WHERE project_id = project_id

        Query:
            SELECT month, SUM(recognized_revenue)
            FROM fact_revenue
            WHERE project_id = :project_id
            GROUP BY month
            ORDER BY month
        """
        rows = (
            self.db.query(
                FactRevenue.month,
                func.sum(FactRevenue.recognized_revenue).label("total"),
            )
            .filter(FactRevenue.project_id == project_id)
            .group_by(FactRevenue.month)
            .order_by(FactRevenue.month)
            .all()
        )
        return [
            ProjectFinancialTrendEntry(
                period=month,
                value=round(float(total), 2),
            )
            for month, total in rows
        ]

    def get_project_collections_trend(
        self, project_id: str
    ) -> list[ProjectFinancialTrendEntry]:
        """Return monthly collections trend for the selected project.

        Source: fact_collections WHERE project_id = project_id

        Query:
            SELECT month, SUM(amount)
            FROM fact_collections
            WHERE project_id = :project_id
            GROUP BY month
            ORDER BY month
        """
        rows = (
            self.db.query(
                FactCollections.month,
                func.sum(FactCollections.amount).label("total"),
            )
            .filter(FactCollections.project_id == project_id)
            .group_by(FactCollections.month)
            .order_by(FactCollections.month)
            .all()
        )
        return [
            ProjectFinancialTrendEntry(
                period=month,
                value=round(float(total), 2),
            )
            for month, total in rows
        ]

    def get_project_receivables_trend(
        self, project_id: str
    ) -> list[ProjectFinancialTrendEntry]:
        """Return historical receivables trend for the selected project.

        Source: fact_receivables_snapshot WHERE project_id = project_id

        Query:
            SELECT snapshot_date, total_receivables
            FROM fact_receivables_snapshot
            WHERE project_id = :project_id
            ORDER BY snapshot_date
        """
        rows = (
            self.db.query(
                FactReceivablesSnapshot.snapshot_date,
                FactReceivablesSnapshot.total_receivables,
            )
            .filter(FactReceivablesSnapshot.project_id == project_id)
            .order_by(FactReceivablesSnapshot.snapshot_date)
            .all()
        )
        return [
            ProjectFinancialTrendEntry(
                period=str(snapshot_date),
                value=round(float(total_receivables), 2),
            )
            for snapshot_date, total_receivables in rows
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str) -> Project:
        """Raise HTTP 404 if the project does not exist in the database."""
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found.",
            )
        return project
