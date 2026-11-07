"""Read-only Reports composition over existing owner calculations.

Current positions and period flows are deliberately labelled separately. No FX,
cash estimation, persisted reports or mutation of source records.
"""

from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.modules.collections.batch import CollectionsPosition
from app.modules.collections.batch import positions as collection_positions
from app.modules.construction.batch import ConstructionPosition
from app.modules.construction.batch import positions as construction_positions
from app.modules.inventory.models import Unit
from app.modules.project_analysis import service
from app.modules.project_analysis.report_schemas import AnalyticsReport, Chart, Metric, Point
from app.modules.projects.models import Project
from app.modules.sales.batch import standing
from app.modules.sales.models import Client
from app.modules.settings.models import Currency

ZERO = Decimal(0)


def chart(
    key: str,
    title: str,
    category: str,
    values: list[tuple[str, Decimal | int | None]],
    source: str,
    *,
    unit: str = "units",
    kind: str = "bars",
    note: str | None = None,
    insight: str | None = None,
) -> Chart:
    """Normalize geometry only; missing values stay missing, zero stays zero."""
    if len(values) > 10 and key in {"agents", "branches", "advisors", "product"}:
        ordered = sorted(values, key=lambda item: -(item[1] or ZERO))
        values = [
            *ordered[:9],
            (
                "All other groups",
                sum((Decimal(value) for _, value in ordered[9:] if value is not None), ZERO),
            ),
        ]
        note = "Nine leading groups shown; remaining groups combined without dropping counts."
    known = [(label, Decimal(value)) for label, value in values if value is not None]
    maximum = max((abs(value) for _, value in known), default=ZERO)
    total = sum((value for _, value in known), ZERO)
    points = [
        Point(
            label=label,
            value=value,
            scale_percentage=(abs(Decimal(value)) / maximum * 100).quantize(Decimal("0.01"))
            if maximum and value is not None
            else ZERO,
            share_percentage=(Decimal(value) / total * 100).quantize(Decimal("0.0001"))
            if total > 0 and value is not None and all(amount >= 0 for _, amount in known)
            else None,
        )
        for label, value in values
    ]
    if insight is None:
        if not known:
            insight = "No recorded values are available for this view."
        elif not maximum:
            insight = "All recorded values in this view are zero."
        else:
            label, value = max(known, key=lambda item: item[1])
            insight = f"{label} has the highest recorded value: {value:,.2f} {unit}."
    return Chart(
        key=key,
        title=title,
        category=category,
        kind=kind,
        unit=unit,
        points=points,
        source=source,
        note=note,
        insight=insight,
    )


