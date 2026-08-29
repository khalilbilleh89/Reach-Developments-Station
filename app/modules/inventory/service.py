"""Inventory domain logic: hierarchy, units, areas, sub-assets and release.

Three rules run through the whole file.

**Nothing derived is stored.** Completeness, release eligibility, weighted
saleable area, parking and storage counts are computed from the rows that hold
the facts. A stored percentage is true on the day it is written and misleading
afterwards, and a dashboard reading a stale copy is how a development releases a
unit it should not have.

**Status moves through events.** A unit's commercial state changes only by
recording why and when. There is no ``PATCH {"commercial_status": ...}`` because
a register whose history can be skipped is not a record of what happened.

**Project first, then unit.** Locks are taken in one order across the codebase.
A foreign-key write takes a key-share lock on the parent, so a path locking the
child first would deadlock against one doing the reverse.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.patching import resolve_updates
from app.db.base import MEASURE_EXPONENT
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.models import (
    AREA_ROLE_INTERNAL,
    AREA_SCHEDULE_APPROVED,
    AREA_SCHEDULE_DRAFT,
    AREA_SCHEDULE_SUPERSEDED,
    CATEGORY_ACCESSIBILITY,
    CATEGORY_FLOOR_BAND,
    CATEGORY_FURNISHING,
    CATEGORY_GARDEN_CLASS,
    CATEGORY_ORIENTATION,
    CATEGORY_SUB_ASSET_SUBTYPE,
    CATEGORY_UNIT_TYPE,
    CATEGORY_VIEW_CLASS,
    COMMERCIAL_STATUS_AVAILABLE,
    COMMERCIAL_STATUS_HELD,
    COMMERCIAL_STATUS_UNRELEASED,
    DIMENSION_COMMERCIAL,
    ENTITY_AREA_SCHEDULE,
    ENTITY_AREA_TYPE,
    ENTITY_BUILDING,
    ENTITY_FLOOR,
    ENTITY_PHASE,
    ENTITY_PHASE_ACCESS,
    ENTITY_SUB_ASSET,
    ENTITY_UNIT,
    INVENTORY_COMMERCIAL_STATUSES,
    PHASE_STATUS_PLANNING,
    AreaType,
    Building,
    Floor,
    InventorySubAsset,
    Phase,
    Unit,
    UnitAreaSchedule,
    UnitAreaValue,
    UnitStatusEvent,
    UserPhaseAccess,
)
from app.modules.inventory.permissions import (
    visible_phase_ids,
    visible_sub_assets,
    visible_units,
)
from app.modules.projects.models import (
    PHASE_SCOPE_ALL,
    PHASE_SCOPE_SELECTED,
    Project,
    UserProjectAccess,
)
from app.modules.projects.service import lock_project
from app.modules.settings.service import require_active_reference_value

#: Codes are typed, read aloud and quoted, so they stay to characters that
#: survive all three.
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_FLOOR_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,16}$")
#: A unit reference is a business label, normalised only enough to be comparable.
_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9 ._/-]{1,64}$")

#: Unique constraint names mapped to the conflict a client should see. The
#: service checks first for a clear message; this catches the race where two
#: requests both pass that check and the database decides between them.
_CONFLICTS = {
    "uq_phases_project_id_code": "A phase with that code already exists in this project.",
    "uq_buildings_phase_id_code": "A building with that code already exists in this phase.",
    "uq_floors_building_id_code": "A floor with that code already exists in this building.",
    "uq_units_project_id_unit_reference": (
        "A unit with that reference already exists in this project."
    ),
    "uq_units_floor_id_unit_number": "A unit with that number already exists on this floor.",
    "uq_inventory_sub_assets_project_id_asset_reference": (
        "A sub-asset with that reference already exists in this project."
    ),
    "uq_area_types_project_id_code": "An area type with that code already exists in this project.",
    "uq_area_types_one_internal": (
        "This project already has an active internal area type. A project has one "
        "primary internal area."
    ),
    "uq_unit_area_schedules_unit_id_revision_code": (
        "That revision code already exists for this unit."
    ),
    "uq_unit_area_schedules_current": "This unit already has an approved area schedule.",
    "uq_unit_area_values_unit_area_schedule_id_area_type_id": (
        "That area type appears twice on the same schedule."
    ),
    "uq_user_phase_access_user_id_phase_id": "That user already has a row for this phase.",
}


def _flush(session: Session) -> None:
    """Flush, turning a known uniqueness race into the message it deserves.

    A predictable conflict answering 500 tells the caller nothing and tells the
    log a lie about what went wrong.
    """
    try:
        session.flush()
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        detail = _CONFLICTS.get(constraint or "")
        if detail is None:
            raise
        session.rollback()
        raise ConflictError(detail) from exc


def _snapshot(instance: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(instance, field) for field in fields}


_PHASE_FIELDS = (
    "id",
    "project_id",
    "code",
    "name",
    "sequence",
    "status",
    "planned_start",
    "planned_completion",
    "notes",
    "is_active",
)
_BUILDING_FIELDS = (
    "id",
    "project_id",
    "phase_id",
    "code",
    "name",
    "zone",
    "block",
    "entrance_wing",
    "sequence",
    "is_active",
)
_FLOOR_FIELDS = (
    "id",
    "project_id",
    "building_id",
    "code",
    "label",
    "level_number",
    "sequence",
    "is_active",
)
_UNIT_FIELDS = (
    "id",
    "project_id",
    "floor_id",
    "unit_number",
    "unit_reference",
    "sequence",
    "asset_class",
    "unit_type_code",
    "bedrooms",
    "bathrooms",
    "has_maid_room",
    "is_duplex",
    "is_penthouse",
    "furnishing_specification_code",
    "floor_band_code",
    "orientation_code",
    "view_class_code",
    "is_corner",
    "pool_access",
    "accessibility_code",
    "garden_class_code",
    "plot_coverage_fraction",
    "commercial_status",
    "legal_status",
    "collection_status",
    "delivery_status",
    "drawings_approved",
    "legal_sale_eligible",
    "pricing_approved",
    "release_date",
    "release_batch",
    "block_reason",
    "is_active",
)
_SUB_ASSET_FIELDS = (
    "id",
    "project_id",
    "floor_id",
    "linked_unit_id",
    "asset_reference",
    "asset_type",
    "subtype_code",
    "area",
    "transfer_mode",
    "notes",
    "is_active",
)
_AREA_TYPE_FIELDS = (
    "id",
    "project_id",
    "code",
    "label",
    "area_role",
    "unit_of_measure",
    "weight_factor",
    "required_for_release",
    "sort_order",
    "is_active",
)
_SCHEDULE_FIELDS = (
    "id",
    "project_id",
    "unit_id",
    "revision_code",
    "status",
    "measurement_standard",
    "plan_revision",
    "source",
    "measured_date",
    "reconciled",
    "notes",
)


def _normalize_code(code: str, *, label: str, pattern: re.Pattern[str] = _CODE_PATTERN) -> str:
    """Upper-case and validate a hierarchy code."""
    normalized = code.strip().upper()
    if not pattern.match(normalized):
        raise ValidationError(f"{label} may contain only letters, digits, hyphen and underscore.")
    return normalized


def _normalize_reference(reference: str) -> str:
    """Trim and collapse whitespace in a unit or asset reference.

    Conservative on purpose: the reference is a business label people recognise,
    so it keeps its spacing and punctuation rather than being folded into a slug.
    """
    normalized = " ".join(reference.split())
    if not _REFERENCE_PATTERN.match(normalized):
        raise ValidationError(
            "A reference may contain only letters, digits, spaces and . _ - / characters."
        )
    return normalized


# --------------------------------------------------------------------------- #
# Phase
# --------------------------------------------------------------------------- #

_PHASE_UPDATABLE = (
    "name",
    "sequence",
    "status",
    "planned_start",
    "planned_completion",
    "notes",
    "is_active",
)
_PHASE_CLEARABLE = frozenset({"planned_start", "planned_completion", "notes"})


def _reload(session: Session, instance: object) -> None:
    """Re-read a row from the database after waiting for the project lock.

    A phase loaded by the route dependency was read before the lock was
    available. Deciding "has this phase any active buildings" against that copy
    is deciding against the state as it was before whoever held the lock
    committed. Refreshing costs one round trip and is the difference between a
    serialised decision and a hopeful one.
    """
    session.refresh(instance)


def list_phases(
    session: Session, *, project: Project, actor: ActorContext, include_inactive: bool = True
) -> list[Phase]:
    statement = select(Phase).where(Phase.project_id == project.id)
    if not include_inactive:
        statement = statement.where(Phase.is_active.is_(True))
    allowed = visible_phase_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(Phase.id.in_(allowed))
    return list(session.scalars(statement.order_by(Phase.sequence, Phase.code)))


def create_phase(
    session: Session,
    *,
    project: Project,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    code: str,
    name: str,
    **fields: object,
) -> Phase:
    project = lock_project(session, project.id)
    normalized = _normalize_code(code, label="A phase code")
    _require_ordered(fields.get("planned_start"), fields.get("planned_completion"))

    phase = Phase(
        project_id=project.id,
        code=normalized,
        name=name.strip(),
        status=fields.get("status") or PHASE_STATUS_PLANNING,
        sequence=fields.get("sequence") or 0,
        planned_start=fields.get("planned_start"),
        planned_completion=fields.get("planned_completion"),
        notes=fields.get("notes"),
        created_by_user_id=actor_user_id,
    )
    session.add(phase)
    _flush(session)
    record_event(
        session,
        action="phase.created",
        entity_type=ENTITY_PHASE,
        entity_id=phase.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(phase, _PHASE_FIELDS),
    )
    session.commit()
    session.refresh(phase)
    return phase


def update_phase(
    session: Session,
    *,
    phase: Phase,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> Phase:
    updates = resolve_updates(changes, fields=_PHASE_UPDATABLE, clearable=_PHASE_CLEARABLE)

    # Retiring a parent and creating a child are the same structural decision
    # seen from two directions, so they queue on the same project row. Without
    # it, "this phase has no active buildings" can be true when it is read and
    # false when it commits.
    lock_project(session, phase.project_id)
    _reload(session, phase)

    resulting_start = updates.get("planned_start", phase.planned_start)
    resulting_end = updates.get("planned_completion", phase.planned_completion)
    _require_ordered(resulting_start, resulting_end)

    if updates.get("is_active") is False and phase.is_active:
        _refuse_deactivation_with_children(session, phase=phase)

    before = _snapshot(phase, _PHASE_FIELDS)
    for field, value in updates.items():
        setattr(phase, field, value)
    _flush(session)
    record_event(
        session,
        action="phase.updated",
        entity_type=ENTITY_PHASE,
        entity_id=phase.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(phase, _PHASE_FIELDS),
    )
    session.commit()
    session.refresh(phase)
    return phase


def _require_ordered(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and end < start:
        raise ValidationError("Planned completion cannot be before planned start.")


def _refuse_deactivation_with_children(session: Session, *, phase: Phase) -> None:
    """Refuse to retire a phase that still holds live inventory.

    Deactivating the parent and leaving active buildings and units beneath it
    makes the register say two different things at once. There is deliberately
    no cascade: hidden mass deactivation is worse than an explicit refusal.
    """
    active_building = session.scalars(
        select(Building.id).where(Building.phase_id == phase.id, Building.is_active.is_(True))
    ).first()
    if active_building is not None:
        raise ConflictError("This phase still has active buildings. Deactivate or move them first.")


# --------------------------------------------------------------------------- #
# Building and floor
# --------------------------------------------------------------------------- #

_BUILDING_UPDATABLE = ("name", "zone", "block", "entrance_wing", "sequence", "is_active")
_BUILDING_CLEARABLE = frozenset({"zone", "block", "entrance_wing"})
_FLOOR_UPDATABLE = ("label", "level_number", "sequence", "is_active")
_FLOOR_CLEARABLE = frozenset({"level_number"})


def list_buildings(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    phase_id: uuid.UUID | None = None,
) -> list[Building]:
    statement = select(Building).where(Building.project_id == project.id)
    if phase_id is not None:
        statement = statement.where(Building.phase_id == phase_id)
    allowed = visible_phase_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(Building.phase_id.in_(allowed))
    return list(session.scalars(statement.order_by(Building.sequence, Building.code)))


def create_building(
    session: Session,
    *,
    project: Project,
    phase: Phase,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    code: str,
    name: str,
    **fields: object,
) -> Building:
    project = lock_project(session, project.id)
    # The phase was loaded before the lock was granted; whoever held it may have
    # retired the phase in the meantime.
    _reload(session, phase)
    if not phase.is_active:
        raise ConflictError("That phase is not active.")
    building = Building(
        project_id=project.id,
        phase_id=phase.id,
        code=_normalize_code(code, label="A building code"),
        name=name.strip(),
        zone=fields.get("zone"),
        block=fields.get("block"),
        entrance_wing=fields.get("entrance_wing"),
        sequence=fields.get("sequence") or 0,
        created_by_user_id=actor_user_id,
    )
    session.add(building)
    _flush(session)
    record_event(
        session,
        action="building.created",
        entity_type=ENTITY_BUILDING,
        entity_id=building.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(building, _BUILDING_FIELDS),
    )
    session.commit()
    session.refresh(building)
    return building


def update_building(
    session: Session,
    *,
    building: Building,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> Building:
    updates = resolve_updates(changes, fields=_BUILDING_UPDATABLE, clearable=_BUILDING_CLEARABLE)
    lock_project(session, building.project_id)
    _reload(session, building)
    if updates.get("is_active") is False and building.is_active:
        active_floor = session.scalars(
            select(Floor.id).where(Floor.building_id == building.id, Floor.is_active.is_(True))
        ).first()
        if active_floor is not None:
            raise ConflictError(
                "This building still has active floors. Deactivate or move them first."
            )

    before = _snapshot(building, _BUILDING_FIELDS)
    for field, value in updates.items():
        setattr(building, field, value)
    _flush(session)
    record_event(
        session,
        action="building.updated",
        entity_type=ENTITY_BUILDING,
        entity_id=building.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(building, _BUILDING_FIELDS),
    )
    session.commit()
    session.refresh(building)
    return building


def list_floors(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    building_id: uuid.UUID | None = None,
    phase_id: uuid.UUID | None = None,
) -> list[Floor]:
    statement = select(Floor).where(Floor.project_id == project.id)
    if building_id is not None:
        statement = statement.where(Floor.building_id == building_id)
    allowed = visible_phase_ids(session, project_id=project.id, actor=actor)
    if phase_id is not None or allowed is not None:
        buildings = select(Building.id).where(Building.project_id == project.id)
        if phase_id is not None:
            buildings = buildings.where(Building.phase_id == phase_id)
        if allowed is not None:
            buildings = buildings.where(Building.phase_id.in_(allowed))
        statement = statement.where(Floor.building_id.in_(buildings))
    return list(session.scalars(statement.order_by(Floor.sequence, Floor.code)))


def create_floor(
    session: Session,
    *,
    project: Project,
    building: Building,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    code: str,
    label: str,
    **fields: object,
) -> Floor:
    project = lock_project(session, project.id)
    _reload(session, building)
    if not building.is_active:
        raise ConflictError("That building is not active.")
    floor = Floor(
        project_id=project.id,
        building_id=building.id,
        code=_normalize_code(code, label="A floor code", pattern=_FLOOR_CODE_PATTERN),
        label=label.strip(),
        level_number=fields.get("level_number"),
        sequence=fields.get("sequence") or 0,
        created_by_user_id=actor_user_id,
    )
    session.add(floor)
    _flush(session)
    record_event(
        session,
        action="floor.created",
        entity_type=ENTITY_FLOOR,
        entity_id=floor.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(floor, _FLOOR_FIELDS),
    )
    session.commit()
    session.refresh(floor)
    return floor


def update_floor(
    session: Session,
    *,
    floor: Floor,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> Floor:
    updates = resolve_updates(changes, fields=_FLOOR_UPDATABLE, clearable=_FLOOR_CLEARABLE)
    lock_project(session, floor.project_id)
    _reload(session, floor)
    if updates.get("is_active") is False and floor.is_active:
        active_unit = session.scalars(
            select(Unit.id).where(Unit.floor_id == floor.id, Unit.is_active.is_(True))
        ).first()
        if active_unit is not None:
            raise ConflictError("This floor still has active units. Deactivate or move them first.")

    before = _snapshot(floor, _FLOOR_FIELDS)
    for field, value in updates.items():
        setattr(floor, field, value)
    _flush(session)
    record_event(
        session,
        action="floor.updated",
        entity_type=ENTITY_FLOOR,
        entity_id=floor.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(floor, _FLOOR_FIELDS),
    )
    session.commit()
    session.refresh(floor)
    return floor


def get_building(session: Session, *, project_id: uuid.UUID, building_id: uuid.UUID) -> Building:
    building = session.scalars(
        select(Building).where(Building.id == building_id, Building.project_id == project_id)
    ).first()
    if building is None:
        raise NotFoundError("Building not found.")
    return building


def get_floor(session: Session, *, project_id: uuid.UUID, floor_id: uuid.UUID) -> Floor:
    floor = session.scalars(
        select(Floor).where(Floor.id == floor_id, Floor.project_id == project_id)
    ).first()
    if floor is None:
        raise NotFoundError("Floor not found.")
    return floor


def phase_of_floor(session: Session, floor: Floor) -> Phase:
    building = session.get(Building, floor.building_id)
    if building is None:  # pragma: no cover - foreign keys make this unreachable
        raise NotFoundError("Building not found.")
    phase = session.get(Phase, building.phase_id)
    if phase is None:  # pragma: no cover - foreign keys make this unreachable
        raise NotFoundError("Phase not found.")
    return phase


# --------------------------------------------------------------------------- #
# Unit
# --------------------------------------------------------------------------- #

#: Reference-backed unit codes and the category each is drawn from.
_UNIT_REFERENCE_FIELDS = {
    "unit_type_code": CATEGORY_UNIT_TYPE,
    "furnishing_specification_code": CATEGORY_FURNISHING,
    "floor_band_code": CATEGORY_FLOOR_BAND,
    "orientation_code": CATEGORY_ORIENTATION,
    "view_class_code": CATEGORY_VIEW_CLASS,
    "accessibility_code": CATEGORY_ACCESSIBILITY,
    "garden_class_code": CATEGORY_GARDEN_CLASS,
}

_UNIT_UPDATABLE = (
    "floor_id",
    "unit_number",
    "unit_reference",
    "sequence",
    "asset_class",
    "unit_type_code",
    "bedrooms",
    "bathrooms",
    "has_maid_room",
    "is_duplex",
    "is_penthouse",
    "furnishing_specification_code",
    "floor_band_code",
    "orientation_code",
    "view_class_code",
    "is_corner",
    "pool_access",
    "accessibility_code",
    "garden_class_code",
    "plot_coverage_fraction",
    "is_active",
)
_UNIT_CLEARABLE = frozenset(
    {
        "unit_type_code",
        "bedrooms",
        "bathrooms",
        "furnishing_specification_code",
        "floor_band_code",
        "orientation_code",
        "view_class_code",
        "accessibility_code",
        "garden_class_code",
        "plot_coverage_fraction",
    }
)

#: The subset of unit fields ``create_unit`` accepts through ``**fields``. The
#: hierarchy and identity arrive as explicit arguments, so listing them here too
#: would let one call supply the same value twice.
_UNIT_FACT_FIELDS = tuple(
    field
    for field in _UNIT_UPDATABLE
    if field
    not in {"floor_id", "unit_number", "unit_reference", "asset_class", "is_active", "sequence"}
)

_RELEASE_UPDATABLE = (
    "drawings_approved",
    "legal_sale_eligible",
    "release_date",
    "release_batch",
    "block_reason",
)
_RELEASE_CLEARABLE = frozenset({"release_date", "release_batch", "block_reason"})


def _validate_unit_codes(
    session: Session, *, country_pack_id: uuid.UUID, values: dict[str, Any]
) -> None:
    """Check every configurable code a unit newly names.

    Only newly assigned codes are checked. A unit already carrying a since
    retired code keeps it: configuration moving on is not a reason to invalidate
    a record that was correct when it was made.
    """
    for field, category in _UNIT_REFERENCE_FIELDS.items():
        code = values.get(field)
        if code is not None:
            require_active_reference_value(
                session, category=category, code=code, country_pack_id=country_pack_id
            )


def lock_unit(session: Session, *, project_id: uuid.UUID, unit_id: uuid.UUID) -> Unit:
    """Take the unit row for update and return its committed state.

    Status is a read-then-write decision, and area approval decides which of a
    unit's schedules is current. Both must be judged against the locked row —
    see ``lock_project`` for why ``populate_existing`` is not optional.
    """
    unit = session.scalars(
        select(Unit)
        .where(Unit.id == unit_id, Unit.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if unit is None:
        raise NotFoundError("Unit not found.")
    return unit


def create_unit(
    session: Session,
    *,
    project: Project,
    floor: Floor,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    unit_number: str,
    unit_reference: str,
    asset_class: str,
    **fields: object,
) -> Unit:
    # The configurable codes below are validated against the project's country
    # pack, so read that project under lock: a jurisdiction change must either
    # land first and be validated against, or wait behind this unit.
    project = lock_project(session, project.id)
    _reload(session, floor)
    if not floor.is_active:
        raise ConflictError("That floor is not active.")
    _validate_unit_codes(session, country_pack_id=project.country_pack_id, values=fields)

    unit = Unit(
        project_id=project.id,
        floor_id=floor.id,
        unit_number=unit_number.strip(),
        unit_reference=_normalize_reference(unit_reference),
        asset_class=asset_class,
        sequence=fields.get("sequence") or 0,
        created_by_user_id=actor_user_id,
        **{
            key: value
            for key, value in fields.items()
            if key in _UNIT_FACT_FIELDS and value is not None
        },
    )
    session.add(unit)
    _flush(session)
    record_event(
        session,
        action="unit.created",
        entity_type=ENTITY_UNIT,
        entity_id=unit.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(unit, _UNIT_FIELDS),
    )
    session.commit()
    session.refresh(unit)
    return unit


def update_unit(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    actor: ActorContext,
    **changes: object,
) -> Unit:
    """Change a unit's physical and classification facts.

    A move between floors is accepted here, but only while the unit is still
    unreleased: changing the floor changes the building and the phase with it,
    and silently moving a held or sold unit into another phase would move it out
    of somebody's access and into somebody else's.
    """
    updates = resolve_updates(changes, fields=_UNIT_UPDATABLE, clearable=_UNIT_CLEARABLE)
    project = lock_project(session, project.id)
    unit = lock_unit(session, project_id=project.id, unit_id=unit.id)

    if "floor_id" in updates and updates["floor_id"] != unit.floor_id:
        if unit.commercial_status != COMMERCIAL_STATUS_UNRELEASED:
            raise ConflictError(
                "A unit can only be moved while it is unreleased. Return it to unreleased first."
            )
        target = get_floor(session, project_id=project.id, floor_id=updates["floor_id"])
        if not target.is_active:
            raise ConflictError("That floor is not active.")
        destination = phase_of_floor(session, target)
        if not destination.is_active:
            raise ConflictError("That phase is not active.")
        _require_phase_in_scope(session, project_id=project.id, actor=actor, phase=destination)
        _require_phase_in_scope(
            session,
            project_id=project.id,
            actor=actor,
            phase=phase_of_floor(session, session.get(Floor, unit.floor_id)),
        )

    if "unit_reference" in updates and updates["unit_reference"] is not None:
        updates["unit_reference"] = _normalize_reference(str(updates["unit_reference"]))
    if "unit_number" in updates and updates["unit_number"] is not None:
        updates["unit_number"] = str(updates["unit_number"]).strip()

    _validate_unit_codes(session, country_pack_id=project.country_pack_id, values=dict(updates))

    before = _snapshot(unit, _UNIT_FIELDS)
    for field, value in updates.items():
        setattr(unit, field, value)
    _flush(session)
    record_event(
        session,
        action="unit.updated",
        entity_type=ENTITY_UNIT,
        entity_id=unit.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(unit, _UNIT_FIELDS),
    )
    session.commit()
    session.refresh(unit)
    return unit


def _require_phase_in_scope(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext, phase: Phase
) -> None:
    allowed = visible_phase_ids(session, project_id=project_id, actor=actor)
    if allowed is not None and phase.id not in set(session.scalars(allowed)):
        raise NotFoundError("Phase not found.")


def update_release_controls(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> Unit:
    """Set the gates that decide whether a unit may be released.

    ``pricing_approved`` is not in ``_RELEASE_UPDATABLE`` and is not accepted by
    the request model either: PR-MVP-04 sets it when a real approved price
    exists. Per-field role checks happen in the route, because each field here
    has a different owner.
    """
    updates = resolve_updates(changes, fields=_RELEASE_UPDATABLE, clearable=_RELEASE_CLEARABLE)
    unit = lock_unit(session, project_id=project.id, unit_id=unit.id)

    before = _snapshot(unit, _UNIT_FIELDS)
    for field, value in updates.items():
        setattr(unit, field, value)
    _flush(session)
    record_event(
        session,
        action="unit.release_controls_updated",
        entity_type=ENTITY_UNIT,
        entity_id=unit.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(unit, _UNIT_FIELDS),
    )
    session.commit()
    session.refresh(unit)
    return unit


# --------------------------------------------------------------------------- #
# Commercial status
# --------------------------------------------------------------------------- #

#: The moves inventory owns. Everything else — reserved, contracted, cancelled,
#: returned — is created by a real sales transaction in PR-MVP-05.
_COMMERCIAL_TRANSITIONS: dict[str, frozenset[str]] = {
    COMMERCIAL_STATUS_UNRELEASED: frozenset({COMMERCIAL_STATUS_HELD, COMMERCIAL_STATUS_AVAILABLE}),
    COMMERCIAL_STATUS_HELD: frozenset({COMMERCIAL_STATUS_UNRELEASED, COMMERCIAL_STATUS_AVAILABLE}),
    COMMERCIAL_STATUS_AVAILABLE: frozenset({COMMERCIAL_STATUS_HELD, COMMERCIAL_STATUS_UNRELEASED}),
}

#: Moves that must say why. Holding a unit and pulling one back off the market
#: are both decisions somebody will have to account for later.
_REASON_REQUIRED = frozenset({COMMERCIAL_STATUS_HELD, COMMERCIAL_STATUS_UNRELEASED})


def latest_commercial_effective_date(session: Session, *, unit_id: uuid.UUID) -> date | None:
    """The effective date of this unit's most recent commercial event."""
    return session.scalars(
        select(func.max(UnitStatusEvent.effective_date)).where(
            UnitStatusEvent.unit_id == unit_id,
            UnitStatusEvent.dimension == DIMENSION_COMMERCIAL,
        )
    ).first()


