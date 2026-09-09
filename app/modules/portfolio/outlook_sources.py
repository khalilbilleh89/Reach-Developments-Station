"""Set-based owner source observations; no dependency on management actions."""

import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

from sqlalchemy import Row, Select, select
from sqlalchemy.orm import Session

from app.modules.portfolio import service
from app.modules.portfolio.outlook_schemas import Coverage, CurrencyBucket, Item
from app.modules.projects.models import Project
from app.modules.settings.models import Currency


def observations(
    session: Session,
    scope: Select,
    as_of: date,
    horizon_end: date,
    coverage: list[Coverage],
    buckets: list[CurrencyBucket],
) -> Iterator[Item]:
    projects = list(
        session.execute(
            select(
                Project.id, Project.code, Project.name, Project.base_currency_id, Project.created_at
            ).where(Project.id.in_(scope))
        )
    )
    if not projects:
        return
    currencies = dict(session.execute(select(Currency.id, Currency.code)).all())
    stock = service.inventory.positions(session, scope)
    sales = service.sales.positions(session, scope, as_of, risk_only=True)
    collections = service.collections.positions(session, scope, as_of)
    cash = service.cashflow.positions(session, scope, as_of)
    costs = service.construction.positions(session, scope, risk_only=True)
    permits = service.development.positions(session, scope, as_of, risk_only=True)
    design = service.consultant.positions(session, scope, as_of)
    collection_coverage = Coverage(
        source="scheduled_collection_due",
        reason=(
            "Missing governing schedules or incompatible allocations are "
            "unavailable; undated contingent obligations are excluded from dated "
            "due amounts."
        ),
    )
    permit_coverage = Coverage(
        source="permit_due",
        reason=(
            "Only unresolved permits with an existing statutory SLA have an "
            "authoritative deadline; undated permits are not placed in the "
            "horizon."
        ),
    )
    design_coverage = Coverage(
        source="consultant_design",
        reason=(
            "Only the active engagement contributes; missing programmes and "
            "undated open items remain incomplete."
        ),
    )
    coverage.extend([collection_coverage, permit_coverage, design_coverage])
    denomination_buckets: dict[str, CurrencyBucket] = {}
    contributors: dict[str, set[uuid.UUID]] = {}
    for project in projects:
        pid = project.id

        def item(
            kind: str,
            key: str,
            title: str,
            section: str,
            basis: str,
            *,
            project: Row = project,
            **values: object,
        ) -> Item:
            return Item(
                item_type=kind,
                source_key=f"{project.id}:{kind}:{key}",
                project_id=project.id,
                project_code=project.code,
                project_name=project.name,
                title=title,
                observation_date=as_of,
                basis=basis,
                drilldown=f"/projects/?project={project.id}&section={section}",
                **values,
            )

        inv = stock.get(pid, service.inventory.InventoryPosition(frozenset(), 0, 0))
        sale = sales.get(pid, service.sales.SalesPosition())
        net, observed = service.commercial_observation(project, sale, as_of)
        remaining = len(inv.eligible_ids - sale.committed_ids) if inv.eligible_ids else None
        forecast = service.forecast(as_of, remaining, net, observed)
        yield item(
            "commercial_sellout",
            str(forecast.window_to),
            "Commercial sellout run-rate estimate",
            "analysis",
            forecast.source_basis,
            commercial=forecast,
            availability=forecast.availability,
            reason=forecast.reason,
        )
        position = cash[pid]
        horizon = service.cashflow.horizon_position(position, as_of, horizon_end)
        yield item(
            "cashflow_forecast",
            str(position.forecast_id or "unavailable"),
            "FORECAST · Lowest unrestricted cash",
            "cashflow",
            "Governed monthly closing unrestricted cash in intersecting "
            "horizon months; full boundary months, no proration.",
            amount=horizon.lowest_unrestricted_cash,
            currency=currencies[position.governing_currency],
            source_version_id=position.forecast_id,
            source_as_of=position.forecast_as_of,
            lowpoint_month=horizon.lowpoint_month,
            first_deficit_month=horizon.first_deficit_month,
            peak_deficit=horizon.peak_deficit,
            forecast_end_month=position.forecast_end_month,
            availability=horizon.availability,
            reason=horizon.reason,
        )
        cost = costs.get(pid, service.construction.ConstructionPosition())
        comparable = (
            cost.eac is not None
            and cost.control_budget is not None
            and cost.forecast_currency == cost.budget_currency
        )
        yield item(
            "construction_eac",
            str(cost.forecast_id or "unavailable"),
            "Construction estimate at completion",
            "construction",
            "Active owner EAC and approved control budget, excluding tax; "
            "only same-currency values are comparable.",
            amount=cost.eac if comparable else None,
            control_budget=cost.control_budget if comparable else None,
            currency=currencies[cost.forecast_currency] if cost.forecast_currency else None,
            source_version_id=cost.forecast_id,
            budget_version_id=cost.budget_id,
            availability="available" if comparable else "unavailable",
            reason=None if comparable else "Missing or incompatible governed budget/EAC basis.",
        )
        collected = collections.get(pid, service.collections.CollectionsPosition())
        collection_coverage.unavailable_project_count += int(
            bool(collected.unavailable_overdue_currencies)
        )
        collection_coverage.undated_item_count += collected.undated_installments
        for currency_id in collected.unavailable_overdue_currencies:
            code = currencies[currency_id]
            denomination_buckets.setdefault(
                code, CurrencyBucket(currency=code)
            ).unavailable_project_count += 1
        for iid, _sale_id, version_id, label, due, currency_id, amount in collected.scheduled:
            if not as_of <= due <= horizon_end:
                continue
            code = currencies[currency_id]
            bucket = denomination_buckets.setdefault(code, CurrencyBucket(currency=code))
            bucket.scheduled_outstanding_due = (
                bucket.scheduled_outstanding_due or Decimal("0")
            ) + amount
            contributors.setdefault(code, set()).add(pid)
            yield item(
                "scheduled_collection_due",
                f"{version_id}:{iid}:{due}",
                label,
                "collections",
                "SCHEDULED / CONTRACTUAL DUE: governing installment "
                "outstanding after confirmed allocations, as of today. Not "
                "expected or actual cash; contingent undated triggers "
                "excluded.",
                due_date=due,
                currency=code,
                amount=amount,
                source_version_id=version_id,
            )
        development = permits.get(pid, service.development.DevelopmentPosition())
        permit_coverage.undated_item_count += development.undated_permits
        for ident, label, due, status, blocking in development.deadlines:
            if as_of <= due <= horizon_end:
                yield item(
                    "permit_due",
                    f"{ident}:{due}",
                    label,
                    "permits",
                    "Current status-effective date plus the permit's "
                    "statutory SLA; horizon inclusion assigns no risk "
                    "severity.",
                    due_date=due,
                    status=status,
                    blocking=blocking,
                )
        programme = design.get(pid)
        if programme is None:
            design_coverage.unavailable_project_count += 1
            continue
        design_coverage.undated_item_count += programme.undated_open_items
        design_coverage.unavailable_project_count += int(not programme.stage_count)
        for ident, label, due, status, planned, expected, actual in programme.open_stages:
            if as_of <= due <= horizon_end:
                yield item(
                    "consultant_stage_due",
                    f"{programme.engagement_id}:{ident}:{due}",
                    label,
                    "consultant",
                    "Active engagement, open uncompleted stage: forecast "
                    "date governs, otherwise planned date.",
                    due_date=due,
                    status=status,
                    planned_date=planned,
                    forecast_date=expected,
                    actual_date=actual,
                    source_version_id=programme.engagement_id,
                )
        for ident, label, due, status in programme.open_deliverables:
            if as_of <= due <= horizon_end:
                yield item(
                    "consultant_deliverable_due",
                    f"{programme.engagement_id}:{ident}:{due}",
                    label,
                    "consultant",
                    "Open deliverable on the active engagement; owner due date.",
                    due_date=due,
                    status=status,
                    source_version_id=programme.engagement_id,
                )
    for code, bucket in denomination_buckets.items():
        bucket.contributing_project_count = len(contributors.get(code, set()))
        if bucket.unavailable_project_count:
            bucket.availability = (
                "unavailable" if bucket.scheduled_outstanding_due is None else "partial"
            )
    buckets.extend(denomination_buckets[code] for code in sorted(denomination_buckets))
