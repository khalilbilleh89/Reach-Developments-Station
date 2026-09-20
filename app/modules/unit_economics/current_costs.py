"""Live contract-based unit costs, separate from historical allocation snapshots."""

from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.commissions.service import current_unit_cost_grants
from app.modules.construction.service import current_unit_cost_sources
from app.modules.inventory.custom_fields import business_today
from app.modules.inventory.models import AreaType, Building, Floor, Unit
from app.modules.inventory.physical import approved_gross_built_areas
from app.modules.projects.land_analytics import complete_project_acquisition_cost
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import service as sales_service
from app.modules.sales.models import SaleContract
from app.modules.settings.models import Currency
from app.modules.unit_economics import permissions, service
from app.modules.unit_economics.calculator import ZERO, DriverLine, allocate, money
from app.modules.unit_economics.current_schemas import (
    CostFigures,
    CostSettingsRead,
    CostSettingsWrite,
    CostSource,
    CurrentCostAnalysis,
    CurrentCostGroup,
    CurrentUnitCost,
)
from app.modules.unit_economics.models import (
    CLASS_DIRECT,
    UNIT_COST_CLASS_OF,
    CurrentCostSettings,
    UnitCost,
)

SHARED = ("hard_cost", "land_cost", "soft_cost", "additional_cost", "finance_cost")
COSTS = (*SHARED, "direct_cost", "seller_cost", "commission_cost")
COMMISSION_TYPES = {"sales_commission", "branch_commission"}


def settings(session: Session, project_id: uuid.UUID) -> CurrentCostSettings | None:
    return session.get(CurrentCostSettings, project_id)


def write_settings(
    session: Session, *, project: Project, actor: ActorContext, payload: CostSettingsWrite
) -> None:
    permissions.require_economics_writer(actor)
    permissions.require_whole_project_scope(session, project_id=project.id, actor=actor)
    if not payload.reason.strip():
        raise ValidationError("Enter why the analysis inputs are changing.")
    lock_project(session, project.id)
    row = settings(session, project.id)
    if (row.revision if row else 0) != payload.expected_revision:
        raise ConflictError("The analysis settings changed. Refresh before saving.")
    area = session.scalar(
        select(AreaType).where(
            AreaType.id == payload.gross_area_type_id,
            AreaType.project_id == project.id,
            AreaType.area_role == "gross",
            AreaType.is_active.is_(True),
        )
    )
    if area is None or area.unit_of_measure not in {"sqm", "sqft"}:
        raise ValidationError("Choose an active gross-built area type measured in sqm or sqft.")
    before = CostSettingsRead.model_validate(row).model_dump(mode="json") if row else None
    if row is not None and row.currency_id != project.base_currency_id:
        raise ConflictError("Delete the old-currency inputs before recording a new currency basis.")
    if row is None:
        row = CurrentCostSettings(
            project_id=project.id, currency_id=project.base_currency_id, revision=0
        )
        session.add(row)
    for key, value in payload.model_dump(exclude={"expected_revision", "reason"}).items():
        setattr(row, key, value)
    row.revision += 1
    session.flush()
    record_event(
        session,
        action="unit_economics.current_settings_written",
        entity_type="unit_cost_analysis",
        entity_id=project.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=payload.reason.strip(),
        before=before,
        after=CostSettingsRead.model_validate(row).model_dump(mode="json"),
    )


def delete_settings(
    session: Session, *, project: Project, actor: ActorContext, revision: int, reason: str
) -> None:
    permissions.require_economics_writer(actor)
    permissions.require_whole_project_scope(session, project_id=project.id, actor=actor)
    if not reason.strip():
        raise ValidationError("Enter a removal reason.")
    lock_project(session, project.id)
    row = settings(session, project.id)
    if row is None:
        raise NotFoundError("Current cost settings not found.")
    if row.revision != revision:
        raise ConflictError("The analysis settings changed. Refresh before deleting.")
    record_event(
        session,
        action="unit_economics.current_settings_deleted",
        entity_type="unit_cost_analysis",
        entity_id=project.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=CostSettingsRead.model_validate(row).model_dump(mode="json"),
    )
    session.delete(row)
    session.flush()