def _require_forward_effective_date(session: Session, *, unit: Unit, effective_date: date) -> None:
    """Refuse a commercial event dated before the one it follows.

    The unit lock already stops two transitions forking the chain, but a linear
    chain can still carry dates that run backwards: held on the 10th, then
    available on the 1st. The statuses would be consistent and the history would
    be a fiction — and every later question asked of it ("what was this unit on
    the 5th?") has two answers.

    Permits have held this rule since PR-MVP-02. The same date is allowed: a
    correction recorded the same day is ordinary, and the event order carries
    the sequence.
    """
    latest = latest_commercial_effective_date(session, unit_id=unit.id)
    if latest is not None and effective_date < latest:
        raise ValidationError(
            f"This unit's last commercial change was effective {latest.isoformat()}. "
            "A later change cannot be dated before it."
        )


def transition_commercial_status(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    to_status: str,
    effective_date: date,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason: str | None = None,
    notes: str | None = None,
    actor: ActorContext | None = None,
) -> Unit:
    """Move a unit between the commercial states inventory owns.

    One transaction: the appended event, the unit's new state and the audit
    entry all commit together, so the register can never show a status whose
    history is missing.
    """
    unit = lock_unit(session, project_id=project.id, unit_id=unit.id)
    from_status = unit.commercial_status

    if to_status not in INVENTORY_COMMERCIAL_STATUSES:
        raise ValidationError(
            "Inventory can move a unit between unreleased, held and available only. "
            "Reserved and contracted are created by a sale."
        )
    if from_status not in _COMMERCIAL_TRANSITIONS:
        raise ConflictError(
            f"A unit that is {from_status.replace('_', ' ')} is no longer inventory's to move."
        )
    if to_status == from_status:
        raise ValidationError("That unit is already in this status.")
    if to_status not in _COMMERCIAL_TRANSITIONS[from_status]:
        raise ConflictError(
            f"A unit cannot move from {from_status.replace('_', ' ')} "
            f"to {to_status.replace('_', ' ')}."
        )
    if to_status in _REASON_REQUIRED and not (reason or "").strip():
        raise ValidationError("A reason is required for this change.")
    _require_forward_effective_date(session, unit=unit, effective_date=effective_date)

    if to_status == COMMERCIAL_STATUS_AVAILABLE:
        blockers = release_blockers(session, unit=unit, today=effective_date, actor=actor)
        if blockers:
            raise ConflictError("This unit cannot be released yet: " + "; ".join(blockers) + ".")

    before = _snapshot(unit, _UNIT_FIELDS)
    unit.commercial_status = to_status
    session.add(
        UnitStatusEvent(
            unit_id=unit.id,
            dimension=DIMENSION_COMMERCIAL,
            from_status=from_status,
            to_status=to_status,
            effective_date=effective_date,
            reason=(reason or "").strip() or None,
            notes=notes,
            changed_by_user_id=actor_user_id,
        )
    )
    _flush(session)
    record_event(
        session,
        action="unit.commercial_status_changed",
        entity_type=ENTITY_UNIT,
        entity_id=unit.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        reason=reason,
        before=before,
        after=_snapshot(unit, _UNIT_FIELDS),
    )
    session.commit()
    session.refresh(unit)
    return unit


