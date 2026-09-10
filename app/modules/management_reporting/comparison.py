"""Compare captured facts, with no live source recalculation or silent zeroes."""

import uuid
from collections.abc import Iterable, Mapping
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.modules.management_actions import reporting as actions
from app.modules.management_reporting import schemas as out
from app.modules.portfolio.schemas import Overview, ProjectSummary


def section(metric: str) -> str:
    if metric.startswith("construction_"):
        return "construction"
    if metric in {"confirmed_receipts", "refunds", "unapplied_cash", "overdue_outstanding"}:
        return "collections"
    if "cash" in metric or "deficit" in metric:
        return "cashflow"
    return "commercial" if metric == "contracted_value" else "capital"


def compare(session: Session, prior: out.SnapshotOut, current: out.SnapshotOut) -> out.Comparison:
    if prior.schema_version != current.schema_version or prior.schema_version != 1:
        raise ConflictError("Snapshot schema versions are not compatible.")
    if prior.scope_type != current.scope_type or prior.project_id != current.project_id:
        raise ConflictError("Compare the same project, or two portfolio snapshots.")
    if prior.captured_at >= current.captured_at:
        raise ConflictError("Choose an earlier prior snapshot and a later current snapshot.")
    before = {p.project_id: p for p in prior.payload.projects}
    after = {p.project_id: p for p in current.payload.projects}
    common = before.keys() & after.keys()
    composition = before.keys() != after.keys()
    movements: list[out.Movement] = []
    facts: list[out.FactChange] = []

    def movement(
        metric: str,
        a: Decimal | int | None,
        b: Decimal | int | None,
        *,
        domain: str,
        unit: str = "count",
        currency: str | None = None,
        prior_currency: str | None = None,
        current_currency: str | None = None,
        project: ProjectSummary | None = None,
        avail_a: str = "available",
        avail_b: str = "available",
        basis: str,
        blocked: str | None = None,
    ) -> None:
        reason = blocked or (
            "Source coverage or value unavailable."
            if a is None or b is None or avail_a != "available" or avail_b != "available"
            else None
        )
        comparable = reason is None
        movements.append(
            out.Movement(
                section=domain,
                metric=metric,
                project_id=project.project_id if project else None,
                project_code=project.code if project else None,
                currency=currency,
                prior_currency=prior_currency or currency,
                current_currency=current_currency or currency,
                unit=unit,
                prior=a,
                current=b,
                delta=Decimal(b) - Decimal(a) if comparable else None,
                prior_availability=avail_a,
                current_availability=avail_b,
                comparable=comparable,
                reason=reason,
                basis=basis,
            )
        )

    def money(
        left: Overview | ProjectSummary,
        right: Overview | ProjectSummary,
        project: ProjectSummary | None = None,
    ) -> None:
        am = {(m.metric_code, m.currency): m for m in left.money}
        bm = {(m.metric_code, m.currency): m for m in right.money}
        for key in sorted(am.keys() | bm.keys()):
            a, b = am.get(key), bm.get(key)
            blocked = None
            if a is None or b is None:
                blocked = (
                    "Added currency position."
                    if a is None
                    else "Currency position no longer present."
                )
            elif a.source_basis != b.source_basis:
                blocked = "Source basis changed."
            elif project is None:

                def contributors(
                    rows: Iterable[ProjectSummary], key: tuple[str, str]
                ) -> set[uuid.UUID]:
                    return {
                        p.project_id
                        for p in rows
                        if any(
                            (m.metric_code, m.currency) == key and m.availability == "available"
                            for m in p.money
                        )
                    }

                if composition or contributors(before.values(), key) != contributors(
                    after.values(), key
                ):
                    blocked = "Portfolio composition or contributing project coverage changed."
            movement(
                key[0],
                a.amount if a else None,
                b.amount if b else None,
                domain=section(key[0]),
                unit="money",
                currency=key[1],
                project=project,
                avail_a=a.availability if a else "absent",
                avail_b=b.availability if b else "absent",
                basis=(b or a).source_basis,
                blocked=blocked,
            )

    def counts(
        a: Overview | ProjectSummary,
        b: Overview | ProjectSummary,
        project: ProjectSummary | None = None,
    ) -> None:
        for metric in ("eligible_units", "committed_units", "active_sold_units"):
            movement(
                metric,
                getattr(a, metric),
                getattr(b, metric),
                domain="commercial",
                project=project,
                basis="Captured Inventory / SaleContract owner counts.",
                blocked="Portfolio composition changed."
                if project is None and composition
                else None,
            )
        movement(
            "sales_penetration",
            a.sales_penetration.percentage,
            b.sales_penetration.percentage,
            domain="commercial",
            unit="percentage_points",
            project=project,
            avail_a=a.sales_penetration.availability,
            avail_b=b.sales_penetration.availability,
            basis=b.sales_penetration.source_basis,
            blocked="Portfolio composition changed." if project is None and composition else None,
        )

    money(prior.payload.overview, current.payload.overview)
    counts(prior.payload.overview, current.payload.overview)
    for pid in sorted(common, key=lambda pid: (after[pid].code, str(pid))):
        a, b = before[pid], after[pid]
        money(a, b, b)
        counts(a, b, b)
        for metric in ("available_units", "remaining_units"):
            movement(
                metric,
                getattr(a, metric),
                getattr(b, metric),
                domain="commercial",
                project=b,
                basis="Captured Inventory owner count.",
            )
        for metric in ("average_monthly_absorption", "estimated_months_to_sell"):
            movement(
                metric,
                getattr(a.sales_run_rate, metric),
                getattr(b.sales_run_rate, metric),
                domain="commercial",
                unit="units_per_month" if metric.startswith("average") else "months",
                project=b,
                avail_a=a.sales_run_rate.availability,
                avail_b=b.sales_run_rate.availability,
                basis=b.sales_run_rate.source_basis,
            )
        for metric in ("name", "code", "status", "currency", "coverage", "cashflow_reason_code"):
            facts.append(
                out.FactChange(
                    section="identity"
                    if metric in {"name", "code", "status", "currency"}
                    else "coverage",
                    project_id=pid,
                    project_code=b.code,
                    fact=metric,
                    prior=getattr(a, metric),
                    current=getattr(b, metric),
                )
            )
        for metric in (
            "current_stage",
            "planned_date",
            "forecast_date",
            "actual_date",
            "stage_status",
            "availability",
            "reason",
        ):
            av, bv = getattr(a.design, metric), getattr(b.design, metric)
            facts.append(
                out.FactChange(
                    section="design",
                    project_id=pid,
                    project_code=b.code,
                    fact=metric,
                    prior=str(av) if av is not None else None,
                    current=str(bv) if bv is not None else None,
                )
            )
        for riskcode in sorted(
            {e.risk_code for e in a.risk_evaluations} | {e.risk_code for e in b.risk_evaluations}
        ):
            av = next((e for e in a.risk_evaluations if e.risk_code == riskcode), None)
            bv = next((e for e in b.risk_evaluations if e.risk_code == riskcode), None)
            facts.append(
                out.FactChange(
                    section="coverage",
                    project_id=pid,
                    project_code=b.code,
                    fact=riskcode,
                    prior=f"{av.availability}: {av.reason or 'Evaluated'}" if av else None,
                    current=f"{bv.availability}: {bv.reason or 'Evaluated'}" if bv else None,
                )
            )
    # Horizon facts retain their source semantics. IDs that include versions/dates
    # are not used to match changing forecasts; project + kind + horizon is stable.
    for horizon in (30, 60, 90):
        af = next(o for o in prior.payload.outlooks if o.horizon_days == horizon)
        bf = next(o for o in current.payload.outlooks if o.horizon_days == horizon)
        for pid in sorted(common, key=str):
            for kind in ("cashflow_forecast", "construction_eac"):
                a = next((i for i in af.items if i.project_id == pid and i.item_type == kind), None)
                b = next((i for i in bf.items if i.project_id == pid and i.item_type == kind), None)
                for metric in (
                    ("amount", "peak_deficit")
                    if kind == "cashflow_forecast"
                    else ("amount", "control_budget")
                ):
                    movement(
                        f"{kind}_{metric}_{horizon}d",
                        getattr(a, metric) if a else None,
                        getattr(b, metric) if b else None,
                        domain="cashflow" if kind == "cashflow_forecast" else "construction",
                        unit="money",
                        currency=b.currency if b else a.currency if a else None,
                        prior_currency=a.currency if a else None,
                        current_currency=b.currency if b else None,
                        project=after[pid],
                        avail_a=a.availability if a else "absent",
                        avail_b=b.availability if b else "absent",
                        basis=(b or a).basis if b or a else "Source unavailable.",
                        blocked="Currency or source basis changed."
                        if a and b and (a.currency != b.currency or a.basis != b.basis)
                        else None,
                    )
                for metric in (
                    "source_version_id",
                    "first_deficit_month",
                    "lowpoint_month",
                    "forecast_end_month",
                    "availability",
                    "reason",
                ):
                    av, bv = getattr(a, metric) if a else None, getattr(b, metric) if b else None
                    facts.append(
                        out.FactChange(
                            section="cashflow" if kind == "cashflow_forecast" else "construction",
                            project_id=pid,
                            project_code=after[pid].code,
                            fact=f"{kind}_{metric}_{horizon}d",
                            prior=str(av) if av is not None else None,
                            current=str(bv) if bv is not None else None,
                        )
                    )
    prior_development = {
        (f.kind, f.source_id): f for f in prior.payload.development if f.project_id in common
    }
    current_development = {
        (f.kind, f.source_id): f for f in current.payload.development if f.project_id in common
    }
    for key in sorted(prior_development.keys() | current_development.keys(), key=str):
        a, b = prior_development.get(key), current_development.get(key)
        source = b or a
        for name in (
            "status",
            "due_date",
            "blocking",
            "planned_date",
            "forecast_date",
            "actual_date",
        ):
            av, bv = getattr(a, name) if a else None, getattr(b, name) if b else None
            facts.append(
                out.FactChange(
                    section="development",
                    project_id=source.project_id,
                    project_code=after[source.project_id].code,
                    fact=f"{source.kind}: {source.label} / {source.source_id} / {name}",
                    prior=str(av) if av is not None else None,
                    current=str(bv) if bv is not None else None,
                )
            )
    ar = {r.risk_id: r for p in before.values() if p.project_id in common for r in p.risks}
    br = {r.risk_id: r for p in after.values() if p.project_id in common for r in p.risks}
    risks = []
    for key in sorted(ar.keys() | br.keys()):
        a, b = ar.get(key), br.get(key)
        classification = "continuing" if a and b else "new" if b else "resolved"
        reason = None
        if not a or not b:
            risk = b or a
            opposite = before[risk.project_id] if b else after[risk.project_id]
            evaluated = next(
                (e for e in opposite.risk_evaluations if e.risk_code == risk.risk_code), None
            )
            if evaluated is None or evaluated.availability != "available":
                classification = "coverage_changed"
                reason = (
                    "Absence under incomplete source coverage cannot prove "
                    "appearance or resolution."
                )
        risks.append(
            out.RiskChange(classification=classification, prior=a, current=b, reason=reason)
        )
    captured = [a for a in current.payload.actions if a.project_id in common]
    execution = out.Execution(
        **actions.execution(
            session,
            [a for a in current.payload.action_frontier if a.project_id in common],
            prior.captured_at,
            current.captured_at,
        ),
        prior_overdue=sum(
            a.project_id in common
            and a.status in ("open", "in_progress")
            and a.due_date < prior.as_of_date
            for a in prior.payload.actions
        ),
        current_overdue=sum(
            a.status in ("open", "in_progress") and a.due_date < current.as_of_date
            for a in captured
        ),
    )

    def identities(
        ids: Iterable[uuid.UUID], source: Mapping[uuid.UUID, ProjectSummary]
    ) -> list[out.ProjectIdentity]:
        return [
            out.ProjectIdentity(project_id=pid, code=source[pid].code, name=source[pid].name)
            for pid in sorted(ids, key=lambda pid: (source[pid].code, str(pid)))
        ]

    return out.Comparison(
        prior=out.SnapshotHeader.model_validate(prior),
        current=out.SnapshotHeader.model_validate(current),
        added_projects=identities(after.keys() - before.keys(), after),
        removed_projects=identities(before.keys() - after.keys(), before),
        common_projects=identities(common, after),
        composition_changed=composition,
        movements=movements,
        facts=facts,
        risks=risks,
        execution=execution,
    )
