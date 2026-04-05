"""
finance.analytics_dashboard_service

Provides read-only analytics queries from the analytics fact tables.

Responsibilities:
  - Query fact_revenue for monthly revenue trends.
  - Query fact_collections for monthly collections trends.
  - Query fact_receivables_snapshot for receivable exposure trends.
  - Derive portfolio-level KPIs from fact table aggregates.

All queries are read-only and target the three analytics fact tables
introduced in PR-23.  Operational tables are never accessed by this service.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.finance.models import (
    FactCollections,
    FactReceivablesSnapshot,
    FactRevenue,
)
from app.modules.finance.schemas import (
    CollectionsTrendEntry,
    PortfolioAnalyticsResponse,
    PortfolioKPI,
    ReceivablesTrendEntry,
    RevenueTrendEntry,
)


class AnalyticsDashboardService:
    """Provides read-only analytics queries from the analytics fact tables.

    All methods query the three analytics fact tables:
      - fact_revenue              — monthly recognized revenue per project / unit.
      - fact_collections          — payments received by project / month.
      - fact_receivables_snapshot — point-in-time receivable aging snapshots.

    No operational tables are accessed; no writes are performed.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_portfolio_analytics(self) -> PortfolioAnalyticsResponse:
        """Return the full portfolio analytics response.

        Aggregates revenue trends, collections trends, receivable trends,
        and top-level portfolio KPIs from the analytics fact tables.
        """
        return PortfolioAnalyticsResponse(
            revenue_trend=self.get_revenue_trend(),
            collections_trend=self.get_collections_trend(),
            receivables_trend=self.get_receivables_trend(),
            kpis=self.get_portfolio_kpis(),
        )

    def get_revenue_trend(self) -> list[RevenueTrendEntry]:
        """Return monthly recognized revenue totals per currency, ordered by month.

        Query:
            SELECT month, currency, SUM(recognized_revenue)
            FROM fact_revenue
            GROUP BY month, currency
            ORDER BY month, currency
        """
        rows = (
            self.db.query(
                FactRevenue.month,
                FactRevenue.currency,
                func.sum(FactRevenue.recognized_revenue).label("total"),
            )
            .group_by(FactRevenue.month, FactRevenue.currency)
            .order_by(FactRevenue.month, FactRevenue.currency)
            .all()
        )
        return [
            RevenueTrendEntry(
                month=month,
                currency=currency,
                total_recognized_revenue=round(float(total), 2),
            )
            for month, currency, total in rows
        ]

    def get_collections_trend(self) -> list[CollectionsTrendEntry]:
        """Return monthly collections totals per currency, ordered by month.

        Query:
            SELECT month, currency, SUM(amount)
            FROM fact_collections
            GROUP BY month, currency
            ORDER BY month, currency
        """
        rows = (
            self.db.query(
                FactCollections.month,
                FactCollections.currency,
                func.sum(FactCollections.amount).label("total"),
            )
            .group_by(FactCollections.month, FactCollections.currency)
            .order_by(FactCollections.month, FactCollections.currency)
            .all()
        )
        return [
            CollectionsTrendEntry(
                month=month,
                currency=currency,
                total_amount=round(float(total), 2),
            )
            for month, currency, total in rows
        ]

    def get_receivables_trend(self) -> list[ReceivablesTrendEntry]:
        """Return receivable totals per currency grouped by snapshot date, ordered by date.

        Query:
            SELECT snapshot_date, currency, SUM(total_receivables)
            FROM fact_receivables_snapshot
            GROUP BY snapshot_date, currency
            ORDER BY snapshot_date, currency
        """
        rows = (
            self.db.query(
                FactReceivablesSnapshot.snapshot_date,
                FactReceivablesSnapshot.currency,
                func.sum(FactReceivablesSnapshot.total_receivables).label("total"),
            )
            .group_by(FactReceivablesSnapshot.snapshot_date, FactReceivablesSnapshot.currency)
            .order_by(FactReceivablesSnapshot.snapshot_date, FactReceivablesSnapshot.currency)
            .all()
        )
        return [
            ReceivablesTrendEntry(
                snapshot_date=str(snapshot_date),
                currency=currency,
                total_receivables=round(float(total), 2),
            )
            for snapshot_date, currency, total in rows
        ]

    def get_portfolio_kpis(self) -> PortfolioKPI:
        """Return top-level portfolio KPIs derived from the analytics fact tables.

        Metrics:
          - total_revenue     — SUM(fact_revenue.recognized_revenue)
          - total_collections — SUM(fact_collections.amount)
          - total_receivables — SUM of the latest fact_receivables_snapshot rows
          - collection_efficiency — total_collections / total_revenue when the
                                    portfolio is single-currency; None when
                                    multiple currencies are present (the ratio
                                    is mathematically invalid across currencies)
          - currencies        — distinct ISO 4217 codes found in analytics facts
        """
        total_revenue = float(
            self.db.query(func.sum(FactRevenue.recognized_revenue)).scalar() or 0.0
        )
        total_collections = float(
            self.db.query(func.sum(FactCollections.amount)).scalar() or 0.0
        )

        # Latest snapshot date across all projects.
        latest_date = (
            self.db.query(func.max(FactReceivablesSnapshot.snapshot_date)).scalar()
        )
        if latest_date is not None:
            total_receivables = float(
                self.db.query(func.sum(FactReceivablesSnapshot.total_receivables))
                .filter(FactReceivablesSnapshot.snapshot_date == latest_date)
                .scalar()
                or 0.0
            )
        else:
            total_receivables = 0.0

        # Collect distinct currencies present across all analytics facts so
        # callers can detect when the portfolio spans multiple denominations.
        revenue_currencies = {
            r[0]
            for r in self.db.query(FactRevenue.currency).distinct().all()
        }
        collections_currencies = {
            r[0]
            for r in self.db.query(FactCollections.currency).distinct().all()
        }
        all_currencies = sorted(revenue_currencies | collections_currencies)

        # collection_efficiency is only valid when all facts share a single
        # currency.  Set to None for multi-currency portfolios so callers cannot
        # silently consume a cross-currency ratio.
        multi_currency = len(all_currencies) > 1
        if multi_currency:
            collection_efficiency: Optional[float] = None
        else:
            collection_efficiency = (
                round(total_collections / total_revenue, 4) if total_revenue > 0 else 0.0
            )

        return PortfolioKPI(
            total_revenue=round(total_revenue, 2),
            total_collections=round(total_collections, 2),
            total_receivables=round(total_receivables, 2),
            collection_efficiency=collection_efficiency,
            currencies=all_currencies,
        )
