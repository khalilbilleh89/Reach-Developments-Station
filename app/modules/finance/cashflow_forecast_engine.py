"""
finance.cashflow_forecast_engine

Core cashflow forecasting engine.

Forecast model:
  expected_collections = SUM(amount) for installments with status in
                         (PENDING, OVERDUE) grouped by calendar month.

Rules:
  - Only future-due or already-overdue installments are included.
  - PAID and CANCELLED installments are excluded.
  - Months are represented as YYYY-MM strings for readability and sorting.
  - No SQL is embedded here; all data is passed in by the service layer.
  - Returned entries are sorted ascending by month.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstallmentLine:
    """A single installment record consumed by the forecast engine."""

    contract_id: str
    project_id: str
    due_date: date
    amount: float
    status: str  # pending | overdue (paid/cancelled are filtered before this)


@dataclass(frozen=True)
class MonthlyForecastEntry:
    """Projected cash inflow for a single calendar month."""

    month: str  # YYYY-MM
    expected_collections: float
    installment_count: int


@dataclass(frozen=True)
class ProjectForecastResult:
    """Cashflow forecast for a single project."""

    project_id: str
    total_expected: float
    monthly_entries: List[MonthlyForecastEntry]


@dataclass(frozen=True)
class PortfolioForecastResult:
    """Cashflow forecast aggregated across the entire portfolio."""

    total_expected: float
    monthly_entries: List[MonthlyForecastEntry]
    project_forecasts: List[ProjectForecastResult]


# ---------------------------------------------------------------------------
# Engine functions
# ---------------------------------------------------------------------------


def _month_key(d: date) -> str:
    """Return a YYYY-MM string for grouping installments by month."""
    return f"{d.year:04d}-{d.month:02d}"


def build_project_forecast(
    project_id: str,
    installments: List[InstallmentLine],
) -> ProjectForecastResult:
    """Compute a monthly cashflow forecast for a single project.

    Parameters
    ----------
    project_id:
        The project being forecast.
    installments:
        Pre-filtered installment lines for this project.
        Must contain only PENDING / OVERDUE installments.

    Returns
    -------
    ProjectForecastResult
        Monthly expected-collection timeline plus totals.
    """
    bucket: dict[str, dict] = {}
    for line in installments:
        key = _month_key(line.due_date)
        if key not in bucket:
            bucket[key] = {"amount": 0.0, "count": 0}
        bucket[key]["amount"] += line.amount
        bucket[key]["count"] += 1

    monthly_entries = [
        MonthlyForecastEntry(
            month=k,
            expected_collections=round(v["amount"], 2),
            installment_count=v["count"],
        )
        for k, v in sorted(bucket.items())
    ]

    total_expected = round(sum(e.expected_collections for e in monthly_entries), 2)

    return ProjectForecastResult(
        project_id=project_id,
        total_expected=total_expected,
        monthly_entries=monthly_entries,
    )


def build_portfolio_forecast(
    project_installments: dict[str, List[InstallmentLine]],
) -> PortfolioForecastResult:
    """Aggregate cashflow forecasts across all projects.

    Parameters
    ----------
    project_installments:
        Mapping of project_id → list of PENDING/OVERDUE installment lines
        belonging to that project.

    Returns
    -------
    PortfolioForecastResult
        Per-project breakdowns plus a combined monthly timeline.
    """
    project_forecasts = [
        build_project_forecast(pid, lines)
        for pid, lines in project_installments.items()
    ]

    # Merge individual project monthly totals into a single timeline.
    combined: dict[str, dict] = {}
    for pf in project_forecasts:
        for entry in pf.monthly_entries:
            if entry.month not in combined:
                combined[entry.month] = {"amount": 0.0, "count": 0}
            combined[entry.month]["amount"] += entry.expected_collections
            combined[entry.month]["count"] += entry.installment_count

    monthly_entries = [
        MonthlyForecastEntry(
            month=k,
            expected_collections=round(v["amount"], 2),
            installment_count=v["count"],
        )
        for k, v in sorted(combined.items())
    ]

    total_expected = round(sum(e.expected_collections for e in monthly_entries), 2)

    return PortfolioForecastResult(
        total_expected=total_expected,
        monthly_entries=monthly_entries,
        project_forecasts=project_forecasts,
    )
