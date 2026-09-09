"""Small deterministic portfolio reductions; no persistence or query logic."""

from collections import defaultdict
from decimal import Decimal

from app.modules.portfolio.schemas import MoneyMetric, ProjectSummary, Risk


def risk_order(risk: Risk) -> tuple[int, str, str, str]:
    return (
        0 if risk.severity == "high" else 1,
        risk.project_code,
        str(risk.project_id),
        risk.risk_id,
    )


def currency_totals(projects: list[ProjectSummary]) -> list[MoneyMetric]:
    buckets: dict[tuple[str, str], list[MoneyMetric]] = defaultdict(list)
    for project in projects:
        for metric in project.money:
            buckets[(metric.metric_code, metric.currency)].append(metric)
    result = []
    for (code, currency), rows in sorted(buckets.items()):
        known = [row for row in rows if row.availability == "available" and row.amount is not None]
        missing = len(rows) - len(known)
        result.append(
            MoneyMetric(
                metric_code=code,
                currency=currency,
                amount=sum((row.amount for row in known), Decimal(0)) if known else None,
                availability="partial"
                if known and missing
                else "available"
                if known
                else "unavailable",
                reason=f"{missing} project(s) have unavailable source coverage."
                if missing
                else None,
                contributing_project_count=len(known),
                missing_project_count=missing,
                source_basis=rows[0].source_basis,
                drilldown="/portfolio/?section=projects",
            )
        )
    return result
