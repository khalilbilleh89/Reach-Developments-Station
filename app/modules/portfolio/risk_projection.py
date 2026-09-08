"""Scoped risk facts, global counts and bounded candidate selection.

Exact totals require evaluating the authorized risk sources. Owner reads are
set-based; neither ProjectSummary nor its unrelated KPIs are composed here.
Only the smallest offset + limit candidates survive selection, and only the
requested page becomes response Risk objects. No project pagination or cache.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from heapq import nsmallest

from sqlalchemy import Row, Select, select
from sqlalchemy.orm import Session

from app.modules.portfolio import calculations, service
from app.modules.portfolio import schemas as out
from app.modules.projects.models import Project
from app.modules.settings.models import Currency


@dataclass
class Metric:
    metric_code: str
    amount: Decimal | None
    currency: str
    drilldown: str
    reason: str | None = None


@dataclass
class Observation:
    monthly_net_absorption: list[int]
    observed_months: int


@dataclass
class Coverage:
    availability: str
    reason: str | None = None


@dataclass
class Candidate:
    """Unvalidated triggered fact; response construction happens after selection."""

    risk_id: str
    severity: str
    project_code: str
    project_id: uuid.UUID
    fields: dict

    @classmethod
    def from_fields(cls, **fields: object) -> "Candidate":
        return cls(
            fields["risk_id"],
            fields["severity"],
            fields["project_code"],
            fields["project_id"],
            fields,
        )


@dataclass
class RiskFacts:
    """Only inputs consumed by the shared ten frozen predicates."""

    project_id: uuid.UUID
    code: str
    name: str
    as_of: date
    money: list[Metric]
    eligible_units: int
    remaining_units: int
    sales_run_rate: Observation
    design: Coverage
    risks: list[Candidate] = field(default_factory=list)
    risk_evaluations: list[out.Evaluation] = field(default_factory=list)
    risk_count: int = 0
    highest_risk: str | None = None
    coverage: str = "available"


def page(
    session: Session, project_ids: Select, as_of: date, *, limit: int, offset: int
) -> out.RiskPage:
    projects = list(
        session.execute(
            select(
                Project.id, Project.code, Project.name, Project.base_currency_id, Project.created_at
            ).where(Project.id.in_(project_ids))
        )
    )
    result = out.RiskPage(
        as_of=as_of, items=[], total=0, offset=offset, limit=limit, unavailable_project_count=0
    )
    if not projects:
        return result
    currencies = dict(session.execute(select(Currency.id, Currency.code)).all())
    stock = service.inventory.positions(session, project_ids)
    commercial = service.sales.positions(session, project_ids, as_of, risk_only=True)
    collected = service.collections.positions(session, project_ids, as_of, risk_only=True)
    # Cashflow retains its complete owner currency/governance checks and bridge.
    cash = service.cashflow.positions(session, project_ids, as_of)
    costs = service.construction.positions(session, project_ids, risk_only=True)
    permits = service.development.positions(session, project_ids, as_of, risk_only=True)
    design = service.consultant.positions(session, project_ids, as_of)

    def facts_for(project: Row) -> RiskFacts:
        pid = project.id
        currency = currencies[project.base_currency_id]
        money: list[Metric] = []

        def metric(
            code: str,
            amount: Decimal | None,
            section: str,
            denomination: uuid.UUID | None = None,
            reason: str | None = None,
        ) -> None:
            money.append(
                Metric(
                    code,
                    amount,
                    currencies[denomination] if denomination else currency,
                    f"/projects/?project={pid}&section={section}",
                    reason,
                )
            )

        collection = collected.get(pid, service.collections.CollectionsPosition())
        for denomination, amount in (
            collection.unapplied or {project.base_currency_id: Decimal(0)}
        ).items():
            metric("unapplied_cash", amount, "collections", denomination)
        for denomination in set(collection.overdue) | collection.unavailable_overdue_currencies or {
            project.base_currency_id
        }:
            unsafe = denomination in collection.unavailable_overdue_currencies
            metric(
                "overdue_outstanding",
                None if unsafe else collection.overdue.get(denomination, Decimal(0)),
                "collections",
                denomination,
                "Missing governing schedule or incompatible allocation currency."
                if unsafe
                else None,
            )
        position = cash[pid]
        metric("unrestricted_cash", position.unrestricted_cash, "cashflow", reason=position.reason)
        metric(
            "forecast_peak_deficit",
            position.peak_deficit,
            "cashflow",
            reason=position.forecast_reason,
        )
        cost = costs.get(pid, service.construction.ConstructionPosition())
        metric(
            "construction_control_budget",
            cost.control_budget,
            "construction",
            cost.budget_currency,
        )
        metric("construction_eac", cost.eac, "construction", cost.forecast_currency)
        inv = stock.get(pid, service.inventory.InventoryPosition(frozenset(), 0, 0))
        sale = commercial.get(pid, service.sales.SalesPosition())
        net, observed = service.commercial_observation(project, sale, as_of)
        programme = design.get(pid)
        coverage = Coverage("unavailable", "No active Consultant engagement.")
        if programme:
            partial = programme.undated_open_items or not programme.stage_count
            coverage = Coverage(
                "partial" if partial else "available",
                "Open programme items have no due date or no stage programme exists."
                if partial
                else None,
            )
        facts = RiskFacts(
            project_id=pid,
            code=project.code,
            name=project.name,
            as_of=as_of,
            money=money,
            eligible_units=len(inv.eligible_ids),
            remaining_units=len(inv.eligible_ids) - len(inv.eligible_ids & sale.committed_ids),
            sales_run_rate=Observation(net, observed),
            design=coverage,
        )
        service._risks(
            facts,
            permits.get(pid, service.development.DevelopmentPosition()),
            programme,
            risk_factory=Candidate.from_fields,
        )
        return facts

    def candidates() -> Iterator[Candidate]:
        for project in projects:
            facts = facts_for(project)
            result.total += len(facts.risks)
            result.unavailable_project_count += int(
                any(item.availability != "available" for item in facts.risk_evaluations)
            )
            yield from facts.risks

    prefix = nsmallest(offset + limit, candidates(), key=calculations.risk_order)
    result.items = [out.Risk(**candidate.fields) for candidate in prefix[offset:]]
    return result
