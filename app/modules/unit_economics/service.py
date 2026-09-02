"""Unit economics: building a cost basis, and reading profit off it.

Two halves, and the line between them is the point of the module.

**Writing** builds a governed allocation version. Finance drafts pools, the
system divides them across eligible units and stores the result, a second person
approves it, and activation makes it the current basis while closing the window
of the one it replaces. Nothing here recalculates a version that has been
submitted; a correction is a clone, not an edit.

**Reading** derives profit and never stores it. Revenue, cost, margin and return
on cost are computed at read time from the allocations, the unit costs and the
frozen sale — because a stored margin is a number that stops agreeing with its
own inputs the first time one of them moves.

The join between them is effective dating. An unsold unit is analysed on the
active version; a sold one on whichever version's window contains its contract
date, permanently. That is the whole reason versions exist, and it is why
nothing in Sales points at this module: the sale's own date is the key.

Source freshness is checked twice — before submission and again before
activation — because the interesting failure is the one in between. An approved
allocation that divided a pool by an area schedule since superseded is an
allocation of a project that no longer exists, and activating it would put a
number nobody can reproduce in front of a finance director.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.custom_fields import business_today
from app.modules.inventory.models import (
    AREA_SCHEDULE_APPROVED,
    Building,
    Floor,
    Phase,
    Unit,
    UnitAreaSchedule,
    UnitAreaValue,
)
from app.modules.inventory.service import area_lines, weighted_saleable_area
from app.modules.pricing.models import STATUS_ACTIVE as PRICE_ACTIVE
from app.modules.pricing.models import UnitPriceVersion
from app.modules.projects.models import LandParcel, Project
from app.modules.projects.service import lock_project
from app.modules.sales import service as sales_service
from app.modules.sales.models import (
    SALE_ACTIVE,
    SALE_TERMINATION_PENDING,
    SaleContract,
)
from app.modules.settings.models import CountryApprovalThreshold
from app.modules.unit_economics import calculator, permissions
from app.modules.unit_economics.calculator import ZERO, AllocationError, DriverLine, money
from app.modules.unit_economics.models import (
    ALLOCATION_METHODS,
    BASIS_ACTUAL,
    BASIS_FORECAST,
    BASIS_SOLD,
    CATEGORY_FINANCE,
    CATEGORY_HARD,
    CATEGORY_LAND,
    CATEGORY_SOFT,
    CLASS_DIRECT,
    COST_ACTIVE,
    COST_REVERSED,
    ENTITY_POOL,
    ENTITY_UNIT_COST,
    ENTITY_VERSION,
    FINANCE_ALLOCATED,
    FINANCE_EXCLUDED,
    FINANCE_TREATMENTS,
    METHOD_CUSTOM_DRIVER,
    METHOD_RAW_AREA,
    METHOD_REVENUE_VALUE,
    METHOD_WEIGHTED_AREA,
    POOL_CATEGORIES,
    POOL_SCOPES,
    POOL_SOURCE_KINDS,
    PROFIT_CURRENCY_MISMATCH,
    PROFIT_MISSING_COST_BASIS,
    PROFIT_MISSING_REVENUE,
    PROFIT_READY,
    PROFIT_UNRECONCILED,
    REQUIRED_CATEGORIES,
    REVENUE_FROM_PRICE,
    REVENUE_FROM_SALE,
    SCOPE_BUILDING,
    SCOPE_PHASE,
    SCOPE_PROJECT,
    SOURCE_MANUAL,
    SOURCE_PROJECT_LAND,
    UNIT_COST_CLASS_OF,
    UNIT_COST_TYPES,
    VERSION_ACTIVE,
    VERSION_APPROVED,
    VERSION_DRAFT,
    VERSION_GOVERNING,
    VERSION_REJECTED,
    VERSION_SUBMITTED,
    VERSION_SUPERSEDED,
    Allocation,
    AllocationVersion,
    CostPool,
    UnitCost,
)

#: The sale states whose economics are contractual truth. A ``signature_pending``
#: contract has been submitted and not signed: its figures are a proposal, and
#: the unit is still analysed on the forecast basis until it is activated.
SOLD_SALE_STATUSES = frozenset({SALE_ACTIVE, SALE_TERMINATION_PENDING})

#: How many affected units a refusal names before it stops. Enough to act on,
#: short enough to read, and it never becomes a way to enumerate a project.
_NAMED_LIMIT = 5


def _now() -> datetime:
    return datetime.now(UTC)


def _text(value: str | None, *, detail: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError(detail)
    return cleaned


# --------------------------------------------------------------------------- #
# Loading, scoped by owner
# --------------------------------------------------------------------------- #


def _version(
    session: Session, *, project_id: uuid.UUID, version_id: uuid.UUID
) -> AllocationVersion:
    version = session.scalars(
        select(AllocationVersion).where(
            AllocationVersion.id == version_id,
            AllocationVersion.project_id == project_id,
        )
    ).first()
    if version is None:
        raise permissions.version_not_found()
    return version


def _lock_version(
    session: Session, *, project_id: uuid.UUID, version_id: uuid.UUID
) -> AllocationVersion:
    """Take the version row, because its lifecycle spans its pools and rows."""
    version = session.scalars(
        select(AllocationVersion)
        .where(
            AllocationVersion.id == version_id,
            AllocationVersion.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if version is None:
        raise permissions.version_not_found()
    return version


def _pool(
    session: Session, *, project_id: uuid.UUID, version_id: uuid.UUID, pool_id: uuid.UUID
) -> CostPool:
    pool = session.scalars(
        select(CostPool).where(
            CostPool.id == pool_id,
            CostPool.project_id == project_id,
            CostPool.allocation_version_id == version_id,
        )
    ).first()
    if pool is None:
        raise permissions.pool_not_found()
    return pool


def active_version(session: Session, *, project_id: uuid.UUID) -> AllocationVersion | None:
    """The basis currently governing unsold economics, if one has been activated."""
    return session.scalars(
        select(AllocationVersion).where(
            AllocationVersion.project_id == project_id,
            AllocationVersion.status == VERSION_ACTIVE,
        )
    ).first()


def version_governing_on(
    session: Session, *, project_id: uuid.UUID, on: date
) -> AllocationVersion | None:
    """The basis whose effective window contains ``on``.

    Effective dating, not a foreign key. A sale signed in February is priced on
    whatever basis was governing in February for ever, and this query is the
    whole mechanism — which is why activating a new version tomorrow cannot
    reach backwards and restate it.
    """
    return session.scalars(
        select(AllocationVersion)
        .where(
            AllocationVersion.project_id == project_id,
            AllocationVersion.status.in_(VERSION_GOVERNING),
            AllocationVersion.effective_from <= on,
            (AllocationVersion.effective_to.is_(None)) | (AllocationVersion.effective_to > on),
        )
        .order_by(AllocationVersion.effective_from.desc())
    ).first()


# --------------------------------------------------------------------------- #
# The eligible population
# --------------------------------------------------------------------------- #


def _eligible_units_statement(pool: CostPool) -> Select[tuple[uuid.UUID]]:
    """The units one pool reaches, from its scope and nothing else.

    Deliberately blind to commercial status. A building does not become cheaper
    because a flat in it was reserved, and a denominator that shrank as units
    sold would quietly raise the cost of everything still unsold — which is the
    exact moment a developer most needs the number to hold still.
    """
    statement = (
        select(Unit.id)
        .join(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .where(Unit.project_id == pool.project_id, Unit.is_active.is_(True))
    )
    if pool.scope_kind == SCOPE_PHASE:
        statement = statement.where(Building.phase_id == pool.phase_id)
    elif pool.scope_kind == SCOPE_BUILDING:
        statement = statement.where(Floor.building_id == pool.building_id)
    return statement


def _eligible_unit_ids(session: Session, *, pool: CostPool) -> list[uuid.UUID]:
    return list(session.scalars(_eligible_units_statement(pool).order_by(Unit.sequence, Unit.id)))


def _unit_labels(session: Session, *, unit_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not unit_ids:
        return {}
    rows = session.execute(select(Unit.id, Unit.unit_reference).where(Unit.id.in_(unit_ids))).all()
    return dict(rows)


def _named(session: Session, unit_ids: list[uuid.UUID]) -> str:
    """A short, readable list of unit references for a refusal message."""
    labels = _unit_labels(session, unit_ids=unit_ids[:_NAMED_LIMIT])
    shown = ", ".join(labels.get(unit_id, str(unit_id)) for unit_id in unit_ids[:_NAMED_LIMIT])
    if len(unit_ids) > _NAMED_LIMIT:
        shown += f" and {len(unit_ids) - _NAMED_LIMIT} more"
    return shown


# --------------------------------------------------------------------------- #
# Land, the one derived pool amount
# --------------------------------------------------------------------------- #


def project_land_total(session: Session, *, project_id: uuid.UUID) -> Decimal:
    """What the land register says this project's land cost.

    Purchase consideration plus acquisition and title fees, over active parcels,
    in the project's base currency — which is what the land columns are
    denominated in. Never a valuation, never a residual, never area times a
    rate: this is cost allocation, and a pool seeded from what the land is
    *worth* would allocate a profit as though it were a cost.
    """
    total = session.scalar(
        select(
            func.coalesce(func.sum(func.coalesce(LandParcel.purchase_price, 0)), 0)
            + func.coalesce(func.sum(func.coalesce(LandParcel.acquisition_fees, 0)), 0)
        ).where(LandParcel.project_id == project_id, LandParcel.is_active.is_(True))
    )
    return money(Decimal(total or 0))


# --------------------------------------------------------------------------- #
# Drivers
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _DriverSet:
    """The denominator for one pool, and the evidence each line rests on."""

    lines: list[DriverLine]
    area_schedule_of: dict[uuid.UUID, uuid.UUID]
    price_version_of: dict[uuid.UUID, uuid.UUID]


def _approved_schedules(
    session: Session, *, unit_ids: list[uuid.UUID]
) -> dict[uuid.UUID, UnitAreaSchedule]:
    if not unit_ids:
        return {}
    rows = session.scalars(
        select(UnitAreaSchedule).where(
            UnitAreaSchedule.unit_id.in_(unit_ids),
            UnitAreaSchedule.status == AREA_SCHEDULE_APPROVED,
        )
    )
    return {schedule.unit_id: schedule for schedule in rows}


def _active_prices(
    session: Session, *, unit_ids: list[uuid.UUID]
) -> dict[uuid.UUID, UnitPriceVersion]:
    if not unit_ids:
        return {}
    rows = session.scalars(
        select(UnitPriceVersion).where(
            UnitPriceVersion.unit_id.in_(unit_ids),
            UnitPriceVersion.status == PRICE_ACTIVE,
        )
    )
    return {version.unit_id: version for version in rows}


def _weighted_drivers(
    session: Session, *, project_id: uuid.UUID, unit_ids: list[uuid.UUID]
) -> _DriverSet:
    """Weighted saleable area, taken from inventory rather than recomputed.

    Inventory owns what a weighted area is; this module owns what to do with it.
    A second implementation of the weighting would be a second answer, and the
    way that disagreement surfaces is a cost per square metre that does not
    match the area schedule it claims to divide.
    """
    schedules = _approved_schedules(session, unit_ids=unit_ids)
    missing = [unit_id for unit_id in unit_ids if unit_id not in schedules]
    if missing:
        raise ValidationError(
            "These units have no approved area schedule, so a weighted-area pool "
            f"cannot be divided across them: {_named(session, missing)}."
        )
    lines: list[DriverLine] = []
    schedule_of: dict[uuid.UUID, uuid.UUID] = {}
    for unit_id in unit_ids:
        schedule = schedules[unit_id]
        area = weighted_saleable_area(area_lines(session, project_id=project_id, schedule=schedule))
        lines.append(DriverLine(unit_id=unit_id, driver_value=area or Decimal("0")))
        schedule_of[unit_id] = schedule.id
    return _DriverSet(lines=lines, area_schedule_of=schedule_of, price_version_of={})


def _raw_area_drivers(session: Session, *, pool: CostPool, unit_ids: list[uuid.UUID]) -> _DriverSet:
    """One named area type, measured on each unit's approved schedule.

    "Raw area" is a single measurement Finance chooses — internal, gross, plot —
    never the sum of every area a unit has. Adding a balcony to an internal area
    to make a bigger denominator produces a division nobody can explain.
    """
    schedules = _approved_schedules(session, unit_ids=unit_ids)
    missing = [unit_id for unit_id in unit_ids if unit_id not in schedules]
    if missing:
        raise ValidationError(
            "These units have no approved area schedule, so a raw-area pool "
            f"cannot be divided across them: {_named(session, missing)}."
        )
    schedule_ids = [schedule.id for schedule in schedules.values()]
    measured = dict(
        session.execute(
            select(UnitAreaValue.unit_area_schedule_id, UnitAreaValue.raw_area).where(
                UnitAreaValue.unit_area_schedule_id.in_(schedule_ids),
                UnitAreaValue.area_type_id == pool.area_type_id,
            )
        ).all()
    )
    without = [unit_id for unit_id in unit_ids if schedules[unit_id].id not in measured]
    if without:
        raise ValidationError(
            "These units have no measurement of the chosen area type on their "
            f"approved schedule: {_named(session, without)}."
        )
    return _DriverSet(
        lines=[
            DriverLine(unit_id=unit_id, driver_value=measured[schedules[unit_id].id])
            for unit_id in unit_ids
        ],
        area_schedule_of={unit_id: schedules[unit_id].id for unit_id in unit_ids},
        price_version_of={},
    )


def _revenue_drivers(
    session: Session, *, version: AllocationVersion, unit_ids: list[uuid.UUID]
) -> _DriverSet:
    """Each unit's current list price, from the pricing version governing it now.

    The reference price excluding tax, because that is what pricing calls the
    developer's economic revenue for a unit. Not a displayed string, not a
    quote, and not a number typed into this module.
    """
    prices = _active_prices(session, unit_ids=unit_ids)
    missing = [unit_id for unit_id in unit_ids if unit_id not in prices]
    if missing:
        raise ValidationError(
            "These units have no current approved price, so a revenue-value pool "
            f"cannot be divided across them: {_named(session, missing)}."
        )
    mismatched = [
        unit_id for unit_id in unit_ids if prices[unit_id].currency_id != version.currency_id
    ]
    if mismatched:
        raise ValidationError(
            "These units are priced in a different currency from the project's "
            "cost basis, and there is no exchange rate to convert them: "
            f"{_named(session, mismatched)}."
        )
    return _DriverSet(
        lines=[
            DriverLine(unit_id=unit_id, driver_value=prices[unit_id].reference_price_ex_tax)
            for unit_id in unit_ids
        ],
        area_schedule_of={},
        price_version_of={unit_id: prices[unit_id].id for unit_id in unit_ids},
    )


def _custom_drivers(session: Session, *, pool: CostPool, unit_ids: list[uuid.UUID]) -> _DriverSet:
    """The driver values Finance entered, read back from the allocation rows.

    Custom driver exists because real allocations sometimes divide on a parking
    count or a quantity surveyor's factor, and the alternative to accepting one
    number per unit is an expression language. Entering a driver writes the
    allocation row with a zero amount; calculating fills the amount in.
    """
    entered = dict(
        session.execute(
            select(Allocation.unit_id, Allocation.driver_value).where(
                Allocation.cost_pool_id == pool.id
            )
        ).all()
    )
    missing = [unit_id for unit_id in unit_ids if unit_id not in entered]
    if missing:
        raise ValidationError(
            "These units have no driver value for this pool, so it cannot be "
            f"divided: {_named(session, missing)}."
        )
    return _DriverSet(
        lines=[DriverLine(unit_id=unit_id, driver_value=entered[unit_id]) for unit_id in unit_ids],
        area_schedule_of={},
        price_version_of={},
    )


def _drivers_for(
    session: Session, *, version: AllocationVersion, pool: CostPool, unit_ids: list[uuid.UUID]
) -> _DriverSet:
    if pool.allocation_method == METHOD_WEIGHTED_AREA:
        return _weighted_drivers(session, project_id=pool.project_id, unit_ids=unit_ids)
    if pool.allocation_method == METHOD_RAW_AREA:
        return _raw_area_drivers(session, pool=pool, unit_ids=unit_ids)
    if pool.allocation_method == METHOD_REVENUE_VALUE:
        return _revenue_drivers(session, version=version, unit_ids=unit_ids)
    if pool.allocation_method == METHOD_CUSTOM_DRIVER:
        return _custom_drivers(session, pool=pool, unit_ids=unit_ids)
    # Unit count: every eligible unit brings exactly one.
    return _DriverSet(
        lines=[DriverLine(unit_id=unit_id, driver_value=Decimal("1")) for unit_id in unit_ids],
        area_schedule_of={},
        price_version_of={},
    )


# --------------------------------------------------------------------------- #
# Versions
# --------------------------------------------------------------------------- #


def _require_draft(version: AllocationVersion) -> None:
    if version.status != VERSION_DRAFT:
        raise ConflictError(
            "This allocation version is no longer a draft. Its cost basis is "
            "frozen; clone it to propose a change."
        )


def _next_version_number(session: Session, *, project_id: uuid.UUID) -> int:
    highest = session.scalar(
        select(func.max(AllocationVersion.version_number)).where(
            AllocationVersion.project_id == project_id
        )
    )
    return int(highest or 0) + 1


def _require_effective_from_allowed(
    session: Session, *, project_id: uuid.UUID, effective_from: date
) -> None:
    """Refuse a version that would be inserted into an already-governed period.

    The first version on a project may be back-dated: PR-MVP-08 arrives after
    sales exist, and without an opening baseline those contracts have no cost
    basis at all. Every later one must start after the current basis started —
    otherwise Finance could slide version four into version one's window and
    silently restate what a unit sold two years ago cost.
    """
    standing = active_version(session, project_id=project_id)
    if standing is None:
        return
    if effective_from <= standing.effective_from:
        raise ConflictError(
            "A cost basis cannot start on or before the one it replaces "
            f"({standing.effective_from.isoformat()}). Back-dating into a period "
            "that has already been governed would restate units already sold."
        )


def create_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    effective_from: date,
    change_reason: str,
    finance_treatment: str,
    correlation_id: uuid.UUID,
) -> AllocationVersion:
    """Open a new draft cost basis for this project."""
    permissions.require_economics_writer(actor)
    if finance_treatment not in FINANCE_TREATMENTS:
        raise ValidationError("That is not a finance treatment.")
    reason = _text(change_reason, detail="Say why this cost basis is being proposed.")

    project = lock_project(session, project.id)
    _require_effective_from_allowed(session, project_id=project.id, effective_from=effective_from)

    version = AllocationVersion(
        project_id=project.id,
        version_number=_next_version_number(session, project_id=project.id),
        # The project's base currency, never a choice. A project accounts in one
        # currency and allocating its cost in another would need an exchange
        # rate this platform deliberately does not have.
        currency_id=project.base_currency_id,
        status=VERSION_DRAFT,
        finance_treatment=finance_treatment,
        effective_from=effective_from,
        change_reason=reason,
        created_by_user_id=actor.user_id,
    )
    session.add(version)
    session.flush()
    record_event(
        session,
        action="unit_economics.version_created",
        entity_type=ENTITY_VERSION,
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "version_number": version.version_number,
            "effective_from": version.effective_from,
            "finance_treatment": version.finance_treatment,
        },
    )
    return version


def clone_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    effective_from: date,
    change_reason: str,
    correlation_id: uuid.UUID,
) -> AllocationVersion:
    """Copy a version's pools into a new draft. The only way to change a basis.

    Pools are copied; allocations are not. A cloned draft has to be recalculated
    against today's areas and prices, which is the point — the alternative is
    carrying an allocation forward without re-reading what it divided.
    """
    permissions.require_economics_writer(actor)
    reason = _text(change_reason, detail="Say why this cost basis is being revised.")
    project = lock_project(session, project.id)
    source = _version(session, project_id=project.id, version_id=version_id)
    _require_effective_from_allowed(session, project_id=project.id, effective_from=effective_from)

    clone = AllocationVersion(
        project_id=project.id,
        version_number=_next_version_number(session, project_id=project.id),
        currency_id=project.base_currency_id,
        status=VERSION_DRAFT,
        finance_treatment=source.finance_treatment,
        effective_from=effective_from,
        change_reason=reason,
        source_version_id=source.id,
        created_by_user_id=actor.user_id,
    )
    session.add(clone)
    session.flush()

    for pool in session.scalars(
        select(CostPool)
        .where(CostPool.allocation_version_id == source.id)
        .order_by(CostPool.pool_number)
    ):
        session.add(
            CostPool(
                project_id=project.id,
                allocation_version_id=clone.id,
                pool_number=pool.pool_number,
                name=pool.name,
                category=pool.category,
                source_kind=pool.source_kind,
                amount=pool.amount,
                scope_kind=pool.scope_kind,
                phase_id=pool.phase_id,
                building_id=pool.building_id,
                allocation_method=pool.allocation_method,
                area_type_id=pool.area_type_id,
                notes=pool.notes,
                created_by_user_id=actor.user_id,
            )
        )
    session.flush()
    record_event(
        session,
        action="unit_economics.version_created",
        entity_type=ENTITY_VERSION,
        entity_id=clone.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "version_number": clone.version_number,
            "effective_from": clone.effective_from,
            "cloned_from": source.version_number,
        },
    )
    return clone


# --------------------------------------------------------------------------- #
# Pools
# --------------------------------------------------------------------------- #


def _require_scope_shape(
    session: Session,
    *,
    project_id: uuid.UUID,
    scope_kind: str,
    phase_id: uuid.UUID | None,
    building_id: uuid.UUID | None,
) -> None:
    """Prove the pool's scope belongs to this project before it is stored.

    The composite foreign keys enforce it too. This exists so the operator gets
    "that phase is not in this project" rather than a constraint violation, and
    so the check is visible where somebody reading the service will find it.
    """
    if scope_kind == SCOPE_PROJECT:
        if phase_id is not None or building_id is not None:
            raise ValidationError("A project-wide pool names neither a phase nor a building.")
        return
    if scope_kind == SCOPE_PHASE:
        if phase_id is None or building_id is not None:
            raise ValidationError("A phase pool names exactly one phase.")
        exists = session.scalars(
            select(Phase.id).where(Phase.id == phase_id, Phase.project_id == project_id)
        ).first()
        if exists is None:
            raise NotFoundError("Phase not found.")
        return
    if building_id is None or phase_id is not None:
        raise ValidationError("A building pool names exactly one building.")
    exists = session.scalars(
        select(Building.id).where(Building.id == building_id, Building.project_id == project_id)
    ).first()
    if exists is None:
        raise NotFoundError("Building not found.")


def _resolve_pool_amount(
    session: Session, *, project_id: uuid.UUID, source_kind: str, amount: Decimal | None
) -> Decimal:
    if source_kind == SOURCE_PROJECT_LAND:
        return project_land_total(session, project_id=project_id)
    if amount is None:
        raise ValidationError("A manual cost pool needs an amount.")
    if amount < 0:
        raise ValidationError("A cost pool amount cannot be negative.")
    return money(amount)


def add_pool(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    pool_number: str,
    name: str,
    category: str,
    source_kind: str,
    amount: Decimal | None,
    scope_kind: str,
    phase_id: uuid.UUID | None,
    building_id: uuid.UUID | None,
    allocation_method: str,
    area_type_id: uuid.UUID | None,
    notes: str | None,
    correlation_id: uuid.UUID,
) -> CostPool:
    """Add one shared cost to a draft basis."""
    permissions.require_economics_writer(actor)
    project = lock_project(session, project.id)
    version = _lock_version(session, project_id=project.id, version_id=version_id)
    _require_draft(version)

    if category not in POOL_CATEGORIES:
        raise ValidationError("That is not a cost category.")
    if source_kind not in POOL_SOURCE_KINDS:
        raise ValidationError("That is not a cost pool source.")
    if scope_kind not in POOL_SCOPES:
        raise ValidationError("That is not a pool scope.")
    if allocation_method not in ALLOCATION_METHODS:
        raise ValidationError("That is not an allocation method.")
    if source_kind == SOURCE_PROJECT_LAND and category != CATEGORY_LAND:
        raise ValidationError("Only a land pool can be sourced from the land register.")
    if category == CATEGORY_FINANCE and version.finance_treatment == FINANCE_EXCLUDED:
        raise ConflictError(
            "This cost basis records finance cost as excluded, so it cannot carry "
            "a finance pool. Change the treatment to allocated first."
        )
    if (allocation_method == METHOD_RAW_AREA) != (area_type_id is not None):
        raise ValidationError(
            "A raw-area pool names exactly one area type, and no other method takes one."
        )
    _require_scope_shape(
        session,
        project_id=project.id,
        scope_kind=scope_kind,
        phase_id=phase_id,
        building_id=building_id,
    )

    pool = CostPool(
        project_id=project.id,
        allocation_version_id=version.id,
        pool_number=_text(pool_number, detail="A cost pool needs a reference.").upper(),
        name=_text(name, detail="A cost pool needs a name."),
        category=category,
        source_kind=source_kind,
        amount=_resolve_pool_amount(
            session, project_id=project.id, source_kind=source_kind, amount=amount
        ),
        scope_kind=scope_kind,
        phase_id=phase_id,
        building_id=building_id,
        allocation_method=allocation_method,
        area_type_id=area_type_id,
        notes=notes,
        created_by_user_id=actor.user_id,
    )
    session.add(pool)
    _invalidate(session, version=version)
    session.flush()
    record_event(
        session,
        action="unit_economics.pool_created",
        entity_type=ENTITY_POOL,
        entity_id=pool.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "pool_number": pool.pool_number,
            "category": pool.category,
            "amount": pool.amount,
            "allocation_method": pool.allocation_method,
            "scope_kind": pool.scope_kind,
        },
    )
    return pool


def update_pool(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    pool_id: uuid.UUID,
    changes: dict[str, Any],
    correlation_id: uuid.UUID,
) -> CostPool:
    """Change one draft pool. Only the fields the caller actually sent."""
    permissions.require_economics_writer(actor)
    project = lock_project(session, project.id)
    version = _lock_version(session, project_id=project.id, version_id=version_id)
    _require_draft(version)
    pool = _pool(session, project_id=project.id, version_id=version.id, pool_id=pool_id)
    before = {
        "name": pool.name,
        "amount": pool.amount,
        "allocation_method": pool.allocation_method,
        "scope_kind": pool.scope_kind,
    }

    if "name" in changes:
        pool.name = _text(changes["name"], detail="A cost pool needs a name.")
    if "notes" in changes:
        pool.notes = changes["notes"]
    if "amount" in changes:
        if pool.source_kind == SOURCE_PROJECT_LAND:
            raise ConflictError(
                "This pool takes its amount from the land register. Correct the "
                "land record instead of typing a different total here."
            )
        pool.amount = _resolve_pool_amount(
            session, project_id=project.id, source_kind=SOURCE_MANUAL, amount=changes["amount"]
        )
    if "allocation_method" in changes:
        method = changes["allocation_method"]
        if method not in ALLOCATION_METHODS:
            raise ValidationError("That is not an allocation method.")
        pool.allocation_method = method
    if "area_type_id" in changes:
        pool.area_type_id = changes["area_type_id"]
    if (pool.allocation_method == METHOD_RAW_AREA) != (pool.area_type_id is not None):
        raise ValidationError(
            "A raw-area pool names exactly one area type, and no other method takes one."
        )
    if "scope_kind" in changes or "phase_id" in changes or "building_id" in changes:
        pool.scope_kind = changes.get("scope_kind", pool.scope_kind)
        pool.phase_id = changes.get("phase_id", pool.phase_id)
        pool.building_id = changes.get("building_id", pool.building_id)
        if pool.scope_kind not in POOL_SCOPES:
            raise ValidationError("That is not a pool scope.")
        if pool.scope_kind == SCOPE_PROJECT:
            pool.phase_id = None
            pool.building_id = None
        elif pool.scope_kind == SCOPE_PHASE:
            pool.building_id = None
        else:
            pool.phase_id = None
        _require_scope_shape(
            session,
            project_id=project.id,
            scope_kind=pool.scope_kind,
            phase_id=pool.phase_id,
            building_id=pool.building_id,
        )

    _invalidate(session, version=version, pool_id=pool.id)
    session.flush()
    record_event(
        session,
        action="unit_economics.pool_updated",
        entity_type=ENTITY_POOL,
        entity_id=pool.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after={
            "name": pool.name,
            "amount": pool.amount,
            "allocation_method": pool.allocation_method,
            "scope_kind": pool.scope_kind,
        },
    )
    return pool


def remove_pool(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    pool_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> None:
    """Drop one pool from a draft. Only ever a draft: history is not deleted."""
    permissions.require_economics_writer(actor)
    project = lock_project(session, project.id)
    version = _lock_version(session, project_id=project.id, version_id=version_id)
    _require_draft(version)
    pool = _pool(session, project_id=project.id, version_id=version.id, pool_id=pool_id)
    number, name = pool.pool_number, pool.name
    session.delete(pool)
    _invalidate(session, version=version)
    session.flush()
    record_event(
        session,
        action="unit_economics.pool_removed_from_draft",
        entity_type=ENTITY_POOL,
        entity_id=pool_id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        before={"pool_number": number, "name": name},
    )


def _invalidate(
    session: Session, *, version: AllocationVersion, pool_id: uuid.UUID | None = None
) -> None:
    """Discard a stale calculation after its inputs changed.

    Editing a pool after calculating leaves allocation rows that divide an
    amount nobody proposed any more. Clearing ``calculated_at`` is what makes
    submission refuse until Finance has looked at the new numbers; custom driver
    values survive, because they are Finance's own input rather than a result.
    """
    version.calculated_at = None
    statement = select(Allocation).where(Allocation.allocation_version_id == version.id)
    if pool_id is not None:
        statement = statement.where(Allocation.cost_pool_id == pool_id)
    for allocation in session.scalars(statement):
        if allocation.allocated_amount == ZERO and allocation.driver_share == 0:
            continue
        allocation.allocated_amount = ZERO
        allocation.driver_share = Decimal("0")
        allocation.is_rounding_recipient = False


def set_custom_drivers(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    pool_id: uuid.UUID,
    drivers: dict[uuid.UUID, Decimal],
    correlation_id: uuid.UUID,
) -> CostPool:
    """Record one driver value per eligible unit for a custom-driver pool.

    Stored on the allocation rows, with a zero amount until the version is
    calculated. That keeps the four tables the schema promises and puts the
    driver exactly where an auditor will look for it: beside the amount it
    produced.
    """
    permissions.require_economics_writer(actor)
    project = lock_project(session, project.id)
    version = _lock_version(session, project_id=project.id, version_id=version_id)
    _require_draft(version)
    pool = _pool(session, project_id=project.id, version_id=version.id, pool_id=pool_id)
    if pool.allocation_method != METHOD_CUSTOM_DRIVER:
        raise ConflictError("Only a custom-driver pool takes driver values.")

    eligible = set(_eligible_unit_ids(session, pool=pool))
    unknown = [unit_id for unit_id in drivers if unit_id not in eligible]
    if unknown:
        raise ValidationError(
            "These units are not in this pool's scope, so they cannot carry a "
            f"driver for it: {_named(session, unknown)}."
        )
    if any(value < 0 for value in drivers.values()):
        raise ValidationError("A driver value cannot be negative.")

    existing = {
        allocation.unit_id: allocation
        for allocation in session.scalars(
            select(Allocation).where(Allocation.cost_pool_id == pool.id)
        )
    }
    for unit_id, value in drivers.items():
        row = existing.get(unit_id)
        if row is None:
            session.add(
                Allocation(
                    project_id=project.id,
                    allocation_version_id=version.id,
                    cost_pool_id=pool.id,
                    unit_id=unit_id,
                    driver_value=value,
                    driver_share=Decimal("0"),
                    allocated_amount=ZERO,
                )
            )
        else:
            row.driver_value = value
            row.driver_share = Decimal("0")
            row.allocated_amount = ZERO
            row.is_rounding_recipient = False
    version.calculated_at = None
    session.flush()
    record_event(
        session,
        action="unit_economics.pool_updated",
        entity_type=ENTITY_POOL,
        entity_id=pool.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={"pool_number": pool.pool_number, "drivers_entered": len(drivers)},
    )
    return pool


# --------------------------------------------------------------------------- #
# Calculation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PoolResult:
    """One pool's calculated allocation, as the preview reports it."""

    pool: CostPool
    eligible_units: int
    driver_total: Decimal
    allocated_total: Decimal
    variance: Decimal