def list_status_events(
    session: Session, *, unit_id: uuid.UUID, dimension: str | None = None
) -> list[UnitStatusEvent]:
    statement = select(UnitStatusEvent).where(UnitStatusEvent.unit_id == unit_id)
    if dimension is not None:
        statement = statement.where(UnitStatusEvent.dimension == dimension)
    return list(
        session.scalars(
            statement.order_by(UnitStatusEvent.effective_date, UnitStatusEvent.changed_at)
        )
    )


# --------------------------------------------------------------------------- #
# Area types and schedules
# --------------------------------------------------------------------------- #

_AREA_TYPE_UPDATABLE = (
    "label",
    "area_role",
    "unit_of_measure",
    "weight_factor",
    "required_for_release",
    "sort_order",
    "is_active",
)
_SCHEDULE_UPDATABLE = (
    "measurement_standard",
    "plan_revision",
    "source",
    "measured_date",
    "reconciled",
    "notes",
)
_SCHEDULE_CLEARABLE = frozenset(
    {"measurement_standard", "plan_revision", "source", "measured_date", "notes"}
)


def list_area_types(
    session: Session, *, project_id: uuid.UUID, include_inactive: bool = True
) -> list[AreaType]:
    statement = select(AreaType).where(AreaType.project_id == project_id)
    if not include_inactive:
        statement = statement.where(AreaType.is_active.is_(True))
    return list(session.scalars(statement.order_by(AreaType.sort_order, AreaType.code)))


