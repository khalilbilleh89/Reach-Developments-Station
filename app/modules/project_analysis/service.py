"""Derived reads from domain truth. No writes, audit events, snapshots or cache."""

import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.modules.access.models import User
from app.modules.cashflow import models as cash_models
from app.modules.cashflow import service as cashflow
from app.modules.collections.models import CollectionReceipt, CollectionRefund
from app.modules.construction.models import ConstructionStage, Payment, UnitStageEvent
from app.modules.consultant_engineering import service as consultant
from app.modules.inventory import models as inventory
from app.modules.inventory.physical import gross_measurement
from app.modules.inventory.service import analysis_eligible, sub_asset_counts
from app.modules.project_analysis import schemas as out
from app.modules.project_analysis.calculations import forecast, ratio, rounded, shift_month
from app.modules.projects.models import Permit, Project
from app.modules.sales.batch import standing
from app.modules.sales.models import (
    RESERVATION_COMMITTED,
    SALE_COMMITTED,
    Reservation,
    SaleContract,
)
from app.modules.settings.models import Currency

POSITION_BASIS = (
    "Current active primary units in available, reserved, contract_pending, contracted or "
    "returned Inventory states. Held, unreleased, withdrawn and inactive units excluded. "
    "Returned stock requires repricing. Commitments use Sales live reservation/contract "
    "states, not cash."
)
SALES_BASIS = (
    "UTC SaleContract.activated_at date; actual binding activation, not contract creation. "
    "Cancellations use UTC cancelled_at and only reverse previously activated sales. "
    "Contract values include tax/fees as total_contract_price, bucketed by original currency. "
    "Unactivated drafts and reservations are not sales."
)


def context(
    session: Session,
    project: Project,
    as_of: date | None,
    period_from: date | None,
    period_to: date | None,
    phase_id: uuid.UUID | None,
    building_id: uuid.UUID | None,
) -> out.Context:
    today = datetime.now(UTC).date()
    cutoff = as_of if as_of is not None else today
    end = period_to if period_to is not None else cutoff
    start = period_from if period_from is not None else shift_month(end, -11)
    if cutoff > today or start > end or end > cutoff or (end - start).days > 731:
        raise ValidationError(
            "Use a period of at most 732 days ending on or before as-of; future as-"
            "of dates are not supported."
        )
    for model, identifier in ((inventory.Phase, phase_id), (inventory.Building, building_id)):
        if identifier is not None:
            row = session.scalar(
                select(model).where(model.id == identifier, model.project_id == project.id)
            )
            if row is None or (
                model is inventory.Building and phase_id and row.phase_id != phase_id
            ):
                raise NotFoundError("Analysis scope not found in this project.")
    currency = session.get(Currency, project.base_currency_id)
    return out.Context(
        project_id=project.id,
        as_of=cutoff,
        period_from=start,
        period_to=end,
        filters={
            "phase_id": str(phase_id) if phase_id else None,
            "building_id": str(building_id) if building_id else None,
        },
        currency=currency.code,
        source_basis=SALES_BASIS,
        snapshot_as_of=today,
    )


def units(session: Session, ctx: out.Context) -> list[inventory.Unit]:
    query = (
        select(inventory.Unit)
        .join(inventory.Floor, inventory.Floor.id == inventory.Unit.floor_id)
        .join(inventory.Building, inventory.Building.id == inventory.Floor.building_id)
        .where(inventory.Unit.project_id == ctx.project_id)
    )
    if ctx.filters["phase_id"]:
        query = query.where(inventory.Building.phase_id == uuid.UUID(ctx.filters["phase_id"]))
    if ctx.filters["building_id"]:
        query = query.where(inventory.Building.id == uuid.UUID(ctx.filters["building_id"]))
    return list(session.scalars(query.order_by(inventory.Unit.id)))


def sales(session: Session, ctx: out.Context, unit_ids: list[uuid.UUID]) -> list[SaleContract]:
    cutoff = datetime.combine(ctx.as_of + timedelta(days=1), time(), UTC)
    return list(
        session.scalars(
            select(SaleContract).where(
                SaleContract.project_id == ctx.project_id,
                SaleContract.unit_id.in_(unit_ids),
                SaleContract.activated_at < cutoff,
                or_(
                    SaleContract.cancelled_at.is_(None),
                    SaleContract.cancelled_at
                    >= datetime.combine(
                        min(ctx.period_from, shift_month(ctx.as_of, -3)), time(), UTC
                    ),
                ),
            )
        )
    )