def calculate_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> list[PoolResult]:
    """Divide every pool across its eligible units and store the result.

    Replaces whatever a previous calculation of this draft produced. There is no
    history inside an unsubmitted draft on purpose: a draft is working state,
    and keeping every intermediate division would bury the one that matters.
    """
    permissions.require_economics_writer(actor)
    project = lock_project(session, project.id)
    version = _lock_version(session, project_id=project.id, version_id=version_id)
    _require_draft(version)

    pools = list(
        session.scalars(
            select(CostPool)
            .where(CostPool.allocation_version_id == version.id)
            .order_by(CostPool.pool_number)
        )
    )
    if not pools:
        raise ConflictError("This cost basis has no pools, so there is nothing to allocate.")

    results: list[PoolResult] = []
    for pool in pools:
        if pool.source_kind == SOURCE_PROJECT_LAND:
            pool.amount = project_land_total(session, project_id=project.id)
        unit_ids = _eligible_unit_ids(session, pool=pool)
        if not unit_ids:
            raise ConflictError(
                f"No units fall in the scope of pool {pool.pool_number}, so it cannot be allocated."
            )
        drivers = _drivers_for(session, version=version, pool=pool, unit_ids=unit_ids)
        try:
            lines = calculator.allocate(pool_amount=pool.amount, drivers=drivers.lines)
        except AllocationError as failure:
            raise ValidationError(f"Pool {pool.pool_number}: {failure}") from failure

        for allocation in session.scalars(
            select(Allocation).where(Allocation.cost_pool_id == pool.id)
        ):
            session.delete(allocation)
        session.flush()

        for line in lines:
            session.add(
                Allocation(
                    project_id=project.id,
                    allocation_version_id=version.id,
                    cost_pool_id=pool.id,
                    unit_id=line.unit_id,
                    driver_value=line.driver_value,
                    driver_share=line.driver_share,
                    allocated_amount=line.allocated_amount,
                    source_area_schedule_id=drivers.area_schedule_of.get(line.unit_id),
                    source_price_version_id=drivers.price_version_of.get(line.unit_id),
                    is_rounding_recipient=line.is_rounding_recipient,
                )
            )
        allocated = money(sum((line.allocated_amount for line in lines), ZERO))
        results.append(
            PoolResult(
                pool=pool,
                eligible_units=len(lines),
                driver_total=sum((line.driver_value for line in lines), Decimal("0")),
                allocated_total=allocated,
                variance=money(pool.amount) - allocated,
            )
        )

    version.calculated_at = _now()
    session.flush()
    record_event(
        session,
        action="unit_economics.version_calculated",
        entity_type=ENTITY_VERSION,
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "pool_count": len(results),
            "source_total": money(sum((result.pool.amount for result in results), ZERO)),
            "allocated_total": money(sum((result.allocated_total for result in results), ZERO)),
        },
    )
    return results