#: The fields that decide what a stored measurement *means*. Everything else
#: about an area type describes it; these two reinterpret every number already
#: recorded against it.
_AREA_TYPE_SEMANTIC_FIELDS = ("area_role", "unit_of_measure")


def _area_type_in_use(session: Session, *, area_type_id: uuid.UUID) -> bool:
    """Whether any measurement has been recorded against this area type."""
    return (
        session.scalars(
            select(UnitAreaValue.id).where(UnitAreaValue.area_type_id == area_type_id).limit(1)
        ).first()
        is not None
    )


def weighted_contributors(*, project_id: uuid.UUID) -> Select[tuple[AreaType]]:
    """Every area type whose unit still shapes this project's weighted total.

    "Active" is not the right population, and using it was a way for the label
    to start lying. ``area_lines`` multiplies a stored measurement by its area
    type's factor whether or not that type is still active, so a retired sqm
    type with measurements against it keeps contributing sqm to every approved
    schedule that references it. Leaving it out of the coherence check let a new
    sqft type in beside it, and then the weighted figure was a sum of two units
    with one of their names on it.

    So a contributor is any type with a non-zero factor that is either active or
    still referenced by a recorded measurement. Retiring a type does not remove
    its contribution; setting its factor to zero does, and that is an explicit,
    audited act.
    """
    used = select(UnitAreaValue.area_type_id).where(UnitAreaValue.area_type_id == AreaType.id)
    return (
        select(AreaType)
        .where(
            AreaType.project_id == project_id,
            AreaType.weight_factor != 0,
            AreaType.is_active.is_(True) | used.exists(),
        )
        .order_by(AreaType.sort_order, AreaType.code)
    )