def money_buckets(rows: list[SaleContract], currencies: dict[uuid.UUID, str]) -> list[out.Money]:
    amounts: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        amounts[currencies[row.currency_id]] += row.total_contract_price
    return [out.Money(currency=code, amount=value) for code, value in sorted(amounts.items())]


def series(
    ctx: out.Context, rows: list[SaleContract], currencies: dict[uuid.UUID, str]
) -> list[out.Month]:
    result = []
    month = shift_month(ctx.period_from, 0)
    while month <= ctx.period_to:
        low, high = (
            max(month, ctx.period_from),
            min(shift_month(month, 1) - timedelta(days=1), ctx.period_to),
        )
        activated = [row for row in rows if low <= row.activated_at.astimezone(UTC).date() <= high]
        cancelled = [
            row
            for row in rows
            if row.cancelled_at and low <= row.cancelled_at.astimezone(UTC).date() <= high
        ]
        result.append(
            out.Month(
                month=month,
                activations=len(activated),
                cancellations=len(cancelled),
                net_absorption=len(activated) - len(cancelled),
                contracted_value=money_buckets(activated, currencies),
            )
        )
        month = shift_month(month, 1)
    return result


def area_lines(session: Session, unit_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    rows = session.execute(
        select(
            inventory.UnitAreaSchedule.unit_id,
            inventory.AreaType.physical_component,
            inventory.AreaType.unit_of_measure,
            inventory.UnitAreaValue.raw_area,
        )
        .join(
            inventory.UnitAreaValue,
            inventory.UnitAreaValue.unit_area_schedule_id == inventory.UnitAreaSchedule.id,
        )
        .join(inventory.AreaType, inventory.AreaType.id == inventory.UnitAreaValue.area_type_id)
        .where(
            inventory.UnitAreaSchedule.unit_id.in_(unit_ids),
            inventory.UnitAreaSchedule.status == "approved",
        )
    )
    result: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for unit_id, component, measure, raw in rows:
        result[unit_id].append(
            {"physical_component": component, "unit_of_measure": measure, "raw_area": raw}
        )
    return result


def fundamental(session: Session, project: Project, ctx: out.Context) -> out.Fundamental:
    population = units(session, ctx)
    ids = [unit.id for unit in population]
    eligible = [unit for unit in population if analysis_eligible(unit)]
    eligible_ids = {unit.id for unit in eligible}
    all_sales = sales(session, ctx, ids)
    currencies = dict(session.execute(select(Currency.id, Currency.code)).all())
    live_sales = [row for row in all_sales if standing(row, ctx.as_of)]
    period_sales = [
        row
        for row in live_sales
        if ctx.period_from <= row.activated_at.astimezone(UTC).date() <= ctx.period_to
    ]
    commitments = set(
        session.scalars(
            select(Reservation.unit_id).where(
                Reservation.project_id == project.id,
                Reservation.unit_id.in_(ids),
                Reservation.status.in_(RESERVATION_COMMITTED),
            )
        )
    ) | set(
        session.scalars(
            select(SaleContract.unit_id).where(
                SaleContract.project_id == project.id,
                SaleContract.unit_id.in_(ids),
                SaleContract.status.in_(SALE_COMMITTED),
            )
        )
    )
    committed = len(eligible_ids & commitments)
    remaining = len(eligible) - committed
    current = ctx.as_of == ctx.snapshot_as_of
    historic_reason = (
        None
        if current
        else (
            "Inventory and classification are current snapshots, not reconstructed "
            "historical positions."
        )
    )
    position = out.Position(
        availability="available" if current else "unavailable",
        reason=historic_reason,
        source_basis=POSITION_BASIS,
        sample_size=len(population),
        total_units=len(population),
        eligible_units=len(eligible),
        available_units=sum(
            unit.is_active and unit.commercial_status == "available" for unit in population
        ),
        committed_units=committed,
        active_sold_units=sum(
            row.status == "active" and row.unit_id in eligible_ids for row in live_sales
        ),
        remaining_units=remaining,
        commercial=dict(Counter(unit.commercial_status for unit in population)),
        legal=dict(Counter(unit.legal_status for unit in population)),
        delivery=dict(Counter(unit.delivery_status for unit in population)),
        penetration=ratio(
            committed if current else None, len(eligible) if current else None, POSITION_BASIS
        ),
    )
    net = []
    observed = 0
    for offset in (-3, -2, -1):
        low, high = shift_month(ctx.as_of, offset), shift_month(ctx.as_of, offset + 1)
        if project.created_at.astimezone(UTC).date() <= low:
            observed += 1
        net.append(
            sum(low <= row.activated_at.astimezone(UTC).date() < high for row in all_sales)
            - sum(
                bool(row.cancelled_at and low <= row.cancelled_at.astimezone(UTC).date() < high)
                for row in all_sales
            )
        )
    advisors = dict(
        session.execute(
            select(User.id, User.display_name).where(
                User.id.in_([row.advisor_user_id for row in period_sales if row.advisor_user_id])
            )
        ).all()
    )

    def ranking(attribute: str) -> list[out.Ranking]:
        grouped: dict[tuple[str, str], list[SaleContract]] = defaultdict(list)
        for row in period_sales:
            value = getattr(row, attribute)
            label = (
                advisors.get(value, "Unknown / Unassigned")
                if attribute == "advisor_user_id"
                else value or "Unknown / Unassigned"
            )
            grouped[(str(value) if value else "", label)].append(row)
        comparable = len({row.currency_id for row in period_sales}) <= 1
        ordered = sorted(
            grouped.items(),
            key=lambda item: (
                -len(item[1]),
                -sum((row.total_contract_price for row in item[1]), Decimal("0"))
                if comparable
                else Decimal("0"),
                item[0],
            ),
        )
        return [
            out.Ranking(
                source_key=source_key or None,
                label=label,
                sales_count=len(group),
                contracted_value=money_buckets(group, currencies),
                source_basis=(
                    f"SaleContract.{attribute}; standing activated sales in period. "
                    "Count descending, value only within one currency, then label."
                ),
                sample_size=len(group),
                share=ratio(len(group), len(period_sales), "Standing period sales"),
                availability="partial" if label == "Unknown / Unassigned" else "available",
                reason="Assignment not recorded on these sales."
                if label == "Unknown / Unassigned"
                else None,
            )
            for (source_key, label), group in ordered
        ]

    def demand(attribute: str) -> list[out.Demand]:
        grouped: dict[str, list[inventory.Unit]] = defaultdict(list)
        for unit in eligible:
            grouped[getattr(unit, attribute) or "Unknown / Unclassified"].append(unit)
        sold_ids = {row.unit_id for row in period_sales} & eligible_ids
        return [
            out.Demand(
                label=label,
                inventory_count=len(group),
                sales_count=len({unit.id for unit in group} & sold_ids),
                source_basis=(
                    f"Current eligible inventory {attribute}; "
                    "standing period sales on that same population."
                ),
                sample_size=len(group),
                demand_share=ratio(
                    len({unit.id for unit in group} & sold_ids),
                    len(sold_ids),
                    "Standing period sales on eligible inventory",
                ),
                penetration=ratio(
                    len({unit.id for unit in group} & sold_ids),
                    len(group),
                    "Eligible inventory of this classification",
                ),
                availability="available" if current else "partial",
                reason=historic_reason,
            )
            for label, group in sorted(grouped.items())
        ]

    lines = area_lines(session, ids)
    premiums = observed_premiums(eligible, period_sales, currencies, lines)
    known_views = sum(unit.view_class_code is not None for unit in eligible)
    return out.Fundamental(
        context=ctx,
        position=position,
        monthly_sales=series(ctx, all_sales, currencies),
        sales_basis=out.Availability(source_basis=SALES_BASIS, sample_size=len(all_sales)),
        branches=ranking("sales_branch_code"),
        salespeople=ranking("advisor_user_id"),
        ranking_basis=out.Availability(
            source_basis=(
                "Explicit SaleContract.sales_branch_code and advisor_user_id; no "
                "creator/client-owner inference."
            ),
            sample_size=len(period_sales),
        ),
        forecast=forecast(ctx.as_of, remaining if current and eligible else None, net, observed),
        property_types=demand("unit_type_code"),
        views=demand("view_class_code"),
        view_basis=out.Availability(
            source_basis="Unit.view_class_code. No feature-label or note inference.",
            sample_size=known_views,
            availability="available"
            if known_views == len(eligible) and known_views
            else "partial"
            if known_views
            else "unavailable",
            reason=None
            if known_views == len(eligible) and known_views
            else "Some or all eligible units have no recorded view class.",
        ),
        observed_premiums=premiums,
    )


def observed_premiums(
    population: list[inventory.Unit],
    rows: list[SaleContract],
    currencies: dict[uuid.UUID, str],
    lines: dict[uuid.UUID, list[dict]],
) -> list[out.Premium]:
    by_unit = {row.unit_id: row for row in rows}
    cohorts: dict[tuple[str, str], list[inventory.Unit]] = defaultdict(list)
    for unit in population:
        if unit.unit_type_code and unit.view_class_code:
            cohorts[(unit.unit_type_code, unit.view_class_code)].append(unit)
    result = []
    for (kind, view), group in sorted(cohorts.items()):
        targets = [unit for unit in group if unit.id in by_unit]
        baseline = [
            unit
            for unit in population
            if unit.unit_type_code == kind
            and unit.view_class_code
            and unit.view_class_code != view
            and unit.id in by_unit
        ]
        compared = targets + baseline
        measures = {unit.id: gross_measurement(lines.get(unit.id, [])) for unit in compared}
        codes = {by_unit[unit.id].currency_id for unit in compared}
        area_units = {value["gross_area_unit"] for value in measures.values()}
        reason = (
            "No sale in this view cohort or no same-type sale with a different recorded view."
            if not targets or not baseline
            else "Currencies differ; no FX conversion or aggregate premium."
            if len(codes) != 1
            else "Complete positive gross areas in the same measurement unit are required."
            if len(area_units) != 1
            or any(
                not value["gross_area"] or value["gross_area"] <= 0 for value in measures.values()
            )
            else None
        )

        def price_per_area(group: list[inventory.Unit], measurements: dict = measures) -> Decimal:
            return sum(
                (by_unit[unit.id].total_contract_price for unit in group), Decimal("0")
            ) / sum((measurements[unit.id]["gross_area"] for unit in group), Decimal("0"))

        target_price = price_per_area(targets) if reason is None else None
        base_price = price_per_area(baseline) if reason is None else None
        if base_price is not None and base_price <= 0:
            reason = "A positive comparable baseline price is required."
        result.append(
            out.Premium(
                property_type=kind,
                view=view,
                baseline=(
                    "Same property type, other explicitly recorded views; unknown views excluded."
                ),
                source_basis=(
                    "(sum contracted price / sum approved gross area in view cohort) / "
                    "(same metric in baseline) - 1, times 100. Descriptive observation "
                    "only."
                ),
                sample_size=len(targets),
                baseline_sample=len(baseline),
                availability="unavailable" if reason else "available",
                reason=reason,
                currency=currencies[next(iter(codes))] if len(codes) == 1 else None,
                area_unit=next(iter(area_units)) if len(area_units) == 1 else None,
                view_price_per_gross_area=rounded(target_price) if reason is None else None,
                baseline_price_per_gross_area=rounded(base_price) if reason is None else None,
                percentage=rounded((target_price / base_price - 1) * 100)
                if reason is None
                else None,
            )
        )
    return result


def financial(session: Session, project: Project, ctx: out.Context) -> out.Financial:
    currencies = dict(session.execute(select(Currency.id, Currency.code)).all())
    rows = sales(session, ctx, [unit.id for unit in units(session, ctx)])
    source_rows = cashflow.collect_source_rows(
        session, project=project, version=None, as_of=ctx.as_of
    )
    # Currency is attached from the original cash record, never guessed from project defaults.
    models = {
        cashflow.SOURCE_RECEIPT: CollectionReceipt,
        cashflow.SOURCE_REFUND: CollectionRefund,
        cashflow.SOURCE_CONSTRUCTION_PAYMENT: Payment,
        cashflow.SOURCE_DEVELOPMENT_MOVEMENT: cash_models.CashflowDevelopmentMovement,
        cashflow.SOURCE_FINANCING_MOVEMENT: cash_models.CashflowFinancingMovement,
    }
    denomination = {}
    for source, model in models.items():
        denomination[source] = dict(
            session.execute(
                select(model.id, model.currency_id).where(model.project_id == project.id)
            ).all()
        )
    buckets: dict[tuple[date, str], out.CashMonth] = {}
    codes = {ctx.currency} | {currencies[row.currency_id] for row in rows}
    actuals = [
        row
        for row in source_rows
        if row.source_type in models
        and row.basis == "actual"
        and ctx.period_from <= row.business_date <= ctx.period_to
    ]
    codes |= {currencies[denomination[row.source_type][row.source_id]] for row in actuals}
    for monthly in series(ctx, rows, currencies):
        for code in sorted(codes):
            sales_in_currency = [
                row
                for row in rows
                if currencies[row.currency_id] == code
                and max(ctx.period_from, monthly.month)
                <= row.activated_at.astimezone(UTC).date()
                <= min(ctx.period_to, shift_month(monthly.month, 1) - timedelta(days=1))
            ]
            buckets[(monthly.month, code)] = out.CashMonth(
                month=monthly.month,
                currency=code,
                new_sales_count=len(sales_in_currency),
                contracted_sales_value=sum(
                    (row.total_contract_price for row in sales_in_currency), Decimal("0")
                ),
            )
    for row in actuals:
        code = currencies[denomination[row.source_type][row.source_id]]
        bucket = buckets[(shift_month(row.business_date, 0), code)]
        if row.source_type == cashflow.SOURCE_RECEIPT:
            bucket.customer_cash_received += row.amount
        elif row.source_type == cashflow.SOURCE_REFUND:
            bucket.customer_refunds += row.amount
        elif row.source_type == cashflow.SOURCE_FINANCING_MOVEMENT:
            if row.flow_direction == "inflow":
                bucket.financing_inflow += row.amount
            else:
                bucket.financing_outflow += row.amount
        else:
            bucket.project_cash_outflow += row.amount
        bucket.net_actual_cash_movement += (
            row.amount if row.flow_direction == "inflow" else -row.amount
        )
    return out.Financial(
        context=ctx.model_copy(
            update={
                "source_basis": SALES_BASIS
                + " Confirmed actual cash uses Cashflow standing-as-of and business dates."
            }
        ),
        monthly=list(buckets.values()),
        cash_scope=(
            "Whole project cash. Phase/building filters affect sales only; project-"
            "level cash is never apportioned."
        ),
        basis=out.Availability(
            source_basis=(
                "Cashflow.collect_source_rows, confirmed standing actual "
                "receipts/refunds, development/construction payments and financing. "
                "Restrictions, forecasts, schedules, commissions and consultant "
                "agreements are not cash. Separate currencies; no FX. Contract value "
                "minus receipts is not overdue."
            ),
            sample_size=len(actuals),
        ),
    )


def technical(session: Session, project: Project, ctx: out.Context) -> out.Technical:
    population = [unit for unit in units(session, ctx) if unit.is_active]
    ids = [unit.id for unit in population]
    lines = area_lines(session, ids)
    grouped: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    gross_count = 0
    for unit_lines in lines.values():
        for line in unit_lines:
            if line["physical_component"]:
                grouped[(line["physical_component"], line["unit_of_measure"])].append(
                    line["raw_area"]
                )
        gross = gross_measurement(unit_lines)
        if gross["gross_area"] is not None:
            gross_count += 1
            grouped[("gross", gross["gross_area_unit"])].append(gross["gross_area"])
    areas = [
        out.Area(
            component=component,
            unit_of_measure=measure,
            minimum=min(values),
            maximum=max(values),
            average=rounded(sum(values) / Decimal(len(values))),
            sample_size=len(values),
            source_basis=(
                "Current approved area schedule; gross sums six physical components and"
                " excludes parking/storage."
            ),
        )
        for (component, measure), values in sorted(grouped.items())
    ]
    features = session.execute(
        select(
            inventory.UnitFeature.label, func.count(func.distinct(inventory.UnitFeature.unit_id))
        )
        .where(inventory.UnitFeature.unit_id.in_(ids), inventory.UnitFeature.is_active.is_(True))
        .group_by(inventory.UnitFeature.label)
    ).all()
    feature_units = (
        session.scalar(
            select(func.count(func.distinct(inventory.UnitFeature.unit_id))).where(
                inventory.UnitFeature.unit_id.in_(ids), inventory.UnitFeature.is_active.is_(True)
            )
        )
        or 0
    )
    attachments = Counter()
    for counts in sub_asset_counts(session, unit_ids=ids).values():
        attachments.update(counts)
    permits = dict(
        session.execute(
            select(Permit.status, func.count())
            .where(Permit.project_id == project.id)
            .group_by(Permit.status)
        ).all()
    )
    workspace = consultant.workspace(session, project)
    active = workspace.active_engagement
    stages = list(
        session.scalars(
            select(ConstructionStage)
            .where(ConstructionStage.project_id == project.id)
            .order_by(ConstructionStage.sequence)
        )
    )
    latest = (
        select(
            UnitStageEvent.stage_id,
            UnitStageEvent.unit_id,
            UnitStageEvent.completed_date,
            func.row_number()
            .over(
                partition_by=(UnitStageEvent.unit_id, UnitStageEvent.stage_id),
                order_by=UnitStageEvent.sequence.desc(),
            )
            .label("rn"),
        )
        .where(UnitStageEvent.project_id == project.id, UnitStageEvent.unit_id.in_(ids))
        .subquery()
    )
    counts = dict(
        session.execute(
            select(latest.c.stage_id, func.count())
            .where(
                latest.c.rn == 1,
                latest.c.completed_date.is_not(None),
                latest.c.completed_date <= ctx.snapshot_as_of,
            )
            .group_by(latest.c.stage_id)
        ).all()
    )
    return out.Technical(
        context=ctx.model_copy(
            update={
                "source_basis": (
                    "Current approved Inventory physical facts; separate Permit, "
                    "Consultant and Construction context."
                )
            }
        ),
        basis=out.Availability(
            availability="partial",
            reason=(
                "Recorded technical product profile; no explicit buyer-issued "
                "specification provenance is stored. Current snapshot, not historical "
                "reconstruction."
            ),
            source_basis=(
                "Inventory physical product facts. Permit, consultant and construction "
                "context are whole project and separate dimensions."
            ),
            sample_size=len(population),
        ),
        product_types=dict(
            Counter(unit.unit_type_code or "Unknown / Unclassified" for unit in population)
        ),
        areas=areas,
        area_coverage=out.Availability(
            availability="available"
            if gross_count == len(population) and gross_count
            else "partial"
            if gross_count
            else "unavailable",
            reason=None
            if gross_count == len(population) and gross_count
            else "Some or all units lack a complete approved six-component gross area.",
            source_basis="Approved six-component gross area coverage",
            sample_size=gross_count,
        ),
        features=dict(features),
        feature_coverage=ratio(
            feature_units,
            len(population),
            "Active units with an active recorded feature / active units in scope",
        ),
        attachments=dict(attachments),
        permits=permits,
        permit_basis=out.Availability(
            availability="available" if permits else "unavailable",
            reason=None if permits else "No permits recorded.",
            source_basis="Whole-project Permit statutory status; issued means Obtained / Issued.",
            sample_size=sum(permits.values()),
        ),
        consultant={
            "active_consultant": active.consultant_name if active else None,
            "accepted_deliverables": workspace.accepted_deliverables,
            "outstanding_deliverables": workspace.outstanding_deliverables,
            "design_stages": workspace.total_stages,
            "current_design_stage": next(
                (
                    stage.name
                    for stage in workspace.stages
                    if active
                    and stage.engagement_id == active.id
                    and stage.status in {"in_progress", "on_hold", "not_started"}
                ),
                None,
            ),
        },
        consultant_basis=out.Availability(
            availability="available" if workspace.engagements else "unavailable",
            reason=None if workspace.engagements else "No consultant agreement recorded.",
            source_basis=(
                "Whole-project Consultant workspace, retained history included. Design "
                "submission is not physical completion."
            ),
            sample_size=len(workspace.engagements),
        ),
        construction_stages=[
            {
                "name": stage.name,
                "completed_units": counts.get(stage.id, 0),
                "denominator": len(population),
            }
            for stage in stages
        ],
        construction_basis=out.Availability(
            availability="available" if stages else "unavailable",
            reason=None if stages else "No construction stages configured.",
            source_basis=(
                "Latest unit construction-stage event; corrections retained. "
                "Independent from design stages."
            ),
            sample_size=len(stages),
        ),
    )