# --------------------------------------------------------------------------- #
# Reconciliation and freshness
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """Whether a version's allocations still add up to the pools they came from."""

    reconciled: bool
    source_cost_total: Decimal
    allocated_cost_total: Decimal
    variance: Decimal
    pool_count: int
    allocation_count: int
    unreconciled_pools: list[str]


def reconcile(session: Session, *, version: AllocationVersion) -> Reconciliation:
    """Prove, pool by pool, that nothing was lost or invented in the division."""
    rows = session.execute(
        select(
            CostPool.id,
            CostPool.pool_number,
            CostPool.amount,
            func.coalesce(func.sum(Allocation.allocated_amount), 0),
            func.count(Allocation.id),
        )
        .select_from(CostPool)
        .outerjoin(Allocation, Allocation.cost_pool_id == CostPool.id)
        .where(CostPool.allocation_version_id == version.id)
        .group_by(CostPool.id, CostPool.pool_number, CostPool.amount)
        .order_by(CostPool.pool_number)
    ).all()

    source_total = ZERO
    allocated_total = ZERO
    allocation_count = 0
    unreconciled: list[str] = []
    for _pool_id, number, amount, allocated, count in rows:
        source_total += money(Decimal(amount))
        allocated_total += money(Decimal(allocated))
        allocation_count += int(count)
        if (
            calculator.reconciles(pool_amount=Decimal(amount), allocated=[Decimal(allocated)])
            != ZERO
        ):
            unreconciled.append(number)
    variance = money(source_total) - money(allocated_total)
    return Reconciliation(
        reconciled=not unreconciled and variance == ZERO,
        source_cost_total=money(source_total),
        allocated_cost_total=money(allocated_total),
        variance=variance,
        pool_count=len(rows),
        allocation_count=allocation_count,
        unreconciled_pools=unreconciled,
    )