def read(
    session: Session,
    project: Project,
    period_from: date | None,
    period_to: date | None,
    threshold: Decimal,
    currency: str | None,
) -> AnalyticsReport:
    ctx = service.context(session, project, None, period_from, period_to, None, None)
    code = currency or ctx.currency
    currencies = dict(session.execute(select(Currency.id, Currency.code)).all())
    if code not in currencies.values():
        raise ValidationError("Choose a registered currency code.")
    currency_id = next(identifier for identifier, value in currencies.items() if value == code)
    fundamental = service.fundamental(session, project, ctx)
    financial = service.financial(session, project, ctx)
    technical = service.technical(session, project, ctx)
    population = list(
        session.scalars(
            select(Unit).where(
                Unit.project_id == project.id,
                Unit.is_active.is_(True),
            )
        )
    )
    rows = service.sales(session, ctx, [unit.id for unit in population])
    live = [row for row in rows if standing(row, ctx.as_of)]
    period = [
        row
        for row in live
        if ctx.period_from <= row.activated_at.astimezone(UTC).date() <= ctx.period_to
    ]
    comparable = [row for row in period if row.currency_id == currency_id]
    sold_ids = {row.unit_id for row in live}
    available = sum(unit.commercial_status == "available" for unit in population)
    states = Counter(unit.commercial_status for unit in population)
    threshold_counts = [
        ("Above threshold", sum(row.net_contract_price_ex_tax > threshold for row in comparable)),
        ("At threshold", sum(row.net_contract_price_ex_tax == threshold for row in comparable)),
        ("Below threshold", sum(row.net_contract_price_ex_tax < threshold for row in comparable)),
    ]
    project_ids = select(Project.id).where(Project.id == project.id)
    collections = collection_positions(session, project_ids, ctx.as_of).get(
        project.id, CollectionsPosition()
    )
    costs = construction_positions(session, project_ids).get(project.id, ConstructionPosition())
    cash = [row for row in financial.monthly if row.currency == code]
    received = sum((row.customer_cash_received for row in cash), ZERO)
    outflow = sum((row.project_cash_outflow for row in cash), ZERO)
    charts = [
        chart(
            "sales-value",
            "Monthly contracted sales value",
            "Sales",
            [(row.month.strftime("%b %Y"), row.contracted_sales_value) for row in cash],
            service.SALES_BASIS,
            unit=code,
            kind="columns",
            insight=(
                "Gross value of contracts activated in each month, including tax and fees. "
                "Later cancellations are not netted here; this is contracted value, not cash."
            ),
        ),
        chart(
            "inventory",
            "Inventory at a glance",
            "Sales",
            sorted(states.items()),
            "Inventory · current active primary units; attached parking/storage excluded.",
            kind="donut",
            insight=(
                f"{len(sold_ids)} units have standing activated sales; {available} "
                f"units are marked available. Reservations and unsigned sales remain "
                f"distinct."
            ),
        ),
        chart(
            "sales-trend",
            "Monthly sales momentum",
            "Sales",
            [(row.month.strftime("%b %Y"), row.activations) for row in fundamental.monthly_sales],
            service.SALES_BASIS,
            kind="columns",
            insight=(
                f"{sum(row.activations for row in fundamental.monthly_sales)} "
                f"activations and "
                f"{sum(row.cancellations for row in fundamental.monthly_sales)} "
                f"cancellations occurred in the period. Activations are gross, "
                f"including deals later cancelled."
            ),
        ),
        chart(
            "net-sales",
            "Net absorption",
            "Sales",
            [
                (row.month.strftime("%b %Y"), row.net_absorption)
                for row in fundamental.monthly_sales
            ],
            "Sales · monthly activations minus cancellations of previously activated contracts.",
            kind="columns",
        ),
        chart(
            "threshold",
            "Sales above your price threshold",
            "Sales",
            threshold_counts,
            (
                "Sales · standing activated period sales; net contract price "
                "excluding tax; selected currency only."
            ),
            kind="donut",
            insight=(
                f"{threshold_counts[0][1]} of {len(comparable)} comparable sales "
                f"exceed {threshold:,.2f} {code}. Exactly equal prices appear "
                f"separately."
            ),
            note=(
                f"{len(period) - len(comparable)} standing period sales in other "
                f"currencies excluded. No exchange conversion."
            ),
        ),
        chart(
            "price-achievement",
            "Achieved price versus reference",
            "Sales",
            [
                (
                    "Above reference",
                    sum(
                        row.net_contract_price_ex_tax > row.reference_price_ex_tax
                        for row in comparable
                    ),
                ),
                (
                    "At reference",
                    sum(
                        row.net_contract_price_ex_tax == row.reference_price_ex_tax
                        for row in comparable
                    ),
                ),
                (
                    "Below reference",
                    sum(
                        row.net_contract_price_ex_tax < row.reference_price_ex_tax
                        for row in comparable
                    ),
                ),
            ],
            (
                "Sales · frozen reference and net contract price excluding tax; "
                "standing period sales in selected currency."
            ),
        ),
        chart(
            "product",
            "Demand by property type",
            "Sales",
            [(row.label, row.sales_count) for row in fundamental.property_types],
            (
                "Analysis · standing period sales on eligible inventory, grouped by "
                "current unit type."
            ),
        ),
        chart(
            "agents",
            "Agent performance",
            "People",
            list(Counter(row.agent_name or "Unassigned" for row in period).most_common()),
            (
                "Sales · frozen agent_name attribution on standing activated period "
                "contracts; grouped by recorded name; no buyer-country inference."
            ),
            unit="sales",
        ),
        chart(
            "branches",
            "Sales by agent branch",
            "People",
            list(Counter(row.agent_branch or "Unassigned" for row in period).most_common()),
            "Sales · frozen agent_branch attribution on standing activated period contracts.",
            unit="sales",
        ),
        chart(
            "advisors",
            "Advisor performance",
            "People",
            [(row.label, row.sales_count) for row in fundamental.salespeople],
            fundamental.ranking_basis.source_basis,
            unit="sales",
        ),
    ]
    buyers = list(
        session.scalars(
            select(Client).where(Client.project_id == project.id, Client.is_active.is_(True))
        )
    )
    purchases = Counter(row.client_id for row in live)
    charts.extend(
        [
            chart(
                "buyers",
                "Buyer portfolio",
                "People",
                [
                    ("One purchased unit", sum(value == 1 for value in purchases.values())),
                    ("Multiple purchased units", sum(value > 1 for value in purchases.values())),
                ],
                (
                    "Sales · distinct client records with standing activated sales on "
                    "active primary units; not individual legal parties."
                ),
                unit="buyers",
                kind="donut",
                insight=(
                    f"{len(purchases)} buyer records hold standing activated purchases. "
                    f"{sum(value > 1 for value in purchases.values())} have more than one "
                    f"purchased unit."
                ),
            ),
            chart(
                "kyc",
                "Buyer onboarding readiness",
                "People",
                sorted(Counter(row.kyc_status for row in buyers).items()),
                "Buyers · all current active client records, including buyers without purchases.",
                unit="buyers",
            ),
            chart(
                "cash-in",
                "Monthly customer collections",
                "Cash & cost",
                [(row.month.strftime("%b %Y"), row.customer_cash_received) for row in cash],
                financial.basis.source_basis,
                unit=code,
                kind="columns",
                insight=(
                    f"Confirmed customer receipts total {received:,.2f} {code} in the "
                    f"selected period. These are gross cash receipts, not net sales "
                    f"revenue."
                ),
            ),
            chart(
                "cash-out",
                "Monthly development spending",
                "Cash & cost",
                [(row.month.strftime("%b %Y"), row.project_cash_outflow) for row in cash],
                financial.basis.source_basis,
                unit=code,
                kind="columns",
                insight=(
                    f"Confirmed development and construction cash outflow is "
                    f"{outflow:,.2f} {code}. Refunds and financing are reported "
                    f"separately."
                ),
            ),
            chart(
                "cash-bridge",
                "Cash movement components",
                "Cash & cost",
                [
                    ("Customer receipts", received),
                    ("Development outflow", -outflow),
                    ("Customer refunds", -sum((row.customer_refunds for row in cash), ZERO)),
                    ("Financing inflow", sum((row.financing_inflow for row in cash), ZERO)),
                    ("Financing outflow", -sum((row.financing_outflow for row in cash), ZERO)),
                    ("Net movement", sum((row.net_actual_cash_movement for row in cash), ZERO)),
                ],
                financial.basis.source_basis,
                unit=code,
                insight=(
                    "Positive values are inflows; negative values are outflows. Net "
                    "movement is the combined movement, not an opening or closing bank "
                    "balance."
                ),
            ),
            chart(
                "collections-position",
                "Collections control position",
                "Cash & cost",
                [
                    ("Confirmed receipts", collections.confirmed.get(currency_id, ZERO)),
                    ("Unapplied receipts", collections.unapplied.get(currency_id, ZERO)),
                    (
                        "Overdue installments",
                        None
                        if currency_id in collections.unavailable_overdue_currencies
                        else collections.overdue.get(currency_id, ZERO),
                    ),
                    ("Refunds outstanding", collections.refund_outstanding.get(currency_id, ZERO)),
                ],
                (
                    "Collections · current owner ledger totals in selected currency. "
                    "Measures overlap and must not be added."
                ),
                unit=code,
                note=(
                    f"{collections.missing_schedules} activated sales lack schedules; "
                    f"{collections.undated_installments} outstanding installments lack "
                    f"due dates."
                ),
                insight=(
                    "Overdue comes from due installments and applied receipts. Unapplied "
                    "receipts remain separate; contract value less cash is not arrears."
                ),
            ),
            chart(
                "construction-cost",
                "Construction cost control",
                "Cash & cost",
                [
                    (
                        "Control budget",
                        costs.control_budget if costs.budget_currency == currency_id else None,
                    ),
                    ("Revised commitments", costs.revised_commitment.get(currency_id)),
                    (
                        "Estimate at completion",
                        costs.eac if costs.forecast_currency == currency_id else None,
                    ),
                ],
                (
                    "Construction · current active budget, committing contracts with "
                    "approved variations, and active forecast; excluding tax."
                ),
                unit=code,
                note=costs.eac_reason or None,
                insight=(
                    "Budget, contractual commitments and forecast are separate cost "
                    "measures, not additive. Missing or different-currency sources "
                    "remain unavailable."
                ),
            ),
            chart(
                "permits",
                "Permit readiness",
                "Delivery",
                sorted(technical.permits.items()),
                technical.permit_basis.source_basis,
                unit="permits",
                kind="donut",
                note=technical.permit_basis.reason,
            ),
            chart(
                "stages",
                "Construction stage completion",
                "Delivery",
                [
                    (str(row["name"]), int(row["completed_units"]))
                    for row in technical.construction_stages
                ],
                technical.construction_basis.source_basis,
                note=technical.construction_basis.reason,
                insight=(
                    "Each bar counts units with a recorded completed stage. A unit can "
                    "appear in several stages; this is not a certified financial "
                    "completion percentage."
                ),
            ),
            chart(
                "delivery",
                "Unit delivery position",
                "Delivery",
                sorted(Counter(unit.delivery_status for unit in population).items()),
                "Inventory · current active primary unit delivery states.",
                kind="donut",
            ),
        ]
    )
    return AnalyticsReport(
        project_name=project.name,
        generated_at=datetime.now(UTC),
        context=ctx,
        threshold=threshold,
        currency=code,
        metrics=[
            Metric(
                label="Active inventory",
                value=len(population),
                unit="units",
                note="Current primary units",
            ),
            Metric(
                label="Sold", value=len(sold_ids), unit="units", note="Standing activated sales"
            ),
            Metric(
                label="Available", value=available, unit="units", note="Current available status"
            ),
            Metric(
                label="Above threshold",
                value=threshold_counts[0][1],
                unit="sales",
                note=f"Standing period sales · {code} · ex-tax",
            ),
            Metric(
                label="Period collections",
                value=received,
                unit=code,
                note="Confirmed gross customer receipts",
            ),
        ],
        charts=charts,
        notices=[
            (
                "Current positions use today's records; the selected period applies "
                "to sales activity and cash flows only. This is not a historical "
                "snapshot."
            ),
            (
                "Sold means activated and not cancelled as of today. Reservations "
                "and unsigned buyer registrations are not activated sales."
            ),
            (
                "Money charts and price thresholds use the selected original "
                "currency. Counts cover all currencies unless explicitly labelled "
                "otherwise; no FX is applied."
            ),
            (
                "Read from current system records. Empty charts mean no matching "
                "records, not independently verified absence of business activity. "
                "Refresh before issuing to management."
            ),
        ],
    )