def _sum(values: list[Decimal | None]) -> Decimal | None:
    return (
        money(sum((v for v in values if v is not None), ZERO))
        if all(v is not None for v in values)
        else None
    )


def _per_sqm(value: Decimal | None, area: Decimal | None) -> Decimal | None:
    return money(value / area) if value is not None and area is not None and area > 0 else None


def group(
    rows: list[CurrentUnitCost], *, key: str, label: str, building_id: uuid.UUID | None = None
) -> CurrentCostGroup:
    fields = {
        name: _sum([getattr(r, name) for r in rows]) if rows else None
        for name in CostFigures.model_fields
        if name not in {"hard_cost_per_sqm", "total_cost_per_sqm", "gross_area_sqm"}
    }
    area = (
        sum((r.gross_area_sqm for r in rows if r.gross_area_sqm is not None), ZERO)
        if rows and all(r.gross_area_sqm is not None for r in rows)
        else None
    )
    return CurrentCostGroup(
        **fields,
        gross_area_sqm=area,
        hard_cost_per_sqm=_per_sqm(fields["hard_cost"], area),
        total_cost_per_sqm=_per_sqm(fields["total_cost"], area),
        id=key,
        label=label,
        building_id=building_id,
        unit_count=len(rows),
        sold_count=sum(r.revenue_basis == "sold" for r in rows),
        cost_complete_count=sum(r.total_cost is not None for r in rows),
        net_profit_complete_count=sum(r.net_profit is not None for r in rows),
        sold_revenue=_sum([r.revenue for r in rows if r.revenue_basis == "sold"]),
        forecast_revenue=_sum([r.revenue for r in rows if r.revenue_basis != "sold"]),
    )


def _unit_cost_rows(rows: list[UnitCost], sale: SaleContract | None) -> list[UnitCost]:
    """Actual direct costs follow the unit; selling costs follow the current deal.

    Unsold units use forecast inputs only for types without an actual direct cost.
    A forecast is an alternative estimate, never an extra copy of an actual cost.
    """
    actual = [
        r
        for r in rows
        if r.basis == "actual"
        and (
            (
                UNIT_COST_CLASS_OF[r.cost_type] == CLASS_DIRECT
                and (
                    r.sale_contract_id is None
                    or (sale is not None and r.sale_contract_id == sale.id)
                )
            )
            or (sale is not None and r.sale_contract_id == sale.id)
        )
    ]
    if sale is not None:
        return actual
    types = {r.cost_type for r in actual}
    return actual + [
        r
        for r in rows
        if r.basis == "forecast" and r.sale_contract_id is None and r.cost_type not in types
    ]