def stale_sources(session: Session, *, version: AllocationVersion) -> list[str]:
    """Everything this version divided that has since moved. Empty is fresh.

    Three kinds of drift, each of which would make the allocation describe a
    project that no longer exists: a unit re-measured and re-approved, a price
    re-activated, and the land register corrected. Checked before submission and
    again immediately before activation, because the window between those two is
    exactly where a superseded area schedule slips through.
    """
    problems: list[str] = []

    schedules = session.execute(
        select(Allocation.unit_id, Allocation.source_area_schedule_id).where(
            Allocation.allocation_version_id == version.id,
            Allocation.source_area_schedule_id.is_not(None),
        )
    ).all()
    if schedules:
        current = dict(
            session.execute(
                select(UnitAreaSchedule.unit_id, UnitAreaSchedule.id).where(
                    UnitAreaSchedule.unit_id.in_([unit_id for unit_id, _ in schedules]),
                    UnitAreaSchedule.status == AREA_SCHEDULE_APPROVED,
                )
            ).all()
        )
        moved = sorted(
            {unit_id for unit_id, snapshot in schedules if current.get(unit_id) != snapshot}
        )
        if moved:
            problems.append(
                "the approved area schedule changed for " + _named(session, list(moved))
            )

    prices = session.execute(
        select(Allocation.unit_id, Allocation.source_price_version_id).where(
            Allocation.allocation_version_id == version.id,
            Allocation.source_price_version_id.is_not(None),
        )
    ).all()
    if prices:
        current_prices = dict(
            session.execute(
                select(UnitPriceVersion.unit_id, UnitPriceVersion.id).where(
                    UnitPriceVersion.unit_id.in_([unit_id for unit_id, _ in prices]),
                    UnitPriceVersion.status == PRICE_ACTIVE,
                )
            ).all()
        )
        moved = sorted(
            {unit_id for unit_id, snapshot in prices if current_prices.get(unit_id) != snapshot}
        )
        if moved:
            problems.append("the approved price changed for " + _named(session, list(moved)))

    land_pools = list(
        session.scalars(
            select(CostPool).where(
                CostPool.allocation_version_id == version.id,
                CostPool.source_kind == SOURCE_PROJECT_LAND,
            )
        )
    )
    if land_pools:
        current_land = project_land_total(session, project_id=version.project_id)
        drifted = [pool.pool_number for pool in land_pools if money(pool.amount) != current_land]
        if drifted:
            problems.append("the land register total changed under " + ", ".join(sorted(drifted)))
    return problems


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #


