"""Read-only composition over authorized owner-domain batch contracts."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.portfolio.risk_projection import RiskFacts

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.cashflow import batch as cashflow
from app.modules.collections import batch as collections
from app.modules.commissions import batch as commissions
from app.modules.construction import batch as construction
from app.modules.consultant_engineering import batch as consultant
from app.modules.inventory import batch as inventory
from app.modules.portfolio import calculations
from app.modules.portfolio import schemas as out
from app.modules.project_analysis.calculations import forecast, ratio, shift_month
from app.modules.projects import batch as development
from app.modules.projects.models import Project
from app.modules.sales import batch as sales
from app.modules.settings.models import Currency

PENETRATION_BASIS = "Distinct committed eligible units / eligible Inventory units * 100."


def summaries(session: Session, project_ids: Select, as_of: date) -> list[out.ProjectSummary]:
    projects = list(
        session.scalars(
            select(Project).where(Project.id.in_(project_ids)).order_by(Project.code, Project.id)
        )
    )
    if not projects:
        return []
    currencies = dict(session.execute(select(Currency.id, Currency.code)).all())
    stock = inventory.positions(session, project_ids)
    commercial = sales.positions(session, project_ids, as_of)
    collected = collections.positions(session, project_ids, as_of)
    cash = cashflow.positions(session, project_ids, as_of)
    costs = construction.positions(session, project_ids)
    permits = development.positions(session, project_ids, as_of)
    design = consultant.positions(session, project_ids, as_of)
    released = commissions.released(session, project_ids)
    return [
        _project_summary(
            project,
            currencies,
            stock,
            commercial,
            collected,
            cash,
            costs,
            permits,
            design,
            released,
            as_of,
        )
        for project in projects
    ]


def commercial_observation(
    project: Project, sale: sales.SalesPosition, as_of: date
) -> tuple[list[int], int]:
    """The existing three complete UTC months, shared by summaries and risks."""
    net = []
    observed = 0
    for offset in (-3, -2, -1):
        low, high = shift_month(as_of, offset), shift_month(as_of, offset + 1)
        observed += int(project.created_at.astimezone(UTC).date() <= low)
        net.append(
            sum(low <= day < high for day in sale.activations)
            - sum(low <= day < high for day in sale.cancellations)
        )
    return net, observed


def _project_summary(
    project: Project,
    currencies: dict[uuid.UUID, str],
    stock: dict[uuid.UUID, inventory.InventoryPosition],
    commercial: dict[uuid.UUID, sales.SalesPosition],
    collected: dict[uuid.UUID, collections.CollectionsPosition],
    cash: dict[uuid.UUID, cashflow.CashPosition],
    costs: dict[uuid.UUID, construction.ConstructionPosition],
    permits: dict[uuid.UUID, development.DevelopmentPosition],
    design: dict[uuid.UUID, consultant.DesignPosition],
    released: dict[uuid.UUID, dict[uuid.UUID, Decimal]],
    as_of: date,
) -> out.ProjectSummary:
    pid = project.id
    currency = currencies[project.base_currency_id]
    inv = stock.get(pid, inventory.InventoryPosition(frozenset(), 0, 0))
    sale = commercial.get(pid, sales.SalesPosition())
    collection = collected.get(pid, collections.CollectionsPosition())
    cost = costs.get(pid, construction.ConstructionPosition())
    dev = permits.get(pid, development.DevelopmentPosition())
    programme = design.get(pid)
    money: list[out.MoneyMetric] = []

    def metric(
        code: str,
        amount: Decimal | None,
        basis: str,
        section: str,
        denomination: uuid.UUID | None = None,
        reason: str | None = None,
        version_id: uuid.UUID | None = None,
    ) -> None:
        money.append(
            out.MoneyMetric(
                metric_code=code,
                amount=amount,
                currency=currencies[denomination] if denomination else currency,
                availability="available" if amount is not None else "unavailable",
                reason=reason,
                contributing_project_count=int(amount is not None),
                missing_project_count=int(amount is None),
                source_basis=basis,
                source_version_id=version_id,
                drilldown=f"/projects/?project={pid}&section={section}",
            )
        )

    def buckets(code: str, amounts: dict[uuid.UUID, Decimal], basis: str, section: str) -> None:
        for denomination, amount in sorted(
            (amounts or {project.base_currency_id: Decimal(0)}).items(),
            key=lambda row: currencies[row[0]],
        ):
            metric(code, amount, basis, section, denomination)

    buckets(
        "contracted_value",
        sale.contracted,
        "Standing activated SaleContract gross price including source tax and fees.",
        "sales",
    )
    buckets(
        "confirmed_receipts",
        collection.confirmed,
        "Confirmed gross Collections receipts; allocations are not additional cash.",
        "collections",
    )
    buckets(
        "refunds",
        collection.refunds,
        "Confirmed Collections refunds shown separately from receipts.",
        "collections",
    )
    buckets(
        "unapplied_cash",
        collection.unapplied,
        "Confirmed receipts less their standing allocations, in receipt currency.",
        "collections",
    )
    for code in set(collection.overdue) | collection.unavailable_overdue_currencies or {
        project.base_currency_id
    }:
        unsafe = code in collection.unavailable_overdue_currencies
        metric(
            "overdue_outstanding",
            None if unsafe else collection.overdue.get(code, Decimal(0)),
            (
                "Collections governing schedule, effective due "
                "dates, waivers and confirmed allocations."
            ),
            "collections",
            code,
            "Missing governing schedule or incompatible allocation currency." if unsafe else None,
        )
    cash_position = cash[pid]
    for code, amount in (
        ("total_cash", cash_position.total_cash),
        ("restricted_cash", cash_position.restricted_cash),
        ("unrestricted_cash", cash_position.unrestricted_cash),
    ):
        metric(
            code,
            amount,
            (
                "Cashflow actual position including governed "
                "opening anchor and standing cash movements."
            ),
            "cashflow",
            reason=cash_position.reason,
            version_id=cash_position.forecast_id,
        )
    metric(
        "forecast_peak_deficit",
        cash_position.peak_deficit,
        "Cashflow governed monthly bridge peak unrestricted deficit; no new management forecast.",
        "cashflow",
        reason=cash_position.forecast_reason,
        version_id=cash_position.forecast_id,
    )
    metric(
        "construction_control_budget",
        cost.control_budget,
        "Construction approved budget plus contingency, ex tax.",
        "construction",
        cost.budget_currency,
        "No active Construction control budget." if cost.control_budget is None else None,
        cost.budget_id,
    )
    metric(
        "construction_eac",
        cost.eac,
        "Construction certified value at forecast cutoff plus forecast remaining, ex tax.",
        "construction",
        cost.forecast_currency,
        cost.eac_reason or None,
        cost.forecast_id,
    )
    buckets(
        "construction_commitment",
        cost.revised_commitment,
        (
            "Construction committing contracts plus approved variations, "
            "ex tax; not comparable to cash paid."
        ),
        "construction",
    )
    buckets(
        "construction_paid",
        cost.paid,
        "Construction confirmed gross payments; separate cash-paid basis.",
        "construction",
    )
    metric(
        "land_acquisition",
        dev.land_total if dev.land_count and not dev.land_incomplete else None,
        "Active Land purchase price plus acquisition fees only when every component is known.",
        "land",
        reason="No complete Land acquisition basis."
        if not dev.land_count or dev.land_incomplete
        else None,
    )
    buckets(
        "commission_released",
        released.get(pid, {}),
        "Released Commission Distribution, NON-CASH; released does not mean paid.",
        "commissions",
    )
    eligible = len(inv.eligible_ids)
    committed = len(inv.eligible_ids & sale.committed_ids)
    remaining = eligible - committed
    net, observed = commercial_observation(project, sale, as_of)
    run_rate = forecast(as_of, remaining if eligible else None, net, observed)
    design_out = out.Design(availability="unavailable", reason="No active Consultant engagement.")
    if programme:
        design_out = out.Design(
            availability="partial"
            if programme.undated_open_items or not programme.stage_count
            else "available",
            reason="Open programme items have no due date or no stage programme exists."
            if programme.undated_open_items or not programme.stage_count
            else None,
            **{
                key: getattr(programme, key)
                for key in (
                    "engagement_id",
                    "consultant_name",
                    "current_stage",
                    "planned_date",
                    "forecast_date",
                    "actual_date",
                    "stage_status",
                    "stage_count",
                    "deliverable_count",
                )
            },
        )
    summary = out.ProjectSummary(
        project_id=pid,
        code=project.code,
        name=project.name,
        status=project.status,
        currency=currency,
        as_of=as_of,
        total_units=inv.total_units,
        eligible_units=eligible,
        available_units=inv.available_units,
        committed_units=committed,
        active_sold_units=len(inv.eligible_ids & sale.active_sold_ids),
        remaining_units=remaining,
        sales_penetration=ratio(committed, eligible, PENETRATION_BASIS),
        sales_run_rate=run_rate,
        money=sorted(money, key=lambda row: (row.metric_code, row.currency)),
        cashflow_reason_code=cash_position.reason_code,
        cashflow_observed_currencies=sorted(
            currencies[code] for code in cash_position.observed_currencies
        ),
        permit_count=dev.permit_count,
        design=design_out,
        risks=[],
        risk_evaluations=[],
        risk_count=0,
        coverage="partial"
        if any(row.availability != "available" for row in money)
        or design_out.availability != "available"
        else "available",
        drilldown=f"/projects/?project={pid}&section=overview",
    )
    _risks(summary, dev, programme)
    return summary


def _risks(
    project: out.ProjectSummary | RiskFacts,
    dev: development.DevelopmentPosition,
    programme: consultant.DesignPosition | None,
    *,
    risk_factory: Callable = out.Risk,
) -> None:
    """The frozen ten source-supported predicates; no scores or configurable engine."""

    def add(
        code: str,
        category: str,
        severity: str,
        title: str,
        value: str,
        basis: str,
        link: str,
        source: str,
        currency: str | None = None,
    ) -> None:
        project.risks.append(
            risk_factory(
                risk_id=f"{project.project_id}:{code}:{source}",
                risk_code=code,
                category=category,
                severity=severity,
                project_id=project.project_id,
                project_code=project.code,
                project_name=project.name,
                title=title,
                reason=f"{title}: {value}. {basis}",
                source_metric=source,
                source_value=value,
                currency=currency,
                basis=basis,
                observation_date=project.as_of,
                drilldown=link,
            )
        )

    checks = (
        (
            "ACTUAL_CASH_DEFICIT",
            "cashflow",
            "high",
            "Actual unrestricted cash deficit",
            "unrestricted_cash",
        ),
        (
            "FORECAST_CASH_DEFICIT",
            "cashflow",
            "high",
            "Forecast cash deficit",
            "forecast_peak_deficit",
        ),
        (
            "COLLECTIONS_OVERDUE",
            "collections",
            "attention",
            "Collections overdue",
            "overdue_outstanding",
        ),
        (
            "UNAPPLIED_CONFIRMED_CASH",
            "collections",
            "attention",
            "Unapplied confirmed cash",
            "unapplied_cash",
        ),
    )
    for code, category, severity, title, metric_code in checks:
        metrics = [row for row in project.money if row.metric_code == metric_code]
        missing = [row for row in metrics if row.amount is None]
        project.risk_evaluations.append(
            out.Evaluation(
                risk_code=code,
                availability="unavailable"
                if len(missing) == len(metrics)
                else "partial"
                if missing
                else "available",
                reason="; ".join(row.reason or "Source unavailable." for row in missing) or None,
            )
        )
        for row in metrics:
            if row.amount is not None and (
                row.amount < 0 if code == "ACTUAL_CASH_DEFICIT" else row.amount > 0
            ):
                add(
                    code,
                    category,
                    severity,
                    title,
                    str(row.amount),
                    "Threshold: < 0." if code == "ACTUAL_CASH_DEFICIT" else "Threshold: > 0.",
                    row.drilldown,
                    f"{metric_code}:{row.currency}",
                    row.currency,
                )
    budget = next(row for row in project.money if row.metric_code == "construction_control_budget")
    eac = next(row for row in project.money if row.metric_code == "construction_eac")
    comparable = (
        budget.amount is not None and eac.amount is not None and budget.currency == eac.currency
    )
    project.risk_evaluations.append(
        out.Evaluation(
            risk_code="CONSTRUCTION_COST_EXCEEDANCE",
            availability="available" if comparable else "unavailable",
            reason=None if comparable else "Comparable control budget and EAC required.",
        )
    )
    if comparable and eac.amount > budget.amount:
        add(
            "CONSTRUCTION_COST_EXCEEDANCE",
            "construction",
            "high",
            "Construction EAC exceeds control budget",
            str(eac.amount),
            f"EAC > control budget {budget.amount}, both ex tax.",
            eac.drilldown,
            "construction_eac",
            eac.currency,
        )
    for code, rows, severity, title in (
        ("UNRESOLVED_BLOCKING_PERMIT", dev.blockers, "high", "Unresolved blocking permit"),
        ("OVERDUE_PERMIT", dev.overdue, "attention", "Overdue permit"),
    ):
        project.risk_evaluations.append(out.Evaluation(risk_code=code, availability="available"))
        for identifier, label in rows:
            add(
                code,
                "permits",
                severity,
                title,
                label,
                "Includes unresolved permits; issued, renewed and withdrawn permits are excluded.",
                f"/projects/?project={project.project_id}&section=permits",
                str(identifier),
            )
    for code, rows, title in (
        (
            "CONSULTANT_STAGE_OVERDUE",
            programme.overdue_stages if programme else [],
            "Consultant stage overdue",
        ),
        (
            "CONSULTANT_DELIVERABLE_OVERDUE",
            programme.overdue_deliverables if programme else [],
            "Consultant deliverable overdue",
        ),
    ):
        project.risk_evaluations.append(
            out.Evaluation(
                risk_code=code,
                availability=project.design.availability,
                reason=project.design.reason,
            )
        )
        for identifier, label, due in rows:
            add(
                code,
                "design",
                "attention",
                title,
                f"{label}, due {due}",
                "Due date < observation date and item remains unresolved under active engagement.",
                f"/projects/?project={project.project_id}&section=consultant",
                str(identifier),
            )
    observed = project.sales_run_rate.observed_months == 3 and project.eligible_units > 0
    project.risk_evaluations.append(
        out.Evaluation(
            risk_code="COMMERCIAL_STALL",
            availability="available" if observed else "unavailable",
            reason=None
            if observed
            else "Three complete observed UTC months and eligible stock required.",
        )
    )
    if (
        observed
        and project.remaining_units > 0
        and sum(project.sales_run_rate.monthly_net_absorption) <= 0
    ):
        add(
            "COMMERCIAL_STALL",
            "commercial",
            "attention",
            "Commercial stall",
            str(sum(project.sales_run_rate.monthly_net_absorption)),
            "Remaining eligible stock > 0 and net absorption over three complete UTC months <= 0.",
            f"/projects/?project={project.project_id}&section=overview",
            "net_absorption",
        )
    project.risks.sort(key=calculations.risk_order)
    project.risk_count = len(project.risks)
    project.highest_risk = project.risks[0].severity if project.risks else None
    if any(item.availability != "available" for item in project.risk_evaluations):
        project.coverage = "partial"


def overview(projects: list[out.ProjectSummary], as_of: date) -> out.Overview:
    risks = sorted((risk for row in projects for risk in row.risks), key=calculations.risk_order)
    eligible = sum(row.eligible_units for row in projects)
    committed = sum(row.committed_units for row in projects)
    return out.Overview(
        as_of=as_of,
        project_count=len(projects),
        projects_requiring_attention=sum(row.risk_count > 0 for row in projects),
        projects_with_incomplete_coverage=sum(row.coverage != "available" for row in projects),
        eligible_units=eligible,
        committed_units=committed,
        active_sold_units=sum(row.active_sold_units for row in projects),
        sales_penetration=ratio(committed, eligible, PENETRATION_BASIS),
        money=calculations.currency_totals(projects),
        risk_count=len(risks),
        priority_risks=risks[:10],
        unavailable_risk_evaluations=dict(
            Counter(
                item.risk_code
                for row in projects
                for item in row.risk_evaluations
                if item.availability != "available"
            )
        ),
    )
