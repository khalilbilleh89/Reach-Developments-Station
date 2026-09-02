"""Unit economics routes: build a cost basis, then read profit off it.

Handlers validate, authorise and orchestrate. Every rule about what may happen
lives in the service; every rule about who may reach it lives in
``permissions.py``.

Lifecycle is never a PATCH. Submitting, approving, rejecting and activating a
cost basis are four acts with four different rights and four sets of
preconditions, so each has its own route. A ``PATCH {"status": "approved"}``
would be the checker's signature available to whoever could reach the endpoint,
which is precisely what the maker/checker rule exists to prevent.

There is one DELETE, and it reaches only a pool on a draft. Nothing that has
been submitted is ever removed: a superseded cost basis is what a sold unit's
economics still rests on, and deleting it would delete the explanation of a
margin somebody reported.

Nothing here computes a figure. Allocation, reconciliation, every profit layer,
every margin and the waterfall all arrive from the service already decided, so
the browser and the API agree with the allocation rows by construction rather
than by two implementations happening to match.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.inventory.models import Unit
from app.modules.unit_economics import permissions, service
from app.modules.unit_economics.models import (
    UNIT_COST_CLASS_OF,
    Allocation,
    AllocationVersion,
    CostPool,
    UnitCost,
)
from app.modules.unit_economics.permissions import EconomicsProject
from app.modules.unit_economics.schemas import (
    AllocationRead,
    AllocationVersionRead,
    CalculationPreview,
    CostPoolRead,
    DriverSet,
    PoolAllocationSummary,
    PoolCreate,
    PoolUpdate,
    ProjectEconomicsRead,
    ReconciliationRead,
    UnitCostCreate,
    UnitCostRead,
    UnitCostReversal,
    UnitEconomicsDetail,
    UnitEconomicsRead,
    VersionClone,
    VersionCreate,
    VersionDecision,
    VersionDetail,
    VersionRejection,
    WaterfallStep,
)

router = APIRouter(prefix="/projects/{project_id}/unit-economics", tags=["unit economics"])


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def _version_read(version: AllocationVersion) -> AllocationVersionRead:
    return AllocationVersionRead.model_validate(version)


def _unit_cost_read(cost: UnitCost) -> UnitCostRead:
    """One cost, with its economic class derived rather than stored.

    The class is policy applied to the type, so it is computed on the way out.
    Storing it would let a row exist whose type and class disagree.
    """
    return UnitCostRead(
        id=cost.id,
        unit_id=cost.unit_id,
        sale_contract_id=cost.sale_contract_id,
        currency_id=cost.currency_id,
        cost_type=cost.cost_type,
        cost_class=UNIT_COST_CLASS_OF[cost.cost_type],
        basis=cost.basis,
        amount=cost.amount,
        effective_date=cost.effective_date,
        reference=cost.reference,
        notes=cost.notes,
        status=cost.status,
        created_at=cost.created_at,
        reversed_at=cost.reversed_at,
        reversal_reason=cost.reversal_reason,
    )


def _economics_read(row: service.UnitEconomics) -> UnitEconomicsRead:
    profit = row.profit
    return UnitEconomicsRead(
        unit_id=row.unit.id,
        unit_reference=row.unit.unit_reference,
        unit_number=row.unit.unit_number,
        commercial_status=row.unit.commercial_status,
        basis=row.basis,
        revenue_source=row.revenue_source,
        revenue_source_id=row.revenue_source_id,
        revenue_currency_id=row.revenue_currency_id,
        cost_currency_id=row.cost_currency_id,
        allocation_version_id=row.version.id if row.version else None,
        allocation_version_number=row.version.version_number if row.version else None,
        allocation_effective_from=row.version.effective_from if row.version else None,
        land_cost=row.land_cost,
        hard_cost=row.hard_cost,
        soft_cost=row.soft_cost,
        direct_cost=row.direct_cost,
        variable_selling_cost=row.variable_selling_cost,
        seller_cost=row.seller_cost,
        allocated_finance_cost=row.allocated_finance_cost,
        deal_finance_cost=row.deal_finance_cost,
        revenue=row.revenue,
        development_cost=profit.development_cost if profit else None,
        commercial_cost=profit.commercial_cost if profit else None,
        finance_cost=profit.finance_cost if profit else None,
        total_cost=profit.total_cost if profit else None,
        gross_profit=profit.gross_profit if profit else None,
        gross_margin_fraction=profit.gross_margin_fraction if profit else None,
        contribution_profit=profit.contribution_profit if profit else None,
        contribution_margin_fraction=(profit.contribution_margin_fraction if profit else None),
        profit_after_finance=profit.profit_after_finance if profit else None,
        margin_fraction=profit.margin_fraction if profit else None,
        return_on_cost_fraction=profit.return_on_cost_fraction if profit else None,
        profitability_status=row.profitability_status,
        below_margin_threshold=row.below_margin_threshold,
        threshold_fraction=row.threshold_fraction,
    )


def _reconciliation_read(summary: service.Reconciliation) -> ReconciliationRead:
    return ReconciliationRead(
        reconciled=summary.reconciled,
        source_cost_total=summary.source_cost_total,
        allocated_cost_total=summary.allocated_cost_total,
        variance=summary.variance,
        pool_count=summary.pool_count,
        allocation_count=summary.allocation_count,
        unreconciled_pools=summary.unreconciled_pools,
    )


def _pool_summary(result: service.PoolResult) -> PoolAllocationSummary:
    return PoolAllocationSummary(
        pool_id=result.pool.id,
        pool_number=result.pool.pool_number,
        name=result.pool.name,
        category=result.pool.category,
        allocation_method=result.pool.allocation_method,
        scope_kind=result.pool.scope_kind,
        pool_amount=result.pool.amount,
        eligible_units=result.eligible_units,
        driver_total=result.driver_total,
        allocated_total=result.allocated_total,
        variance=result.variance,
    )


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #


@router.get(
    "/summary",
    response_model=ProjectEconomicsRead,
    summary="The project's current blended economics",
)
def read_summary(
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> ProjectEconomicsRead:
    totals, _rows = service.project_economics(session, project=project, actor=actor)
    return ProjectEconomicsRead(
        currency_id=totals.currency_id,
        unit_count=totals.unit_count,
        comparable_unit_count=totals.totals.unit_count,
        sold_count=totals.sold_count,
        unsold_count=totals.unsold_count,
        negative_profit_count=totals.negative_profit_count,
        below_threshold_count=totals.below_threshold_count,
        incomplete_count=totals.incomplete_count,
        currency_mismatch_count=totals.currency_mismatch_count,
        threshold_fraction=totals.threshold_fraction,
        revenue_total=totals.totals.revenue_total,
        development_cost_total=totals.totals.development_cost_total,
        commercial_cost_total=totals.totals.commercial_cost_total,
        finance_cost_total=totals.totals.finance_cost_total,
        total_cost_total=totals.totals.total_cost_total,
        gross_profit_total=totals.totals.gross_profit_total,
        contribution_profit_total=totals.totals.contribution_profit_total,
        profit_total=totals.totals.profit_total,
        margin_fraction=totals.totals.margin_fraction,
        return_on_cost_fraction=totals.totals.return_on_cost_fraction,
        active_version=(_version_read(totals.active_version) if totals.active_version else None),
    )


@router.get(
    "/units",
    response_model=list[UnitEconomicsRead],
    summary="Every unit's economics on the project register",
)
def read_register(
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[UnitEconomicsRead]:
    return [
        _economics_read(row) for row in service.unit_register(session, project=project, actor=actor)
    ]


@router.get(
    "/units/{unit_id}",
    response_model=UnitEconomicsDetail,
    summary="One unit's economics, its waterfall and its recorded costs",
)
def read_unit(
    unit_id: uuid.UUID,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> UnitEconomicsDetail:
    permissions.require_economics_reader(actor)
    unit = permissions.require_visible_unit(session, project=project, unit_id=unit_id, actor=actor)
    row = service.unit_economics(session, project=project, actor=actor, unit=unit)
    return UnitEconomicsDetail(
        economics=_economics_read(row),
        waterfall=[WaterfallStep(**step) for step in service.waterfall(row)],
        unit_costs=[_unit_cost_read(cost) for cost in _unit_costs(session, unit_id=unit.id)],
    )


@router.get(
    "/sales/{sale_id}",
    response_model=UnitEconomicsDetail,
    summary="One sale's economics, on the basis that governed when it was signed",
)
def read_sale(
    sale_id: uuid.UUID,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> UnitEconomicsDetail:
    permissions.require_economics_reader(actor)
    sale = permissions.require_visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    row = service.sale_economics(session, project=project, actor=actor, sale=sale)
    return UnitEconomicsDetail(
        economics=_economics_read(row),
        waterfall=[WaterfallStep(**step) for step in service.waterfall(row)],
        unit_costs=[
            _unit_cost_read(cost)
            for cost in _unit_costs(session, unit_id=sale.unit_id, sale_id=sale.id)
        ],
    )


def _unit_costs(
    session: Session, *, unit_id: uuid.UUID, sale_id: uuid.UUID | None = None
) -> list[UnitCost]:
    statement = select(UnitCost).where(UnitCost.unit_id == unit_id)
    if sale_id is not None:
        statement = statement.where(UnitCost.sale_contract_id == sale_id)
    return list(session.scalars(statement.order_by(UnitCost.effective_date, UnitCost.created_at)))


@router.get(
    "/unit-costs",
    response_model=list[UnitCostRead],
    summary="Recorded unit costs across the project",
)
def list_unit_costs(
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
    unit_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[UnitCostRead]:
    permissions.require_economics_reader(actor)
    statement = select(UnitCost).where(UnitCost.project_id == project.id)
    if unit_id is not None:
        statement = statement.where(UnitCost.unit_id == unit_id)
    allowed = permissions.visible_units(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(UnitCost.unit_id.in_(allowed))
    return [
        _unit_cost_read(cost)
        for cost in session.scalars(
            statement.order_by(UnitCost.effective_date.desc(), UnitCost.created_at.desc())
        )
    ]


# --------------------------------------------------------------------------- #
# Allocation versions
# --------------------------------------------------------------------------- #


@router.get(
    "/allocation-versions",
    response_model=list[AllocationVersionRead],
    summary="Every cost basis this project has had",
)
def list_versions(
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[AllocationVersionRead]:
    permissions.require_economics_reader(actor)
    return [
        _version_read(version)
        for version in session.scalars(
            select(AllocationVersion)
            .where(AllocationVersion.project_id == project.id)
            .order_by(AllocationVersion.version_number.desc())
        )
    ]


@router.get(
    "/allocation-versions/{version_id}",
    response_model=VersionDetail,
    summary="One cost basis with its pools and its reconciliation",
)
def read_version(
    version_id: uuid.UUID,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> VersionDetail:
    permissions.require_economics_reader(actor)
    version = session.scalars(
        select(AllocationVersion).where(
            AllocationVersion.id == version_id,
            AllocationVersion.project_id == project.id,
        )
    ).first()
    if version is None:
        raise permissions.version_not_found()
    pools = session.scalars(
        select(CostPool)
        .where(CostPool.allocation_version_id == version.id)
        .order_by(CostPool.pool_number)
    )
    return VersionDetail(
        version=_version_read(version),
        pools=[CostPoolRead.model_validate(pool) for pool in pools],
        reconciliation=_reconciliation_read(service.reconcile(session, version=version)),
        stale_sources=service.stale_sources(session, version=version),
    )


@router.get(
    "/allocation-versions/{version_id}/allocations",
    response_model=list[AllocationRead],
    summary="Every unit allocation in one cost basis",
)
def read_allocations(
    version_id: uuid.UUID,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
    pool_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[AllocationRead]:
    permissions.require_economics_reader(actor)
    statement = (
        select(Allocation, Unit.unit_reference)
        .join(Unit, Unit.id == Allocation.unit_id)
        .where(
            Allocation.allocation_version_id == version_id,
            Allocation.project_id == project.id,
        )
    )
    if pool_id is not None:
        statement = statement.where(Allocation.cost_pool_id == pool_id)
    allowed = permissions.visible_units(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(Allocation.unit_id.in_(allowed))
    return [
        AllocationRead(
            unit_id=row.unit_id,
            unit_reference=reference,
            driver_value=row.driver_value,
            driver_share=row.driver_share,
            allocated_amount=row.allocated_amount,
            source_area_schedule_id=row.source_area_schedule_id,
            source_price_version_id=row.source_price_version_id,
            is_rounding_recipient=row.is_rounding_recipient,
        )
        for row, reference in session.execute(statement.order_by(Unit.sequence, Unit.id)).all()
    ]


@router.post(
    "/allocation-versions",
    response_model=AllocationVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a draft cost basis",
)
def create_version(
    payload: VersionCreate,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> AllocationVersionRead:
    version = service.create_version(
        session,
        project=project,
        actor=actor,
        effective_from=payload.effective_from,
        change_reason=payload.change_reason,
        finance_treatment=payload.finance_treatment,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_read(version)


@router.post(
    "/allocation-versions/{version_id}/clone",
    response_model=AllocationVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Copy a cost basis into a new draft",
)
def clone_version(
    version_id: uuid.UUID,
    payload: VersionClone,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> AllocationVersionRead:
    version = service.clone_version(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        effective_from=payload.effective_from,
        change_reason=payload.change_reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_read(version)


# --------------------------------------------------------------------------- #
# Draft pools
# --------------------------------------------------------------------------- #


@router.post(
    "/allocation-versions/{version_id}/pools",
    response_model=CostPoolRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a shared cost to a draft basis",
)
def add_pool(
    version_id: uuid.UUID,
    payload: PoolCreate,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> CostPoolRead:
    pool = service.add_pool(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        pool_number=payload.pool_number,
        name=payload.name,
        category=payload.category,
        source_kind=payload.source_kind,
        amount=payload.amount,
        scope_kind=payload.scope_kind,
        phase_id=payload.phase_id,
        building_id=payload.building_id,
        allocation_method=payload.allocation_method,
        area_type_id=payload.area_type_id,
        notes=payload.notes,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(pool)
    return CostPoolRead.model_validate(pool)


@router.patch(
    "/allocation-versions/{version_id}/pools/{pool_id}",
    response_model=CostPoolRead,
    summary="Change a pool on a draft basis",
)
def update_pool(
    version_id: uuid.UUID,
    pool_id: uuid.UUID,
    payload: PoolUpdate,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> CostPoolRead:
    pool = service.update_pool(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        pool_id=pool_id,
        changes=payload.model_dump(exclude_unset=True),
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(pool)
    return CostPoolRead.model_validate(pool)


@router.delete(
    "/allocation-versions/{version_id}/pools/{pool_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a pool from a draft basis",
)
def remove_pool(
    version_id: uuid.UUID,
    pool_id: uuid.UUID,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> None:
    service.remove_pool(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        pool_id=pool_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()


@router.put(
    "/allocation-versions/{version_id}/pools/{pool_id}/drivers",
    response_model=CostPoolRead,
    summary="Record the driver values for a custom-driver pool",
)
def set_drivers(
    version_id: uuid.UUID,
    pool_id: uuid.UUID,
    payload: DriverSet,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> CostPoolRead:
    drivers: dict[uuid.UUID, Decimal] = {
        entry.unit_id: entry.driver_value for entry in payload.drivers
    }
    pool = service.set_custom_drivers(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        pool_id=pool_id,
        drivers=drivers,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(pool)
    return CostPoolRead.model_validate(pool)


# --------------------------------------------------------------------------- #
# Calculation and lifecycle
# --------------------------------------------------------------------------- #


@router.post(
    "/allocation-versions/{version_id}/calculate",
    response_model=CalculationPreview,
    summary="Divide every pool and show what it came to",
)
def calculate_version(
    version_id: uuid.UUID,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> CalculationPreview:
    results = service.calculate_version(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    version = session.scalars(
        select(AllocationVersion).where(AllocationVersion.id == version_id)
    ).one()
    summary = service.reconcile(session, version=version)
    return CalculationPreview(
        version=_version_read(version),
        pools=[_pool_summary(result) for result in results],
        source_cost_total=summary.source_cost_total,
        allocated_cost_total=summary.allocated_cost_total,
        variance=summary.variance,
        reconciled=summary.reconciled,
        stale_sources=service.stale_sources(session, version=version),
    )


@router.post(
    "/allocation-versions/{version_id}/submit",
    response_model=AllocationVersionRead,
    summary="Freeze a draft and put it in front of a checker",
)
def submit_version(
    version_id: uuid.UUID,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> AllocationVersionRead:
    version = service.submit_version(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_read(version)


@router.post(
    "/allocation-versions/{version_id}/approve",
    response_model=AllocationVersionRead,
    summary="Sign a submitted cost basis",
)
def approve_version(
    version_id: uuid.UUID,
    payload: VersionDecision,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> AllocationVersionRead:
    version = service.approve_version(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_read(version)


@router.post(
    "/allocation-versions/{version_id}/reject",
    response_model=AllocationVersionRead,
    summary="Refuse a submitted cost basis",
)
def reject_version(
    version_id: uuid.UUID,
    payload: VersionRejection,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> AllocationVersionRead:
    version = service.reject_version(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_read(version)


@router.post(
    "/allocation-versions/{version_id}/activate",
    response_model=AllocationVersionRead,
    summary="Make an approved cost basis current",
)
def activate_version(
    version_id: uuid.UUID,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> AllocationVersionRead:
    version = service.activate_version(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_read(version)


# --------------------------------------------------------------------------- #
# Unit costs
# --------------------------------------------------------------------------- #


@router.post(
    "/units/{unit_id}/costs",
    response_model=UnitCostRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a cost attributable to one unit",
)
def record_unit_cost(
    unit_id: uuid.UUID,
    payload: UnitCostCreate,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> UnitCostRead:
    unit = permissions.require_visible_unit(session, project=project, unit_id=unit_id, actor=actor)
    cost = service.record_unit_cost(
        session,
        project=project,
        actor=actor,
        unit=unit,
        cost_type=payload.cost_type,
        basis=payload.basis,
        amount=payload.amount,
        effective_date=payload.effective_date,
        sale_contract_id=payload.sale_contract_id,
        reference=payload.reference,
        notes=payload.notes,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(cost)
    return _unit_cost_read(cost)


@router.post(
    "/unit-costs/{cost_id}/reverse",
    response_model=UnitCostRead,
    summary="Reverse a recorded unit cost",
)
def reverse_unit_cost(
    cost_id: uuid.UUID,
    payload: UnitCostReversal,
    project: EconomicsProject,
    session: DbSession,
    actor: ActiveActor,
) -> UnitCostRead:
    cost = service.reverse_unit_cost(
        session,
        project=project,
        actor=actor,
        cost_id=cost_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(cost)
    return _unit_cost_read(cost)