def _require_ready_to_submit(session: Session, *, version: AllocationVersion) -> None:
    """Every gate a cost basis passes before a second person is asked to sign it."""
    if version.calculated_at is None:
        raise ConflictError("This cost basis has not been calculated since it was last changed.")
    pools = list(
        session.scalars(select(CostPool).where(CostPool.allocation_version_id == version.id))
    )
    if not pools:
        raise ConflictError("This cost basis has no pools, so there is nothing to approve.")

    categories = {pool.category for pool in pools}
    missing = [name for name in REQUIRED_CATEGORIES if name not in categories]
    if missing:
        raise ConflictError(
            "A cost basis must address land, hard and soft cost explicitly. Missing: "
            + ", ".join(missing)
            + ". Record a zero pool where the cost is genuinely nil rather than "
            "leaving it out."
        )
    if version.finance_treatment == FINANCE_ALLOCATED and CATEGORY_FINANCE not in categories:
        raise ConflictError(
            "This cost basis allocates finance cost but has no finance pool. Add "
            "one, or record finance cost as excluded."
        )

    summary = reconcile(session, version=version)
    if summary.allocation_count == 0:
        raise ConflictError("This cost basis has no allocations, so no unit carries any cost.")
    if not summary.reconciled:
        raise ConflictError(
            "This cost basis does not reconcile. These pools do not equal the sum "
            "of their allocations: " + ", ".join(summary.unreconciled_pools) + "."
        )
    problems = stale_sources(session, version=version)
    if problems:
        raise ConflictError(
            "This cost basis was calculated against sources that have since "
            "changed — " + "; ".join(problems) + ". Recalculate before submitting."
        )


def submit_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> AllocationVersion:
    """Freeze a draft's inputs and put it in front of a checker."""
    permissions.require_economics_writer(actor)
    project = lock_project(session, project.id)
    version = _lock_version(session, project_id=project.id, version_id=version_id)
    _require_draft(version)
    _require_ready_to_submit(session, version=version)

    version.status = VERSION_SUBMITTED
    version.submitted_at = _now()
    version.submitted_by_user_id = actor.user_id
    session.flush()
    summary = reconcile(session, version=version)
    record_event(
        session,
        action="unit_economics.version_submitted",
        entity_type=ENTITY_VERSION,
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "version_number": version.version_number,
            "source_cost_total": summary.source_cost_total,
            "allocated_cost_total": summary.allocated_cost_total,
            "pool_count": summary.pool_count,
            "allocation_count": summary.allocation_count,
        },
    )
    return version


def approve_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    reason: str | None,
    correlation_id: uuid.UUID,
) -> AllocationVersion:
    """Sign a submitted cost basis. Never the person who submitted it."""
    permissions.require_economics_approver(actor)
    project = lock_project(session, project.id)
    version = _lock_version(session, project_id=project.id, version_id=version_id)
    if version.status != VERSION_SUBMITTED:
        raise ConflictError("Only a submitted cost basis can be approved.")
    if version.submitted_by_user_id is not None:
        permissions.require_different_approver(
            actor, submitted_by_user_id=version.submitted_by_user_id
        )

    version.status = VERSION_APPROVED
    version.approved_at = _now()
    version.approved_by_user_id = actor.user_id
    session.flush()
    record_event(
        session,
        action="unit_economics.version_approved",
        entity_type=ENTITY_VERSION,
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={"version_number": version.version_number},
    )
    return version