def _require_coherent_weighted_unit(
    session: Session,
    *,
    project_id: uuid.UUID,
    area_type_id: uuid.UUID | None,
    unit_of_measure: str,
    weight_factor: Decimal,
    is_active: bool,
    in_use: bool = False,
) -> None:
    """Every area that contributes to the weighted total must measure the same way.

    The weighted saleable area is a sum. Adding 100 sqm to 200 sqft produces a
    number with no unit and no meaning, and this MVP has no conversion — nor
    should it acquire one to paper over a configuration mistake. So the project
    picks one unit for everything it weighs, and the second unit is refused at
    the point somebody configures it.

    An area type with a zero factor contributes nothing to the sum, so it may
    measure in whatever the drawings use. One that has been retired but still has
    measurements against it does contribute, so it is checked too.
    """
    if weight_factor == 0 or not (is_active or in_use):
        return
    statement = weighted_contributors(project_id=project_id)
    if area_type_id is not None:
        statement = statement.where(AreaType.id != area_type_id)
    for other in session.scalars(statement):
        if other.unit_of_measure != unit_of_measure:
            raise ValidationError(
                f"This project weighs areas in {other.unit_of_measure} "
                f"(see {other.code}). An area type that contributes to the weighted "
                f"saleable area cannot measure in {unit_of_measure}: the total would "
                "add two different units together."
            )


def weighted_area_unit(session: Session, *, project_id: uuid.UUID) -> str | None:
    """The unit the project's weighted saleable area is expressed in.

    ``None`` when nothing contributes yet. Read from exactly the population the
    calculation uses, so the label and the number can never describe different
    sets of area types.
    """
    contributor = session.scalars(weighted_contributors(project_id=project_id)).first()
    return contributor.unit_of_measure if contributor is not None else None


def create_area_type(
    session: Session,
    *,
    project: Project,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    code: str,
    label: str,
    area_role: str,
    weight_factor: Decimal,
    **fields: object,
) -> AreaType:
    project = lock_project(session, project.id)
    _require_coherent_weighted_unit(
        session,
        project_id=project.id,
        area_type_id=None,
        unit_of_measure=str(fields.get("unit_of_measure") or "sqm"),
        weight_factor=weight_factor,
        is_active=True,
    )
    area_type = AreaType(
        project_id=project.id,
        code=_normalize_code(code, label="An area type code"),
        label=label.strip(),
        area_role=area_role,
        unit_of_measure=fields.get("unit_of_measure") or "sqm",
        weight_factor=weight_factor,
        required_for_release=bool(fields.get("required_for_release")),
        sort_order=fields.get("sort_order") or 0,
        created_by_user_id=actor_user_id,
    )
    session.add(area_type)
    _flush(session)
    record_event(
        session,
        action="area_type.created",
        entity_type=ENTITY_AREA_TYPE,
        entity_id=area_type.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(area_type, _AREA_TYPE_FIELDS),
    )
    session.commit()
    session.refresh(area_type)
    return area_type


