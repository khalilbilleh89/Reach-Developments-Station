"""Cashflow-owned batch composition and denomination refusal.

No consumer reconstructs cash. This module loads sources in fixed queries and
uses the same source assembly, opening anchor, bridge and deficit calculations
as Cashflow's project report. Incompatible sources invalidate the whole balance.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.standing import as_of_bound, standing_conditions
from app.modules.cashflow import calculator
from app.modules.cashflow import models as m
from app.modules.cashflow import service as owner
from app.modules.collections import service as collections
from app.modules.collections.models import CollectionReceipt, CollectionReceiptAllocation
from app.modules.construction import service as construction
from app.modules.construction.models import ForecastVersion as ConstructionForecast
from app.modules.payment_plans.models import PaymentPlan, PaymentPlanVersion
from app.modules.projects.models import Project
from app.modules.sales.models import SaleContract


@dataclass
class CashPosition:
    governing_currency: uuid.UUID
    observed_currencies: set[uuid.UUID] = field(default_factory=set)
    reason: str | None = None
    reason_code: str | None = None
    total_cash: Decimal | None = None
    restricted_cash: Decimal | None = None
    unrestricted_cash: Decimal | None = None
    peak_deficit: Decimal | None = None
    forecast_id: uuid.UUID | None = None
    forecast_reason: str | None = None
    forecast_as_of: date | None = None
    forecast_end_month: date | None = None
    projected_months: list[tuple[date, Decimal]] = field(default_factory=list)


@dataclass(frozen=True)
class HorizonPosition:
    lowest_unrestricted_cash: Decimal | None
    lowpoint_month: date | None
    first_deficit_month: date | None
    peak_deficit: Decimal | None
    reason: str | None


def horizon_position(position: CashPosition, as_of: date, horizon_end: date) -> HorizonPosition:
    """Monthly bridge observations in intersecting calendar months, never prorated.

    A partial last month includes that month's governed closing position. This
    is a monthly forecast outlook, not the separate daily funding-window report.
    """
    if position.forecast_reason:
        return HorizonPosition(None, None, None, None, position.forecast_reason)
    months = [
        (month, value)
        for month, value in position.projected_months
        if owner.month_of(as_of) <= month <= owner.month_of(horizon_end)
    ]
    if not months:
        return HorizonPosition(
            None, None, None, None, "No governed forecast months in this horizon."
        )
    month, amount = min(months, key=lambda item: (item[1], item[0]))
    first = next((month for month, value in months if value < 0), None)
    peak = calculator.peak_deficit(months).peak_funding_deficit
    return HorizonPosition(amount, month, first, peak, None)


def _group(rows: Sequence, key: str = "project_id") -> dict[uuid.UUID, list]:
    result: dict[uuid.UUID, list] = {}
    for row in rows:
        result.setdefault(getattr(row, key), []).append(row)
    return result


def _standing(model: type, as_of: date) -> list:
    return standing_conditions(
        status=model.status,
        confirmed_at=model.confirmed_at,
        reversed_at=model.reversed_at,
        as_of=as_of,
    )


def positions(session: Session, project_ids: Select, as_of: date) -> dict[uuid.UUID, CashPosition]:
    projects = list(session.scalars(select(Project).where(Project.id.in_(project_ids))))
    versions = {
        row.project_id: row
        for row in session.scalars(
            select(m.CashflowForecastVersion).where(
                m.CashflowForecastVersion.project_id.in_(project_ids),
                m.CashflowForecastVersion.status == m.FORECAST_ACTIVE,
            )
        )
    }
    version_ids = [row.id for row in versions.values()]
    receipts = _group(
        collections.cashflow_receipt_rows(session, project_ids=project_ids, as_of=as_of)
    )
    refunds = _group(
        collections.cashflow_refund_rows(session, project_ids=project_ids, as_of=as_of)
    )
    payments = _group(
        construction.cashflow_payment_rows(session, project_ids=project_ids, as_of=as_of)
    )
    development = _group(
        list(
            session.scalars(
                select(m.CashflowDevelopmentMovement).where(
                    m.CashflowDevelopmentMovement.project_id.in_(project_ids),
                    *_standing(m.CashflowDevelopmentMovement, as_of),
                )
            )
        )
    )
    financing = _group(
        list(
            session.scalars(
                select(m.CashflowFinancingMovement).where(
                    m.CashflowFinancingMovement.project_id.in_(project_ids),
                    *_standing(m.CashflowFinancingMovement, as_of),
                )
            )
        )
    )
    restrictions: dict[uuid.UUID, list] = {}
    for row, receipt_date, reference in session.execute(
        select(
            m.CashflowReceiptRestriction,
            CollectionReceipt.receipt_date,
            CollectionReceipt.receipt_number,
        )
        .join(CollectionReceipt, CollectionReceipt.id == m.CashflowReceiptRestriction.receipt_id)
        .where(
            m.CashflowReceiptRestriction.project_id.in_(project_ids),
            *_standing(m.CashflowReceiptRestriction, as_of),
            *_standing(CollectionReceipt, as_of),
        )
    ):
        restrictions.setdefault(row.project_id, []).append((row, receipt_date, reference))
    releases = _group(
        list(
            session.scalars(
                select(m.CashflowRestrictionRelease)
                .join(
                    m.CashflowReceiptRestriction,
                    m.CashflowReceiptRestriction.id == m.CashflowRestrictionRelease.restriction_id,
                )
                .join(
                    CollectionReceipt,
                    CollectionReceipt.id == m.CashflowReceiptRestriction.receipt_id,
                )
                .where(
                    m.CashflowRestrictionRelease.project_id.in_(project_ids),
                    *_standing(m.CashflowRestrictionRelease, as_of),
                    *_standing(m.CashflowReceiptRestriction, as_of),
                    *_standing(CollectionReceipt, as_of),
                )
            )
        )
    )
    snapshot = _group(
        list(
            session.scalars(
                select(m.CashflowCustomerScheduleSnapshot)
                .where(
                    m.CashflowCustomerScheduleSnapshot.project_id.in_(project_ids),
                    m.CashflowCustomerScheduleSnapshot.forecast_version_id.in_(version_ids),
                )
                .order_by(m.CashflowCustomerScheduleSnapshot.chosen_forecast_date)
            )
        )
    )
    lines = _group(
        list(
            session.scalars(
                select(m.CashflowForecastLine).where(
                    m.CashflowForecastLine.project_id.in_(project_ids),
                    m.CashflowForecastLine.forecast_version_id.in_(version_ids),
                )
            )
        )
    )
    allocations = _group(
        list(
            session.scalars(
                select(CollectionReceiptAllocation).where(
                    CollectionReceiptAllocation.project_id.in_(project_ids),
                    collections._allocation_effective_on(as_of),
                )
            )
        )
    )
    sale_currencies = dict(
        session.execute(
            select(SaleContract.id, SaleContract.currency_id).where(
                SaleContract.project_id.in_(project_ids)
            )
        ).all()
    )
    construction_versions = list(
        session.scalars(
            select(ConstructionForecast).where(
                ConstructionForecast.project_id.in_(project_ids),
                or_(
                    ConstructionForecast.status == "active",
                    ConstructionForecast.id.in_(
                        [row.construction_forecast_version_id for row in versions.values()]
                    ),
                ),
            )
        )
    )
    current_construction = {
        row.project_id: row for row in construction_versions if row.status == "active"
    }
    pinned_construction = {row.id: row for row in construction_versions}
    plans = _group(
        list(
            session.scalars(
                select(PaymentPlanVersion)
                .join(PaymentPlan, PaymentPlan.id == PaymentPlanVersion.payment_plan_id)
                .where(PaymentPlan.project_id.in_(project_ids))
            )
        )
    )
    result: dict[uuid.UUID, CashPosition] = {}
    for project in projects:
        pid = project.id
        version = versions.get(pid)
        target = CashPosition(project.base_currency_id, forecast_id=version.id if version else None)
        if version:
            target.forecast_as_of = version.as_of_date
            target.forecast_end_month = version.forecast_end_month
        result[pid] = target
        target.observed_currencies = {
            row.currency_id
            for rows in (receipts, refunds, payments, development, financing)
            for row in rows.get(pid, [])
        }
        if version:
            target.observed_currencies.add(version.currency_id)
            pinned_cost = pinned_construction.get(version.construction_forecast_version_id)
            if pinned_cost is not None:
                target.observed_currencies.add(pinned_cost.currency_id)
            target.observed_currencies.update(
                sale_currencies[row.sale_contract_id] for row in snapshot.get(pid, [])
            )
        if target.observed_currencies - {project.base_currency_id}:
            target.reason_code = "cashflow_currency_mismatch"
            target.reason = "Cashflow source currencies cannot be combined without governed FX."
            target.forecast_reason = target.reason
            continue
        # Offset once by the same sale, with original owner lifecycle conditions.
        unapplied: dict[uuid.UUID, Decimal] = {}
        for row in receipts.get(pid, []):
            unapplied[row.sale_contract_id] = (
                unapplied.get(row.sale_contract_id, Decimal(0)) + row.amount
            )
        for row in allocations.get(pid, []):
            unapplied[row.sale_contract_id] = (
                unapplied.get(row.sale_contract_id, Decimal(0)) - row.amount
            )
        unapplied = {key: value for key, value in unapplied.items() if value > 0}
        matched: dict[tuple[date, str, object, object], Decimal] = {}
        unattributed: dict[date, Decimal] = {}
        if version:
            for row in payments.get(pid, []):
                if row.business_date > version.as_of_date:
                    month = owner.month_of(row.business_date)
                    for code, amount in row.by_cost_code.items():
                        key = (month, owner.GRAIN_CONSTRUCTION, code, None)
                        matched[key] = matched.get(key, Decimal(0)) + amount
                    unattributed[month] = (
                        unattributed.get(month, Decimal(0)) + row.unattributed_amount
                    )
            for row in development.get(pid, []):
                if row.movement_date > version.as_of_date:
                    key = (
                        owner.month_of(row.movement_date),
                        owner.GRAIN_DEVELOPMENT,
                        row.category,
                        row.phase_id,
                    )
                    matched[key] = matched.get(key, Decimal(0)) + row.amount
            for row in financing.get(pid, []):
                if row.movement_date > version.as_of_date:
                    key = (
                        owner.month_of(row.movement_date),
                        owner.GRAIN_FINANCING,
                        row.movement_type,
                        row.flow_direction,
                    )
                    matched[key] = matched.get(key, Decimal(0)) + row.amount
        remainders = owner.remaining_forecast_amounts(lines.get(pid, []), matched, unattributed)
        sources = owner.assemble_source_rows(
            version=version,
            as_of=as_of,
            receipts=receipts.get(pid, []),
            refunds=refunds.get(pid, []),
            payments=payments.get(pid, []),
            development=development.get(pid, []),
            financing=financing.get(pid, []),
            restrictions=restrictions.get(pid, []),
            releases=releases.get(pid, []),
            snapshot=snapshot.get(pid, []),
            lines=lines.get(pid, []),
            unapplied=unapplied,
            remainders=remainders,
        )
        held = owner.actual_cash_position(sources, version=version, as_of=as_of)
        target.total_cash, target.restricted_cash, target.unrestricted_cash = (
            held.total_cash,
            held.restricted_cash,
            held.unrestricted_cash,
        )
        if version is None:
            target.forecast_reason = "No active Cashflow forecast."
            continue
        current = current_construction.get(pid)
        bound = as_of_bound(version.as_of_date)
        governing = {
            row.id
            for row in plans.get(pid, [])
            if row.activated_at is not None
            and row.activated_at < bound
            and (row.superseded_at is None or row.superseded_at >= bound)
        }
        pinned = {row.payment_plan_version_id for row in snapshot.get(pid, [])}
        if (
            current is not None and current.id != version.construction_forecast_version_id
        ) or pinned != governing:
            target.forecast_reason = "Active Cashflow forecast has stale source versions."
        elif version.forecast_end_month < owner.month_of(as_of):
            target.forecast_reason = "Active Cashflow forecast horizon has ended."
        else:
            bridge = owner.positions_from_rows(sources, version=version, as_of=as_of)
            target.projected_months = [
                (row.period_month, row.closing_unrestricted_cash) for row in bridge
            ]
            target.peak_deficit = calculator.peak_deficit(
                [(row.period_month, row.closing_unrestricted_cash) for row in bridge]
            ).peak_funding_deficit
    return result