def reject_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> AllocationVersion:
    """Refuse a submitted cost basis, with the reason on the record."""
    permissions.require_economics_approver(actor)
    detail = _text(reason, detail="Say why this cost basis is being rejected.")
    project = lock_project(session, project.id)
    version = _lock_version(session, project_id=project.id, version_id=version_id)
    if version.status != VERSION_SUBMITTED:
        raise ConflictError("Only a submitted cost basis can be rejected.")
    if version.submitted_by_user_id is not None:
        permissions.require_different_approver(
            actor, submitted_by_user_id=version.submitted_by_user_id
        )

    version.status = VERSION_REJECTED
    version.rejected_at = _now()
    version.rejected_by_user_id = actor.user_id
    version.rejection_reason = detail
    session.flush()
    record_event(
        session,
        action="unit_economics.version_rejected",
        entity_type=ENTITY_VERSION,
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=detail,
        after={"version_number": version.version_number},
    )
    return version


def activate_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> AllocationVersion:
    """Make an approved basis current, and close the window of the one it replaces.

    One transaction, under the project lock, because "at most one active version"
    spans two rows. The partial unique index is the backstop; the lock is what
    makes the loser get a sentence rather than a constraint violation.

    Freshness is re-checked here and not only at submission. Approval can be
    hours or weeks before activation, and an area schedule superseded in between
    would otherwise become governing economics nobody could reproduce.
    """
    permissions.require_economics_writer(actor)
    project = lock_project(session, project.id)
    version = _lock_version(session, project_id=project.id, version_id=version_id)
    if version.status != VERSION_APPROVED:
        raise ConflictError("Only an approved cost basis can be activated.")

    today = business_today()
    if version.effective_from > today:
        raise ConflictError(
            "This cost basis takes effect on "
            f"{version.effective_from.isoformat()} and cannot be made current before then."
        )

    summary = reconcile(session, version=version)
    if not summary.reconciled:
        raise ConflictError(
            "This cost basis no longer reconciles and cannot be made current: "
            + ", ".join(summary.unreconciled_pools)
            + "."
        )
    problems = stale_sources(session, version=version)
    if problems:
        raise ConflictError(
            "This cost basis was approved against sources that have since changed — "
            + "; ".join(problems)
            + ". Clone it, recalculate and have it approved again."
        )

    standing = session.scalars(
        select(AllocationVersion)
        .where(
            AllocationVersion.project_id == project.id,
            AllocationVersion.status == VERSION_ACTIVE,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if standing is not None:
        if version.effective_from <= standing.effective_from:
            raise ConflictError(
                "This cost basis starts on or before the one it would replace "
                f"({standing.effective_from.isoformat()}), which would restate a "
                "period that has already been governed."
            )
        standing.status = VERSION_SUPERSEDED
        standing.superseded_at = _now()
        standing.effective_to = version.effective_from
        # Flushed before the new version is made active, not with it. The
        # partial unique index is not deferrable, and the unit of work orders
        # two updates to the same table by identity rather than by the order
        # they were assigned — so without this the pair can reach PostgreSQL
        # with both rows briefly active, which is a constraint violation the
        # operator would read as a bug rather than as the guard working.
        session.flush()

    version.status = VERSION_ACTIVE
    version.activated_at = _now()
    version.activated_by_user_id = actor.user_id
    version.effective_to = None
    session.flush()

    if standing is not None:
        record_event(
            session,
            action="unit_economics.version_superseded",
            entity_type=ENTITY_VERSION,
            entity_id=standing.id,
            correlation_id=correlation_id,
            actor_user_id=actor.user_id,
            after={
                "version_number": standing.version_number,
                "effective_to": standing.effective_to,
            },
        )
    record_event(
        session,
        action="unit_economics.version_activated",
        entity_type=ENTITY_VERSION,
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "version_number": version.version_number,
            "effective_from": version.effective_from,
            "source_cost_total": summary.source_cost_total,
            "allocated_cost_total": summary.allocated_cost_total,
        },
    )
    return version


# --------------------------------------------------------------------------- #
# Unit costs
# --------------------------------------------------------------------------- #


def record_unit_cost(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    unit: Unit,
    cost_type: str,
    basis: str,
    amount: Decimal,
    effective_date: date,
    sale_contract_id: uuid.UUID | None,
    reference: str | None,
    notes: str | None,
    correlation_id: uuid.UUID,
) -> UnitCost:
    """Record a cost that belongs to one unit without dividing anything.

    An actual cost must name the contract it was incurred on where the unit has
    one. A commission is earned on a specific deal, and a commission with no
    deal on it is a commission that will still be counted against the unit after
    the buyer walks away.
    """
    permissions.require_economics_writer(actor)
    if cost_type not in UNIT_COST_TYPES:
        raise ValidationError("That is not a unit cost type.")
    if basis not in (BASIS_FORECAST, BASIS_ACTUAL):
        raise ValidationError("A unit cost is either forecast or actual.")
    if amount <= 0:
        raise ValidationError("A unit cost must be for a positive amount.")
    if basis == BASIS_ACTUAL and effective_date > business_today():
        raise ValidationError(
            "An actual cost records something that happened. It cannot be dated in the future."
        )

    project = lock_project(session, project.id)
    sale: SaleContract | None = None
    if sale_contract_id is not None:
        sale = session.scalars(
            select(SaleContract).where(
                SaleContract.id == sale_contract_id,
                SaleContract.project_id == project.id,
                SaleContract.unit_id == unit.id,
            )
        ).first()
        if sale is None:
            raise NotFoundError("Sale contract not found.")
    elif basis == BASIS_ACTUAL:
        live = _live_sale(session, unit_id=unit.id)
        if live is not None:
            raise ValidationError(
                "This unit has a live contract, so an actual cost must say which "
                "sale it was incurred on."
            )

    cost = UnitCost(
        project_id=project.id,
        unit_id=unit.id,
        sale_contract_id=sale.id if sale is not None else None,
        currency_id=project.base_currency_id,
        cost_type=cost_type,
        basis=basis,
        amount=money(amount),
        effective_date=effective_date,
        reference=(reference or "").strip() or None,
        notes=notes,
        status=COST_ACTIVE,
        created_by_user_id=actor.user_id,
    )
    session.add(cost)
    session.flush()
    record_event(
        session,
        action="unit_economics.unit_cost_recorded",
        entity_type=ENTITY_UNIT_COST,
        entity_id=cost.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "unit_reference": unit.unit_reference,
            "cost_type": cost.cost_type,
            "basis": cost.basis,
            "amount": cost.amount,
            "effective_date": cost.effective_date,
        },
    )
    return cost