def update_area_type(
    session: Session,
    *,
    project: Project,
    area_type: AreaType,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> AreaType:
    """Change an area type.

    A factor change moves every weighted saleable area derived from it, which is
    why it is audited. It never touches a raw measured area: those are what the
    drawing says, and a configuration change does not re-measure a building.
    """
    updates = resolve_updates(changes, fields=_AREA_TYPE_UPDATABLE, clearable=frozenset())
    lock_project(session, project.id)
    _reload(session, area_type)

    in_use = _area_type_in_use(session, area_type_id=area_type.id)
    semantic = [
        field
        for field in _AREA_TYPE_SEMANTIC_FIELDS
        if field in updates and updates[field] != getattr(area_type, field)
    ]
    if semantic and in_use:
        raise ConflictError(
            "Measurements have already been recorded against this area type, so its "
            "role and unit of measure are fixed. Changing them would silently give "
            "every stored figure a new meaning without anyone re-measuring."
        )

    _require_coherent_weighted_unit(
        session,
        project_id=project.id,
        area_type_id=area_type.id,
        unit_of_measure=str(updates.get("unit_of_measure", area_type.unit_of_measure)),
        weight_factor=updates.get("weight_factor", area_type.weight_factor),  # type: ignore[arg-type]
        is_active=bool(updates.get("is_active", area_type.is_active)),
        in_use=in_use,
    )

    before = _snapshot(area_type, _AREA_TYPE_FIELDS)
    for field, value in updates.items():
        setattr(area_type, field, value)
    _flush(session)
    record_event(
        session,
        action="area_type.updated",
        entity_type=ENTITY_AREA_TYPE,
        entity_id=area_type.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(area_type, _AREA_TYPE_FIELDS),
    )
    session.commit()
    session.refresh(area_type)
    return area_type


def get_area_type(session: Session, *, project_id: uuid.UUID, area_type_id: uuid.UUID) -> AreaType:
    area_type = session.scalars(
        select(AreaType).where(AreaType.id == area_type_id, AreaType.project_id == project_id)
    ).first()
    if area_type is None:
        raise NotFoundError("Area type not found.")
    return area_type


def internal_area_type(session: Session, *, project_id: uuid.UUID) -> AreaType | None:
    """The project's one active internal area type, if it has configured one."""
    return session.scalars(
        select(AreaType).where(
            AreaType.project_id == project_id,
            AreaType.area_role == AREA_ROLE_INTERNAL,
            AreaType.is_active.is_(True),
        )
    ).first()


def list_area_schedules(session: Session, *, unit_id: uuid.UUID) -> list[UnitAreaSchedule]:
    return list(
        session.scalars(
            select(UnitAreaSchedule)
            .where(UnitAreaSchedule.unit_id == unit_id)
            .order_by(UnitAreaSchedule.created_at)
        )
    )


def get_area_schedule(
    session: Session, *, project_id: uuid.UUID, unit_id: uuid.UUID, schedule_id: uuid.UUID
) -> UnitAreaSchedule:
    schedule = session.scalars(
        select(UnitAreaSchedule).where(
            UnitAreaSchedule.id == schedule_id,
            UnitAreaSchedule.unit_id == unit_id,
            UnitAreaSchedule.project_id == project_id,
        )
    ).first()
    if schedule is None:
        raise NotFoundError("Area schedule not found.")
    return schedule


def approved_schedule(session: Session, *, unit_id: uuid.UUID) -> UnitAreaSchedule | None:
    return session.scalars(
        select(UnitAreaSchedule).where(
            UnitAreaSchedule.unit_id == unit_id,
            UnitAreaSchedule.status == AREA_SCHEDULE_APPROVED,
        )
    ).first()


def _write_area_values(
    session: Session,
    *,
    project_id: uuid.UUID,
    schedule: UnitAreaSchedule,
    values: list[dict[str, Any]],
) -> None:
    """Replace a draft schedule's measured lines."""
    existing = {
        value.area_type_id: value
        for value in session.scalars(
            select(UnitAreaValue).where(UnitAreaValue.unit_area_schedule_id == schedule.id)
        )
    }
    seen: set[uuid.UUID] = set()
    for entry in values:
        area_type_id = entry["area_type_id"]
        if area_type_id in seen:
            raise ValidationError("An area type may appear only once on a schedule.")
        seen.add(area_type_id)
        area_type = get_area_type(session, project_id=project_id, area_type_id=area_type_id)
        if not area_type.is_active:
            raise ValidationError(f"Area type {area_type.code} is not active.")
        row = existing.pop(area_type_id, None)
        if row is None:
            session.add(
                UnitAreaValue(
                    project_id=project_id,
                    unit_area_schedule_id=schedule.id,
                    area_type_id=area_type_id,
                    raw_area=entry["raw_area"],
                )
            )
        else:
            row.raw_area = entry["raw_area"]
    for orphan in existing.values():
        session.delete(orphan)


def create_area_schedule(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    revision_code: str,
    values: list[dict[str, Any]],
    **fields: object,
) -> UnitAreaSchedule:
    """Start a new measured revision. Always a draft: approval is a second act."""
    unit = lock_unit(session, project_id=project.id, unit_id=unit.id)
    schedule = UnitAreaSchedule(
        project_id=project.id,
        unit_id=unit.id,
        revision_code=_normalize_code(revision_code, label="A revision code"),
        status=AREA_SCHEDULE_DRAFT,
        measurement_standard=fields.get("measurement_standard"),
        plan_revision=fields.get("plan_revision"),
        source=fields.get("source"),
        measured_date=fields.get("measured_date"),
        reconciled=bool(fields.get("reconciled")),
        notes=fields.get("notes"),
        created_by_user_id=actor_user_id,
    )
    session.add(schedule)
    _flush(session)
    _write_area_values(session, project_id=project.id, schedule=schedule, values=values)
    _flush(session)
    record_event(
        session,
        action="unit_area_schedule.created",
        entity_type=ENTITY_AREA_SCHEDULE,
        entity_id=schedule.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(schedule, _SCHEDULE_FIELDS),
    )
    session.commit()
    session.refresh(schedule)
    return schedule


def update_area_schedule(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    schedule: UnitAreaSchedule,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    values: list[dict[str, Any]] | None = None,
    **changes: object,
) -> UnitAreaSchedule:
    """Edit a draft. An approved or superseded revision is immutable."""
    updates = resolve_updates(changes, fields=_SCHEDULE_UPDATABLE, clearable=_SCHEDULE_CLEARABLE)
    lock_unit(session, project_id=project.id, unit_id=unit.id)
    session.refresh(schedule)
    if schedule.status != AREA_SCHEDULE_DRAFT:
        raise ConflictError(
            "An approved area schedule cannot be edited. Create a new revision instead."
        )

    before = _snapshot(schedule, _SCHEDULE_FIELDS)
    for field, value in updates.items():
        setattr(schedule, field, value)
    if values is not None:
        _write_area_values(session, project_id=project.id, schedule=schedule, values=values)
    _flush(session)
    record_event(
        session,
        action="unit_area_schedule.updated",
        entity_type=ENTITY_AREA_SCHEDULE,
        entity_id=schedule.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(schedule, _SCHEDULE_FIELDS),
    )
    session.commit()
    session.refresh(schedule)
    return schedule


def approve_area_schedule(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    schedule: UnitAreaSchedule,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> UnitAreaSchedule:
    """Make one measured revision the current one.

    The unit is locked first, so two approvals arriving together are decided in
    sequence: the second re-reads the state the first committed and either
    supersedes it correctly or is refused. Without the lock both would read "no
    approved schedule" and both would win.
    """
    unit = lock_unit(session, project_id=project.id, unit_id=unit.id)
    session.refresh(schedule)
    if schedule.unit_id != unit.id or schedule.project_id != project.id:
        raise NotFoundError("Area schedule not found.")
    if schedule.status == AREA_SCHEDULE_APPROVED:
        raise ConflictError("That revision is already approved.")
    if schedule.status == AREA_SCHEDULE_SUPERSEDED:
        raise ConflictError("A superseded revision cannot be approved again.")
    if not schedule.reconciled:
        raise ConflictError(
            "This revision has not been reconciled against the drawing it came from."
        )

    lines = {
        value.area_type_id: value
        for value in session.scalars(
            select(UnitAreaValue).where(UnitAreaValue.unit_area_schedule_id == schedule.id)
        )
    }
    required = [
        area_type
        for area_type in list_area_types(session, project_id=project.id, include_inactive=False)
        if area_type.required_for_release
    ]
    missing = [area_type.code for area_type in required if area_type.id not in lines]
    if missing:
        raise ConflictError(
            "This revision is missing required areas: " + ", ".join(sorted(missing)) + "."
        )

    current = approved_schedule(session, unit_id=unit.id)
    before = _snapshot(schedule, _SCHEDULE_FIELDS)
    if current is not None:
        current.status = AREA_SCHEDULE_SUPERSEDED
        session.flush()
    schedule.status = AREA_SCHEDULE_APPROVED
    schedule.approved_by_user_id = actor_user_id
    schedule.approved_at = func.now()
    _flush(session)
    record_event(
        session,
        action="unit_area_schedule.approved",
        entity_type=ENTITY_AREA_SCHEDULE,
        entity_id=schedule.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(schedule, _SCHEDULE_FIELDS),
    )
    session.commit()
    session.refresh(schedule)
    return schedule


def area_lines(
    session: Session, *, project_id: uuid.UUID, schedule: UnitAreaSchedule | None
) -> list[dict[str, Any]]:
    """The measured lines of a schedule with their weighted contributions.

    The weighted figure is derived here and nowhere else. It is never stored: a
    factor change would leave a stored total describing a rule that no longer
    applies.

    Each line is quantised to the scale areas are measured at. A 20.0000 balcony
    at 0.500000 contributes 10.0000 sqm, not 10.0000000000 — and the lines a
    reader sees add up to the total they see, which an unquantised sum would not
    guarantee.
    """
    if schedule is None:
        return []
    rows = session.execute(
        select(UnitAreaValue, AreaType)
        .join(AreaType, AreaType.id == UnitAreaValue.area_type_id)
        .where(UnitAreaValue.unit_area_schedule_id == schedule.id)
        .order_by(AreaType.sort_order, AreaType.code)
    ).all()
    return [
        {
            "area_type_id": area_type.id,
            "code": area_type.code,
            "label": area_type.label,
            "area_role": area_type.area_role,
            "unit_of_measure": area_type.unit_of_measure,
            "raw_area": value.raw_area,
            "weight_factor": area_type.weight_factor,
            "weighted_area": (value.raw_area * area_type.weight_factor).quantize(
                MEASURE_EXPONENT, rounding=ROUND_HALF_UP
            ),
        }
        for value, area_type in rows
    ]


def weighted_saleable_area(lines: list[dict[str, Any]]) -> Decimal | None:
    """The sum of every line's weighted contribution.

    Exact ``Decimal`` arithmetic throughout, over lines already quantised to the
    measurement scale, so the total equals the column of figures above it. A
    weighted saleable area that has been through a binary float is a number
    nobody can reconcile against the drawing it came from.
    """
    if not lines:
        return None
    total = Decimal("0")
    for line in lines:
        total += line["weighted_area"]
    return total


# --------------------------------------------------------------------------- #
# Completeness and release
# --------------------------------------------------------------------------- #


def completeness_checks(
    session: Session, *, unit: Unit, actor: ActorContext | None = None
) -> list[tuple[str, bool]]:
    """Every requirement this unit's inventory record has, and whether it is met.

    One list, so the boolean, the percentage and the outstanding items can never
    disagree — they are three readings of the same thing. Nothing here is
    stored: a completeness percentage written to a column is true on the day it
    is written and quietly wrong afterwards.

    Custom fields marked ``required_for_release`` join the list, which is the one
    transition-specific rule the field system implements. It is a concrete
    requirement rather than a dependency expression language, deliberately: a
    general one would be a rules engine.
    """
    from app.modules.inventory.custom_fields import missing_required_custom_fields

    floor = session.get(Floor, unit.floor_id)
    building = session.get(Building, floor.building_id) if floor is not None else None
    phase = session.get(Phase, building.phase_id) if building is not None else None
    hierarchy_live = bool(
        floor is not None
        and floor.is_active
        and building is not None
        and building.is_active
        and phase is not None
        and phase.is_active
    )

    checks: list[tuple[str, bool]] = [
        ("Hierarchy is active", hierarchy_live),
        ("Unit reference", bool(unit.unit_reference)),
        ("Unit type", unit.unit_type_code is not None),
        (
            "Bedrooms",
            unit.bedrooms is not None or unit.asset_class == "commercial",
        ),
    ]

    schedule = approved_schedule(session, unit_id=unit.id)
    checks.append(("Approved area schedule", schedule is not None))
    recorded: set[uuid.UUID] = set()
    if schedule is not None:
        recorded = {
            value.area_type_id
            for value in session.scalars(
                select(UnitAreaValue).where(UnitAreaValue.unit_area_schedule_id == schedule.id)
            )
        }
    for area_type in list_area_types(session, project_id=unit.project_id, include_inactive=False):
        if area_type.required_for_release:
            checks.append((f"Area: {area_type.label}", area_type.id in recorded))

    checks.extend(missing_required_custom_fields(session, unit=unit, actor=actor))
    return checks


def completeness(
    session: Session, *, unit: Unit, actor: ActorContext | None = None
) -> tuple[bool, int, list[str]]:
    """Whether the record is complete, how nearly, and what is outstanding."""
    checks = completeness_checks(session, unit=unit, actor=actor)
    missing = [label for label, satisfied in checks if not satisfied]
    percent = round((len(checks) - len(missing)) * 100 / len(checks)) if checks else 100
    return (not missing), percent, missing


def release_blockers(
    session: Session,
    *,
    unit: Unit,
    today: date | None = None,
    actor: ActorContext | None = None,
) -> list[str]:
    """Everything standing between this unit and being offered for sale.

    Before PR-MVP-04 exists, ``pricing_approved`` is false on every unit and this
    list always contains "Pricing not approved". That is correct, not a gap: a
    development should not offer a unit it has no approved price for, and there
    is deliberately no override.
    """
    effective = today or date.today()
    blockers: list[str] = []
    if not unit.is_active:
        blockers.append("Unit is not active")
    _, _, missing = completeness(session, unit=unit, actor=actor)
    if missing:
        blockers.append("Inventory record incomplete: " + ", ".join(missing))
    if not unit.drawings_approved:
        blockers.append("Drawings not approved")
    if not unit.legal_sale_eligible:
        blockers.append("Legal sale eligibility not confirmed")
    if not unit.pricing_approved:
        blockers.append("Pricing not approved")
    if unit.release_date is None:
        blockers.append("Release date not set")
    elif unit.release_date > effective:
        blockers.append(f"Release date {unit.release_date.isoformat()} not reached")
    if unit.block_reason:
        blockers.append(f"Commercial block: {unit.block_reason}")
    return blockers


# --------------------------------------------------------------------------- #
# Sub-assets
# --------------------------------------------------------------------------- #

_SUB_ASSET_UPDATABLE = (
    "asset_reference",
    "subtype_code",
    "floor_id",
    "linked_unit_id",
    "area",
    "transfer_mode",
    "notes",
    "is_active",
)
_SUB_ASSET_CLEARABLE = frozenset({"subtype_code", "floor_id", "linked_unit_id", "area", "notes"})


def sub_asset_counts(session: Session, *, unit_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """Parking and storage counts, derived from the linked rows themselves."""
    if not unit_ids:
        return {}
    rows = session.execute(
        select(
            InventorySubAsset.linked_unit_id,
            InventorySubAsset.asset_type,
            func.count(InventorySubAsset.id),
        )
        .where(
            InventorySubAsset.linked_unit_id.in_(unit_ids),
            InventorySubAsset.is_active.is_(True),
        )
        .group_by(InventorySubAsset.linked_unit_id, InventorySubAsset.asset_type)
    ).all()
    counts: dict[uuid.UUID, dict] = {}
    for unit_id, asset_type, count in rows:
        counts.setdefault(unit_id, {})[asset_type] = count
    return counts


def list_sub_assets(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    asset_type: str | None = None,
    unit_id: uuid.UUID | None = None,
    floor_id: uuid.UUID | None = None,
    linked: bool | None = None,
    is_active: bool | None = None,
) -> list[InventorySubAsset]:
    statement = select(InventorySubAsset).where(InventorySubAsset.project_id == project.id)
    if asset_type is not None:
        statement = statement.where(InventorySubAsset.asset_type == asset_type)
    if unit_id is not None:
        statement = statement.where(InventorySubAsset.linked_unit_id == unit_id)
    if floor_id is not None:
        statement = statement.where(InventorySubAsset.floor_id == floor_id)
    if linked is True:
        statement = statement.where(InventorySubAsset.linked_unit_id.is_not(None))
    if linked is False:
        statement = statement.where(InventorySubAsset.linked_unit_id.is_(None))
    if is_active is not None:
        statement = statement.where(InventorySubAsset.is_active.is_(is_active))

    statement = visible_sub_assets(statement, session, project_id=project.id, actor=actor)
    return list(session.scalars(statement.order_by(InventorySubAsset.asset_reference)))


def get_sub_asset(
    session: Session, *, project: Project, actor: ActorContext, asset_id: uuid.UUID
) -> InventorySubAsset:
    statement = visible_sub_assets(
        select(InventorySubAsset).where(
            InventorySubAsset.id == asset_id,
            InventorySubAsset.project_id == project.id,
        ),
        session,
        project_id=project.id,
        actor=actor,
    )
    asset = session.scalars(statement).first()
    if asset is None:
        raise NotFoundError("Sub-asset not found.")
    return asset


def _validate_sub_asset_links(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    values: dict[str, Any],
) -> None:
    floor_id = values.get("floor_id")
    unit_id = values.get("linked_unit_id")
    if floor_id is not None:
        from app.modules.inventory.permissions import require_floor

        # Not merely "a floor of this project": a floor of a phase this caller
        # may see. Otherwise a restricted caller parks an asset in a phase they
        # cannot open, and reads its reference back through the asset.
        require_floor(session, project=project, floor_id=floor_id, actor=actor)
    if unit_id is not None:
        from app.modules.inventory.permissions import require_unit

        unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
        if floor_id is not None and floor_id != unit.floor_id:
            raise ValidationError(
                "A sub-asset attached to a unit sits on that unit's floor, or on none."
            )
    subtype = values.get("subtype_code")
    if subtype is not None:
        require_active_reference_value(
            session,
            category=CATEGORY_SUB_ASSET_SUBTYPE,
            code=subtype,
            country_pack_id=project.country_pack_id,
        )


def create_sub_asset(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    asset_reference: str,
    asset_type: str,
    **fields: object,
) -> InventorySubAsset:
    project = lock_project(session, project.id)
    _validate_sub_asset_links(session, project=project, actor=actor, values=fields)
    asset = InventorySubAsset(
        project_id=project.id,
        asset_reference=_normalize_reference(asset_reference),
        asset_type=asset_type,
        subtype_code=fields.get("subtype_code"),
        floor_id=fields.get("floor_id"),
        linked_unit_id=fields.get("linked_unit_id"),
        area=fields.get("area"),
        transfer_mode=fields.get("transfer_mode") or "attached",
        notes=fields.get("notes"),
        created_by_user_id=actor.user_id,
    )
    session.add(asset)
    _flush(session)
    record_event(
        session,
        action="sub_asset.created",
        entity_type=ENTITY_SUB_ASSET,
        entity_id=asset.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(asset, _SUB_ASSET_FIELDS),
    )
    session.commit()
    session.refresh(asset)
    return asset


def update_sub_asset(
    session: Session,
    *,
    project: Project,
    asset: InventorySubAsset,
    actor: ActorContext,
    **changes: object,
) -> InventorySubAsset:
    updates = resolve_updates(changes, fields=_SUB_ASSET_UPDATABLE, clearable=_SUB_ASSET_CLEARABLE)
    project = lock_project(session, project.id)
    resulting = {
        "floor_id": updates.get("floor_id", asset.floor_id),
        "linked_unit_id": updates.get("linked_unit_id", asset.linked_unit_id),
        "subtype_code": updates.get("subtype_code") if "subtype_code" in updates else None,
    }
    _validate_sub_asset_links(session, project=project, actor=actor, values=resulting)
    if "asset_reference" in updates and updates["asset_reference"] is not None:
        updates["asset_reference"] = _normalize_reference(str(updates["asset_reference"]))

    before = _snapshot(asset, _SUB_ASSET_FIELDS)
    for field, value in updates.items():
        setattr(asset, field, value)
    _flush(session)
    record_event(
        session,
        action="sub_asset.updated",
        entity_type=ENTITY_SUB_ASSET,
        entity_id=asset.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(asset, _SUB_ASSET_FIELDS),
    )
    session.commit()
    session.refresh(asset)
    return asset


# --------------------------------------------------------------------------- #
# Unit register
# --------------------------------------------------------------------------- #


def _unit_filters(
    *,
    project_id: uuid.UUID,
    phase_id: uuid.UUID | None,
    building_id: uuid.UUID | None,
    floor_id: uuid.UUID | None,
    commercial_status: str | None,
    unit_type_code: str | None,
    asset_class: str | None,
    search: str | None,
    is_active: bool | None,
) -> list[ColumnElement[bool]]:
    """The WHERE clauses the page query and the counts share.

    Built once so the totals can never describe a different population from the
    rows they are reported alongside.
    """
    clauses: list[ColumnElement[bool]] = [Unit.project_id == project_id]
    if commercial_status is not None:
        clauses.append(Unit.commercial_status == commercial_status)
    if unit_type_code is not None:
        clauses.append(Unit.unit_type_code == unit_type_code)
    if asset_class is not None:
        clauses.append(Unit.asset_class == asset_class)
    if is_active is not None:
        clauses.append(Unit.is_active.is_(is_active))
    if floor_id is not None:
        clauses.append(Unit.floor_id == floor_id)
    if building_id is not None:
        clauses.append(Unit.floor_id.in_(select(Floor.id).where(Floor.building_id == building_id)))
    if phase_id is not None:
        clauses.append(
            Unit.floor_id.in_(
                select(Floor.id)
                .join(Building, Building.id == Floor.building_id)
                .where(Building.phase_id == phase_id)
            )
        )
    if search:
        pattern = f"%{search.strip()}%"
        clauses.append(Unit.unit_reference.ilike(pattern) | Unit.unit_number.ilike(pattern))
    return clauses


def list_units(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    limit: int,
    offset: int,
    **filters: object,
) -> list[Unit]:
    clauses = _unit_filters(project_id=project.id, **filters)
    statement = visible_units(
        select(Unit).where(*clauses), session, project_id=project.id, actor=actor
    )
    return list(
        session.scalars(
            statement.order_by(Unit.sequence, Unit.unit_reference).limit(limit).offset(offset)
        )
    )


def unit_register_totals(
    session: Session, *, project: Project, actor: ActorContext, **filters: object
) -> dict[str, int]:
    """Counts over the whole matching set, not over the page being returned.

    A register that reports the size of one page under the name ``total`` tells
    a manager there are fifty units when there are two hundred and fifty.
    """
    clauses = _unit_filters(project_id=project.id, **filters)
    statement = visible_units(
        select(
            func.count(Unit.id),
            func.count(Unit.id).filter(Unit.commercial_status == COMMERCIAL_STATUS_AVAILABLE),
            func.count(Unit.id).filter(Unit.commercial_status == COMMERCIAL_STATUS_HELD),
            func.count(Unit.id).filter(Unit.commercial_status == COMMERCIAL_STATUS_UNRELEASED),
        ).where(*clauses),
        session,
        project_id=project.id,
        actor=actor,
    )
    row = session.execute(statement).one()
    return {
        "total": row[0],
        "available_count": row[1],
        "held_count": row[2],
        "unreleased_count": row[3],
    }


def hierarchy_labels(
    session: Session, *, unit_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, Any]]:
    """Phase, building and floor identity for a page of units, in one query."""
    if not unit_ids:
        return {}
    rows = session.execute(
        select(
            Unit.id,
            Floor.id,
            Floor.code,
            Building.id,
            Building.code,
            Phase.id,
            Phase.code,
        )
        .join(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .join(Phase, Phase.id == Building.phase_id)
        .where(Unit.id.in_(unit_ids))
    ).all()
    return {
        row[0]: {
            "floor_id": row[1],
            "floor_code": row[2],
            "building_id": row[3],
            "building_code": row[4],
            "phase_id": row[5],
            "phase_code": row[6],
        }
        for row in rows
    }


# --------------------------------------------------------------------------- #
# Phase access administration
# --------------------------------------------------------------------------- #


def _membership(
    session: Session, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> UserProjectAccess:
    membership = session.scalars(
        select(UserProjectAccess).where(
            UserProjectAccess.project_id == project_id,
            UserProjectAccess.user_id == user_id,
        )
    ).first()
    if membership is None:
        raise NotFoundError("That user has no access record for this project.")
    return membership


def set_phase_scope(
    session: Session,
    *,
    project: Project,
    user_id: uuid.UUID,
    phase_scope: str,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> UserProjectAccess:
    """Widen or narrow how much of a project's inventory a member sees.

    The project row is locked first because the invariant spans two rows: the
    assigned project manager must always see every phase, and a concurrent
    manager assignment must not be able to slip past a narrowing decided against
    a stale read of who the manager is.
    """
    project = lock_project(session, project.id)
    membership = _membership(session, project_id=project.id, user_id=user_id)
    if phase_scope == PHASE_SCOPE_SELECTED and project.project_manager_user_id == user_id:
        raise ConflictError(
            "The assigned project manager sees every phase. Reassign the project "
            "manager before narrowing their scope."
        )

    before = {"phase_scope": membership.phase_scope}
    membership.phase_scope = phase_scope
    _flush(session)
    record_event(
        session,
        action="project_access.phase_scope_changed",
        entity_type=ENTITY_PHASE_ACCESS,
        entity_id=membership.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after={"phase_scope": membership.phase_scope},
    )
    session.commit()
    session.refresh(membership)
    return membership


def list_phase_access(
    session: Session, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[tuple[UserPhaseAccess, Phase]]:
    rows = session.execute(
        select(UserPhaseAccess, Phase)
        .join(Phase, Phase.id == UserPhaseAccess.phase_id)
        .where(UserPhaseAccess.project_id == project_id, UserPhaseAccess.user_id == user_id)
        .order_by(Phase.sequence, Phase.code)
    ).all()
    return [(row[0], row[1]) for row in rows]


def set_phase_access(
    session: Session,
    *,
    project: Project,
    phase: Phase,
    user_id: uuid.UUID,
    is_active: bool,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> UserPhaseAccess:
    """Grant or revoke one phase for one member.

    Re-granting reactivates the existing row rather than adding a second, so the
    grant and revoke history of a pairing stays on a single line.
    """
    project = lock_project(session, project.id)
    _membership(session, project_id=project.id, user_id=user_id)

    access = session.scalars(
        select(UserPhaseAccess).where(
            UserPhaseAccess.user_id == user_id, UserPhaseAccess.phase_id == phase.id
        )
    ).first()
    if access is None:
        if not is_active:
            raise NotFoundError("That user has no access record for this phase.")
        access = UserPhaseAccess(
            project_id=project.id,
            user_id=user_id,
            phase_id=phase.id,
            is_active=True,
            granted_by_user_id=actor_user_id,
        )
        session.add(access)
        before = None
    else:
        before = {"is_active": access.is_active}
        access.is_active = is_active
        if is_active:
            access.granted_at = func.now()
            access.granted_by_user_id = actor_user_id
            access.revoked_at = None
            access.revoked_by_user_id = None
        else:
            access.revoked_at = func.now()
            access.revoked_by_user_id = actor_user_id
    _flush(session)
    record_event(
        session,
        action="phase_access.granted" if is_active else "phase_access.revoked",
        entity_type=ENTITY_PHASE_ACCESS,
        entity_id=access.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after={"is_active": access.is_active, "phase_id": str(phase.id), "user_id": str(user_id)},
    )
    session.commit()
    session.refresh(access)
    return access


def ensure_manager_sees_every_phase(
    session: Session, *, project: Project, user_id: uuid.UUID
) -> None:
    """Widen a newly assigned project manager's scope if it was narrowed.

    Called by the access administration route after a manager assignment. A
    project manager who can only see half the inventory is not managing the
    project.
    """
    membership = session.scalars(
        select(UserProjectAccess).where(
            UserProjectAccess.project_id == project.id,
            UserProjectAccess.user_id == user_id,
        )
    ).first()
    if membership is not None and membership.phase_scope != PHASE_SCOPE_ALL:
        membership.phase_scope = PHASE_SCOPE_ALL