def read_analysis(
    session: Session, *, project: Project, actor: ActorContext
) -> CurrentCostAnalysis:
    permissions.require_economics_reader(actor)
    permissions.require_whole_project_scope(session, project_id=project.id, actor=actor)
    config = settings(session, project.id)
    issues: list[str] = []
    units = list(
        session.execute(
            select(Unit, Building, Floor)
            .outerjoin(Floor, Floor.id == Unit.floor_id)
            .join(Building, Building.id == func.coalesce(Unit.building_id, Floor.building_id))
            .where(Unit.project_id == project.id, Unit.is_active.is_(True))
            .order_by(Building.sequence, Floor.sequence, Unit.sequence, Unit.unit_reference)
        )
    )
    ids = [u.id for u, _b, _f in units]
    areas = (
        approved_gross_built_areas(
            session, project_id=project.id, area_type_id=config.gross_area_type_id
        )
        if config
        else {}
    )
    missing = [u.unit_reference for u, _b, _f in units if areas.get(u.id, ZERO) <= 0]
    if config is None:
        issues.append("Set the gross-built area basis and supplemental cost inputs.")
    if missing:
        issues.append(
            f"{len(missing)} units lack a positive approved gross-built measurement; "
            "shared allocation is unavailable."
        )
    if not units:
        issues.append("No active units to allocate costs to.")
    currency_ok = config is None or config.currency_id == project.base_currency_id
    if not currency_ok:
        issues.append("Analysis inputs use another currency. No conversion is assumed.")
    sources = current_unit_cost_sources(session, project_id=project.id)
    same_currency = all(s["currency_id"] == project.base_currency_id for s in sources)
    if not same_currency:
        issues.append(
            "Construction contains a different currency; contract totals are unavailable."
        )
    by_category = (
        {
            key: money(sum((s["amount"] for s in sources if s["category"] == key), ZERO))
            for key in ("hard", "soft", "contingency", "other")
        }
        if same_currency
        else {}
    )
    hard = by_category.get("hard") if any(s["category"] == "hard" for s in sources) else None
    if hard is None:
        issues.append("No comparable signed hard-cost contract has been recorded.")
    land = complete_project_acquisition_cost(session, project_id=project.id)
    if land is None:
        issues.append("Land acquisition costs are missing or incomplete.")

    def configured(name: str) -> Decimal | None:
        value = getattr(config, name) if config and currency_ok else None
        if value is None:
            issues.append(
                f"Enter {name.replace('_', ' ')}; explicit zero means no additional cost."
            )
        return value

    soft_extra = configured("supplemental_soft_cost")
    extra = configured("additional_cost")
    finance = configured("finance_cost")
    pools = {
        "hard_cost": hard,
        "land_cost": land,
        "soft_cost": _sum([by_category.get("soft"), soft_extra]),
        "additional_cost": _sum([by_category.get("contingency"), by_category.get("other"), extra]),
        "finance_cost": finance,
    }
    allocations: dict[str, dict[uuid.UUID, Decimal]] = {}
    if units and not missing:
        drivers = [DriverLine(unit_id=i, driver_value=areas[i]) for i in ids]
        for name, amount in pools.items():
            if amount is not None:
                allocations[name] = {
                    a.unit_id: a.allocated_amount
                    for a in allocate(pool_amount=amount, drivers=drivers)
                }
    sales = {
        s.unit_id: s
        for s in session.scalars(
            select(SaleContract).where(
                SaleContract.project_id == project.id,
                SaleContract.unit_id.in_(ids),
                SaleContract.status.in_(service.SOLD_SALE_STATUSES),
            )
        )
    }
    prices = service._active_prices(session, unit_ids=ids)
    grants = {
        g.sale_contract_id: g for g in current_unit_cost_grants(session, project_id=project.id)
    }
    costs: dict[uuid.UUID, list[UnitCost]] = defaultdict(list)
    for cost in session.scalars(
        select(UnitCost).where(
            UnitCost.project_id == project.id,
            UnitCost.unit_id.in_(ids),
            UnitCost.status == "active",
        )
    ):
        costs[cost.unit_id].append(cost)
    result: list[CurrentUnitCost] = []
    for unit, building, floor in units:
        unit_issues: list[str] = []
        if (unit.id in areas and areas[unit.id] <= 0) or unit.id not in areas:
            unit_issues.append("Positive approved gross-built area missing.")
        sale, price = sales.get(unit.id), prices.get(unit.id)
        if sale is None and price is not None and not unit.pricing_approved:
            price = None
            unit_issues.append("The asking price needs reapproval after inventory changes.")
        revenue = (
            sale.net_contract_price_ex_tax
            if sale
            else price.reference_price_ex_tax
            if price
            else None
        )
        revenue_currency = sale.currency_id if sale else price.currency_id if price else None
        if revenue_currency not in {None, project.base_currency_id}:
            revenue = None
            unit_issues.append("Revenue currency differs from project costs.")
        applicable = _unit_cost_rows(costs[unit.id], sale)
        cost_currency_ok = all(r.currency_id == project.base_currency_id for r in applicable)
        if not cost_currency_ok:
            unit_issues.append("Unit costs include a different currency.")
        manual_commission = [r for r in applicable if r.cost_type in COMMISSION_TYPES]
        direct = (
            money(sum((r.amount for r in applicable if r.cost_type not in COMMISSION_TYPES), ZERO))
            if cost_currency_ok
            else None
        )
        grant = grants.get(sale.id) if sale else None
        commission: Decimal | None
        if grant is not None:
            commission = (
                grant.commission_total if grant.currency_id == project.base_currency_id else None
            )
            commission_basis = (
                "released grant" if grant.status == "released" else "draft grant provision"
            )
            if manual_commission:
                unit_issues.append(
                    "Recorded unit commissions are excluded: the commission grant is counted once."
                )
        elif manual_commission:
            commission = (
                money(sum((r.amount for r in manual_commission), ZERO))
                if cost_currency_ok
                else None
            )
            commission_basis = "recorded unit commissions"
        else:
            rate = config.commission_rate_fraction if config else None
            commission = (
                money(revenue * rate)
                if revenue is not None and rate is not None
                else ZERO
                if rate == 0
                else None
            )
            commission_basis = "project rate provision" if rate is not None else "unavailable"
        if commission is None:
            unit_issues.append(
                "Commission amount or an explicit provision rate is missing/incomparable."
            )
        frozen = sales_service.frozen_seller_costs(sale) if sale else None
        seller = (
            money(frozen.commercial + frozen.finance)
            if frozen and frozen.reconciled and revenue_currency == project.base_currency_id
            else ZERO
            if not frozen
            else None
        )
        values = {name: allocations.get(name, {}).get(unit.id) for name in SHARED}
        values.update(direct_cost=direct, seller_cost=seller, commission_cost=commission)
        total = _sum(list(values.values()))
        profit = money(revenue - total) if revenue is not None and total is not None else None
        tax_rate = config.profit_tax_rate_fraction if config else None
        tax = (
            money(max(profit, ZERO) * tax_rate)
            if profit is not None and tax_rate is not None
            else None
        )
        net = money(profit - tax) if profit is not None and tax is not None else None
        area = areas.get(unit.id)
        result.append(
            CurrentUnitCost(
                **values,
                unit_id=unit.id,
                unit_reference=unit.unit_reference,
                building_id=building.id,
                building_name=building.name,
                floor_id=floor.id if floor else None,
                floor_name=floor.label if floor else "Building-level units",
                sale_id=sale.id if sale else None,
                revenue_basis="sold" if sale else "asking_price" if price else "unavailable",
                commission_basis=commission_basis,
                issues=unit_issues,
                gross_area_sqm=area,
                hard_cost_per_sqm=_per_sqm(values["hard_cost"], area),
                total_cost=total,
                total_cost_per_sqm=_per_sqm(total, area),
                revenue=revenue,
                profit_before_tax=profit,
                tax_amount=tax,
                net_profit=net,
            )
        )
    if config is None or config.profit_tax_rate_fraction is None:
        issues.append(
            "Profit-tax rate is not entered; net profit remains unavailable. VAT is separate."
        )
    buildings: dict[uuid.UUID, list[CurrentUnitCost]] = defaultdict(list)
    floors: dict[tuple[uuid.UUID, uuid.UUID | None], list[CurrentUnitCost]] = defaultdict(list)
    for row in result:
        buildings[row.building_id].append(row)
        floors[(row.building_id, row.floor_id)].append(row)
    source_rows = [
        CostSource(category=s["category"], reference=s["reference"], amount=s["amount"])
        for s in sources
        if s["currency_id"] == project.base_currency_id
    ]
    source_rows += [
        CostSource(category=cat, reference=ref, amount=value)
        for cat, ref, value in (
            ("land", "Land register: purchase plus acquisition charges", land),
            ("soft", "Supplemental soft costs outside the signed contracts", soft_extra),
            ("additional", "Additional shared costs outside other categories", extra),
            ("finance", "Shared project finance cost", finance),
        )
    ]
    return CurrentCostAnalysis(
        as_of_date=business_today(),
        currency_id=project.base_currency_id,
        currency_code=session.scalar(
            select(Currency.code).where(Currency.id == project.base_currency_id)
        )
        or "",
        gross_area_label=(
            session.scalar(select(AreaType.label).where(AreaType.id == config.gross_area_type_id))
            if config
            else None
        ),
        settings=CostSettingsRead.model_validate(config) if config else None,
        issues=issues,
        sources=source_rows,
        units=result,
        project=group(result, key=str(project.id), label=project.name),
        buildings=[
            group(rows, key=str(key), label=rows[0].building_name, building_id=key)
            for key, rows in buildings.items()
        ],
        floors=[
            group(
                rows,
                key=f"{key[0]}:{key[1] or 'direct'}",
                label=f"{rows[0].building_name} / {rows[0].floor_name}",
                building_id=key[0],
            )
            for key, rows in floors.items()
        ],
    )