def reverse_unit_cost(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    cost_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> UnitCost:
    """Undo a recorded cost. The row stays, reversed, with the reason on it."""
    permissions.require_economics_writer(actor)
    detail = _text(reason, detail="Say why this cost is being reversed.")
    project = lock_project(session, project.id)
    cost = session.scalars(
        select(UnitCost).where(UnitCost.id == cost_id, UnitCost.project_id == project.id)
    ).first()
    if cost is None:
        raise permissions.unit_cost_not_found()
    allowed = permissions.visible_units(session, project_id=project.id, actor=actor)
    if allowed is not None:
        visible = session.scalars(
            select(Unit.id).where(Unit.id == cost.unit_id, Unit.id.in_(allowed))
        ).first()
        if visible is None:
            raise permissions.unit_cost_not_found()
    if cost.status == COST_REVERSED:
        raise ConflictError("This cost has already been reversed.")

    cost.status = COST_REVERSED
    cost.reversed_at = _now()
    cost.reversed_by_user_id = actor.user_id
    cost.reversal_reason = detail
    session.flush()
    record_event(
        session,
        action="unit_economics.unit_cost_reversed",
        entity_type=ENTITY_UNIT_COST,
        entity_id=cost.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=detail,
        after={"cost_type": cost.cost_type, "amount": cost.amount},
    )
    return cost


def _live_sale(session: Session, *, unit_id: uuid.UUID) -> SaleContract | None:
    return session.scalars(
        select(SaleContract).where(
            SaleContract.unit_id == unit_id,
            SaleContract.status.in_(SOLD_SALE_STATUSES),
        )
    ).first()


# --------------------------------------------------------------------------- #
# The read model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class UnitEconomics:
    """One unit's whole economic position, computed and never stored."""

    unit: Unit
    basis: str
    revenue_source: str | None
    revenue_source_id: uuid.UUID | None
    revenue_currency_id: uuid.UUID | None
    cost_currency_id: uuid.UUID
    version: AllocationVersion | None
    land_cost: Decimal
    hard_cost: Decimal
    soft_cost: Decimal
    allocated_finance_cost: Decimal
    direct_cost: Decimal
    variable_selling_cost: Decimal
    seller_cost: Decimal
    deal_finance_cost: Decimal
    revenue: Decimal | None
    profit: calculator.Profitability | None
    profitability_status: str
    below_margin_threshold: bool | None
    threshold_fraction: Decimal | None


@dataclass(frozen=True, slots=True)
class _Costs:
    """The unit-level cost rows that apply to one unit on one basis."""

    direct: Decimal
    selling: Decimal


def _cost_index(
    session: Session, *, project_id: uuid.UUID, unit_ids: list[uuid.UUID]
) -> dict[tuple[uuid.UUID, str, uuid.UUID | None], _Costs]:
    """Every active unit cost, grouped by unit, basis and contract. One query.

    Keyed by contract as well as basis because a sold unit's economics counts
    the costs of *its* deal. A commission recorded against a contract that was
    later cancelled must not follow the unit into the next sale.
    """
    if not unit_ids:
        return {}
    rows = session.execute(
        select(
            UnitCost.unit_id,
            UnitCost.basis,
            UnitCost.sale_contract_id,
            UnitCost.cost_type,
            func.sum(UnitCost.amount),
        )
        .where(
            UnitCost.project_id == project_id,
            UnitCost.unit_id.in_(unit_ids),
            UnitCost.status == COST_ACTIVE,
        )
        .group_by(UnitCost.unit_id, UnitCost.basis, UnitCost.sale_contract_id, UnitCost.cost_type)
    ).all()
    index: dict[tuple[uuid.UUID, str, uuid.UUID | None], list[Decimal]] = defaultdict(
        lambda: [ZERO, ZERO]
    )
    for unit_id, basis, sale_id, cost_type, total in rows:
        slot = 0 if UNIT_COST_CLASS_OF[cost_type] == CLASS_DIRECT else 1
        index[(unit_id, basis, sale_id)][slot] += money(Decimal(total))
    return {key: _Costs(direct=value[0], selling=value[1]) for key, value in index.items()}


def _allocation_index(
    session: Session, *, version_ids: set[uuid.UUID], unit_ids: list[uuid.UUID]
) -> dict[tuple[uuid.UUID, uuid.UUID], dict[str, Decimal]]:
    """Allocated cost per unit per version, split by category. One query.

    Never one query per unit: a register of eight hundred units asking four
    questions each is the shape that makes a screen unusable at exactly the
    scale it becomes worth reading.
    """
    if not version_ids or not unit_ids:
        return {}
    rows = session.execute(
        select(
            Allocation.allocation_version_id,
            Allocation.unit_id,
            CostPool.category,
            func.sum(Allocation.allocated_amount),
        )
        .join(CostPool, CostPool.id == Allocation.cost_pool_id)
        .where(
            Allocation.allocation_version_id.in_(version_ids),
            Allocation.unit_id.in_(unit_ids),
        )
        .group_by(Allocation.allocation_version_id, Allocation.unit_id, CostPool.category)
    ).all()
    index: dict[tuple[uuid.UUID, uuid.UUID], dict[str, Decimal]] = defaultdict(
        lambda: dict.fromkeys(POOL_CATEGORIES, ZERO)
    )
    for version_id, unit_id, category, total in rows:
        index[(version_id, unit_id)][category] = money(Decimal(total))
    return index


def _threshold_fraction(session: Session, *, project: Project) -> Decimal | None:
    """The minimum margin this project's country pack expects, if it sets one.

    Read from settings rather than restated here. A second minimum-margin field
    owned by this module would be a second policy, and the two would disagree
    the first time somebody updated one of them.
    """
    return session.scalar(
        select(CountryApprovalThreshold.minimum_margin_rate_fraction).where(
            CountryApprovalThreshold.country_pack_id == project.country_pack_id
        )
    )


def _economics_for(
    *,
    project: Project,
    unit: Unit,
    sale: SaleContract | None,
    price: UnitPriceVersion | None,
    version: AllocationVersion | None,
    allocated: dict[str, Decimal],
    costs: _Costs,
    seller_costs: sales_service.FrozenSellerCosts | None,
    reconciled: bool,
    threshold: Decimal | None,
) -> UnitEconomics:
    """Assemble one unit's position from facts already loaded. No queries here.

    Revenue for a sold unit is the net contract price — after the concessions
    the buyer received, before the costs the seller absorbed. Those costs are
    subtracted below, on their own layers. Using the contract's
    ``effective_net_revenue_snapshot`` instead would subtract them a second time
    and produce a margin that is wrong and internally consistent, which is the
    worst combination available.
    """
    sold = sale is not None
    basis = BASIS_SOLD if sold else BASIS_FORECAST
    land = allocated.get(CATEGORY_LAND, ZERO)
    hard = allocated.get(CATEGORY_HARD, ZERO)
    soft = allocated.get(CATEGORY_SOFT, ZERO)
    allocated_finance = (
        allocated.get(CATEGORY_FINANCE, ZERO)
        if version is not None and version.finance_treatment == FINANCE_ALLOCATED
        else ZERO
    )
    seller_commercial = seller_costs.commercial if seller_costs is not None else ZERO
    seller_finance = seller_costs.finance if seller_costs is not None else ZERO

    if sold and sale is not None:
        revenue: Decimal | None = money(sale.net_contract_price_ex_tax)
        revenue_source: str | None = REVENUE_FROM_SALE
        revenue_source_id: uuid.UUID | None = sale.id
        revenue_currency: uuid.UUID | None = sale.currency_id
    elif price is not None:
        revenue = money(price.reference_price_ex_tax)
        revenue_source = REVENUE_FROM_PRICE
        revenue_source_id = price.id
        revenue_currency = price.currency_id
    else:
        revenue = None
        revenue_source = None
        revenue_source_id = None
        revenue_currency = None

    status = PROFIT_READY
    if revenue is None:
        status = PROFIT_MISSING_REVENUE
    elif version is None:
        status = PROFIT_MISSING_COST_BASIS
    elif revenue_currency != project.base_currency_id:
        status = PROFIT_CURRENCY_MISMATCH
    elif not reconciled or (seller_costs is not None and not seller_costs.reconciled):
        status = PROFIT_UNRECONCILED

    profit: calculator.Profitability | None = None
    below: bool | None = None
    if status == PROFIT_READY and revenue is not None:
        profit = calculator.profitability(
            revenue=revenue,
            costs=calculator.CostInputs(
                direct_cost=costs.direct,
                land_cost=land,
                hard_cost=hard,
                soft_cost=soft,
                variable_selling_cost=costs.selling,
                commercial_seller_cost=seller_commercial,
                allocated_finance_cost=allocated_finance,
                deal_finance_cost=seller_finance,
            ),
        )
        if threshold is not None and profit.margin_fraction is not None:
            below = profit.margin_fraction < threshold

    return UnitEconomics(
        unit=unit,
        basis=basis,
        revenue_source=revenue_source,
        revenue_source_id=revenue_source_id,
        revenue_currency_id=revenue_currency,
        cost_currency_id=project.base_currency_id,
        version=version,
        land_cost=land,
        hard_cost=hard,
        soft_cost=soft,
        allocated_finance_cost=allocated_finance,
        direct_cost=costs.direct,
        variable_selling_cost=costs.selling,
        seller_cost=seller_commercial,
        deal_finance_cost=seller_finance,
        revenue=revenue,
        profit=profit,
        profitability_status=status,
        below_margin_threshold=below,
        threshold_fraction=threshold,
    )


def _reconciled_versions(session: Session, *, version_ids: set[uuid.UUID]) -> dict[uuid.UUID, bool]:
    """Which of these versions still add up. One grouped query, not one per unit."""
    if not version_ids:
        return {}
    rows = session.execute(
        select(
            CostPool.allocation_version_id,
            CostPool.id,
            CostPool.amount,
            func.coalesce(func.sum(Allocation.allocated_amount), 0),
        )
        .select_from(CostPool)
        .outerjoin(Allocation, Allocation.cost_pool_id == CostPool.id)
        .where(CostPool.allocation_version_id.in_(version_ids))
        .group_by(CostPool.allocation_version_id, CostPool.id, CostPool.amount)
    ).all()
    verdict = dict.fromkeys(version_ids, True)
    for version_id, _pool_id, amount, allocated in rows:
        if money(Decimal(amount)) != money(Decimal(allocated)):
            verdict[version_id] = False
    return verdict


def unit_register(
    session: Session, *, project: Project, actor: ActorContext
) -> list[UnitEconomics]:
    """Every unit's economics, in a fixed handful of queries.

    Batched deliberately. The register is the screen a finance director opens on
    a project with eight hundred units, and the version of it that asked four
    questions per row would take three thousand round trips to say what this one
    says in about a dozen.
    """
    permissions.require_economics_reader(actor)

    statement = (
        select(Unit)
        .join(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .where(Unit.project_id == project.id, Unit.is_active.is_(True))
    )
    allowed = permissions.visible_units(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(Unit.id.in_(allowed))
    units = list(session.scalars(statement.order_by(Unit.sequence, Unit.unit_reference)))
    unit_ids = [unit.id for unit in units]
    if not unit_ids:
        return []

    sales = {
        sale.unit_id: sale
        for sale in session.scalars(
            select(SaleContract).where(
                SaleContract.project_id == project.id,
                SaleContract.unit_id.in_(unit_ids),
                SaleContract.status.in_(SOLD_SALE_STATUSES),
            )
        )
    }
    prices = _active_prices(session, unit_ids=unit_ids)
    standing = active_version(session, project_id=project.id)

    governing = list(
        session.scalars(
            select(AllocationVersion).where(
                AllocationVersion.project_id == project.id,
                AllocationVersion.status.in_(VERSION_GOVERNING),
            )
        )
    )
    by_id = {version.id: version for version in governing}

    def version_for(unit_id: uuid.UUID) -> AllocationVersion | None:
        sale = sales.get(unit_id)
        if sale is None:
            return standing
        for version in governing:
            if version.effective_from <= sale.contract_date and (
                version.effective_to is None or sale.contract_date < version.effective_to
            ):
                return version
        return None

    chosen = {unit_id: version_for(unit_id) for unit_id in unit_ids}
    version_ids = {version.id for version in chosen.values() if version is not None}
    allocations = _allocation_index(session, version_ids=version_ids, unit_ids=unit_ids)
    costs = _cost_index(session, project_id=project.id, unit_ids=unit_ids)
    reconciled = _reconciled_versions(session, version_ids=version_ids)
    threshold = _threshold_fraction(session, project=project)

    rows: list[UnitEconomics] = []
    for unit in units:
        sale = sales.get(unit.id)
        version = chosen.get(unit.id)
        key = (
            (unit.id, BASIS_ACTUAL, sale.id)
            if sale is not None
            else (unit.id, BASIS_FORECAST, None)
        )
        rows.append(
            _economics_for(
                project=project,
                unit=unit,
                sale=sale,
                price=prices.get(unit.id),
                version=version,
                allocated=allocations.get(
                    (version.id, unit.id) if version is not None else (unit.id, unit.id),
                    {},
                ),
                costs=costs.get(key, _Costs(direct=ZERO, selling=ZERO)),
                seller_costs=(
                    sales_service.frozen_seller_costs(sale) if sale is not None else None
                ),
                reconciled=reconciled.get(version.id, True) if version is not None else True,
                threshold=threshold,
            )
        )
    _ = by_id
    return rows


def unit_economics(
    session: Session, *, project: Project, actor: ActorContext, unit: Unit
) -> UnitEconomics:
    """One unit's economics, on whichever basis its commercial state calls for."""
    permissions.require_economics_reader(actor)
    sale = _live_sale(session, unit_id=unit.id)
    version = (
        version_governing_on(session, project_id=project.id, on=sale.contract_date)
        if sale is not None
        else active_version(session, project_id=project.id)
    )
    return _one(session, project=project, unit=unit, sale=sale, version=version)


def sale_economics(
    session: Session, *, project: Project, actor: ActorContext, sale: SaleContract
) -> UnitEconomics:
    """One sale's economics, on the basis that governed when it was signed.

    Answers the question a cancelled deal still raises: what did we make on it?
    A contract that has been unwound keeps its revenue, its costs and its cost
    basis, because deleting the economics of a failed sale is how a business
    stops learning from them.
    """
    permissions.require_economics_reader(actor)
    unit = session.get(Unit, sale.unit_id)
    if unit is None:  # pragma: no cover - a sale cannot outlive its unit
        raise NotFoundError("Unit not found.")
    version = version_governing_on(session, project_id=project.id, on=sale.contract_date)
    return _one(session, project=project, unit=unit, sale=sale, version=version)


def _one(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    sale: SaleContract | None,
    version: AllocationVersion | None,
) -> UnitEconomics:
    """One unit, assembled the same way the register assembles all of them."""
    version_ids = {version.id} if version is not None else set()
    allocations = _allocation_index(session, version_ids=version_ids, unit_ids=[unit.id])
    costs = _cost_index(session, project_id=project.id, unit_ids=[unit.id])
    key = (unit.id, BASIS_ACTUAL, sale.id) if sale is not None else (unit.id, BASIS_FORECAST, None)
    prices = _active_prices(session, unit_ids=[unit.id])
    reconciled = _reconciled_versions(session, version_ids=version_ids)
    return _economics_for(
        project=project,
        unit=unit,
        sale=sale,
        price=prices.get(unit.id),
        version=version,
        allocated=allocations.get((version.id, unit.id), {}) if version is not None else {},
        costs=costs.get(key, _Costs(direct=ZERO, selling=ZERO)),
        seller_costs=sales_service.frozen_seller_costs(sale) if sale is not None else None,
        reconciled=reconciled.get(version.id, True) if version is not None else True,
        threshold=_threshold_fraction(session, project=project),
    )


@dataclass(frozen=True, slots=True)
class ProjectEconomics:
    """The project's current blended position, and what it could not include."""

    currency_id: uuid.UUID
    totals: calculator.PortfolioTotals
    unit_count: int
    sold_count: int
    unsold_count: int
    negative_profit_count: int
    below_threshold_count: int
    incomplete_count: int
    currency_mismatch_count: int
    threshold_fraction: Decimal | None
    active_version: AllocationVersion | None


def project_economics(
    session: Session, *, project: Project, actor: ActorContext
) -> tuple[ProjectEconomics, list[UnitEconomics]]:
    """The blended current view: locked where sold, expected where not.

    Sold units keep the revenue they were sold at and the cost basis that
    governed then; unsold units use today's approved price and today's basis.
    That mixture is what a developer actually manages — revaluing sold units to
    today's list price would produce a profit nobody can collect.
    """
    rows = unit_register(session, project=project, actor=actor)
    ready = [row.profit for row in rows if row.profit is not None]
    totals = calculator.portfolio(ready)
    return (
        ProjectEconomics(
            currency_id=project.base_currency_id,
            totals=totals,
            unit_count=len(rows),
            sold_count=sum(1 for row in rows if row.basis == BASIS_SOLD),
            unsold_count=sum(1 for row in rows if row.basis == BASIS_FORECAST),
            negative_profit_count=sum(
                1 for row in rows if row.profit is not None and row.profit.profit_after_finance < 0
            ),
            below_threshold_count=sum(1 for row in rows if row.below_margin_threshold),
            incomplete_count=sum(
                1
                for row in rows
                if row.profitability_status
                in {PROFIT_MISSING_REVENUE, PROFIT_MISSING_COST_BASIS, PROFIT_UNRECONCILED}
            ),
            currency_mismatch_count=sum(
                1 for row in rows if row.profitability_status == PROFIT_CURRENCY_MISMATCH
            ),
            threshold_fraction=_threshold_fraction(session, project=project),
            active_version=active_version(session, project_id=project.id),
        ),
        rows,
    )


def waterfall(row: UnitEconomics) -> list[dict[str, Any]]:
    """The cost waterfall as an ordered list of labelled steps.

    Built here rather than in the browser because the order *is* the
    calculation: a frontend that owned the sequence could render a subtraction
    the backend never made, and it would look exactly as authoritative.
    """
    if row.profit is None:
        return []
    values: dict[str, Decimal] = {
        "revenue": row.profit.revenue,
        "land_cost": row.land_cost,
        "hard_cost": row.hard_cost,
        "soft_cost": row.soft_cost,
        "direct_cost": row.direct_cost,
        "gross_profit": row.profit.gross_profit,
        "variable_selling_cost": row.variable_selling_cost,
        "seller_cost": row.seller_cost,
        "contribution_profit": row.profit.contribution_profit,
        "finance_cost": row.profit.finance_cost,
        "profit_after_finance": row.profit.profit_after_finance,
    }
    return [
        {
            "key": key,
            "label": label,
            "amount": values[key],
            "is_subtotal": key in calculator.WATERFALL_SUBTOTALS,
        }
        for key, label in calculator.WATERFALL_STEPS
    ]
