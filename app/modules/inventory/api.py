"""Inventory routes: hierarchy, units, areas, sub-assets, fields and import.

Handlers validate, authorise and orchestrate. Every rule about what an inventory
record may be lives in the service; every rule about who may reach it lives in
``permissions.py``. A route that decided either for itself would be the one route
that later disagrees with the rest.

Nesting stops at the resource. Filters narrow a list rather than growing the
path: ``/units?phase_id=`` and not ``/phases/{id}/buildings/{id}/floors/{id}/units``.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import select

from app.core.errors import ValidationError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession, SystemAdmin
from app.modules.inventory import custom_fields as fields_service
from app.modules.inventory import import_service, service
from app.modules.inventory.models import (
    CustomFieldDefinition,
    Phase,
    Unit,
    UnitAreaSchedule,
)
from app.modules.inventory.permissions import (
    InventoryProject,
    require_commercial_transition_writer,
    require_inventory_release_writer,
    require_inventory_structure_writer,
    require_phase,
    require_project_configurer,
    require_unit,
)
from app.modules.inventory.schemas import (
    AreaScheduleCreateRequest,
    AreaScheduleRead,
    AreaScheduleUpdateRequest,
    AreaTypeCreateRequest,
    AreaTypeRead,
    AreaTypeUpdateRequest,
    BuildingCreateRequest,
    BuildingRead,
    BuildingUpdateRequest,
    CommercialTransitionRequest,
    CustomFieldCreateRequest,
    CustomFieldRead,
    CustomFieldUpdateRequest,
    CustomValueRead,
    CustomValuesRequest,
    FloorCreateRequest,
    FloorRead,
    FloorUpdateRequest,
    ImportReport,
    PhaseAccessRead,
    PhaseAccessRequest,
    PhaseCreateRequest,
    PhaseRead,
    PhaseScopeRequest,
    PhaseUpdateRequest,
    ReleaseControlsRequest,
    SubAssetCreateRequest,
    SubAssetRead,
    SubAssetUpdateRequest,
    UnitCreateRequest,
    UnitDetail,
    UnitRegister,
    UnitStatusEventRead,
    UnitSummary,
    UnitUpdateRequest,
)
from app.modules.projects.models import LandParcel, Project
from app.modules.projects.permissions import AccessibleProject, require_project_writer

router = APIRouter(prefix="/projects", tags=["inventory"])

#: A page of a unit register. Large enough for a floor, bounded so one request
#: cannot ask for a whole development.
_MAX_PAGE = 200


# --------------------------------------------------------------------------- #
# Phases
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/inventory/phases",
    response_model=list[PhaseRead],
    summary="List the phases of a project",
)
def list_phases(
    session: DbSession, actor: ActiveActor, project: InventoryProject
) -> list[PhaseRead]:
    phases = service.list_phases(session, project=project, actor=actor)
    return [PhaseRead.model_validate(phase) for phase in phases]


@router.post(
    "/{project_id}/inventory/phases",
    response_model=PhaseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a phase",
)
def create_phase(
    payload: PhaseCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> PhaseRead:
    require_project_configurer(actor)
    phase = service.create_phase(
        session,
        project=project,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return PhaseRead.model_validate(phase)


@router.get(
    "/{project_id}/inventory/phases/{phase_id}",
    response_model=PhaseRead,
    summary="Read a phase",
)
def read_phase(
    phase_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> PhaseRead:
    return PhaseRead.model_validate(
        require_phase(session, project=project, phase_id=phase_id, actor=actor)
    )


@router.patch(
    "/{project_id}/inventory/phases/{phase_id}",
    response_model=PhaseRead,
    summary="Update a phase",
)
def update_phase(
    phase_id: uuid.UUID,
    payload: PhaseUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> PhaseRead:
    require_project_configurer(actor)
    phase = require_phase(session, project=project, phase_id=phase_id, actor=actor)
    updated = service.update_phase(
        session,
        phase=phase,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return PhaseRead.model_validate(updated)


# --------------------------------------------------------------------------- #
# Buildings and floors
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/inventory/buildings",
    response_model=list[BuildingRead],
    summary="List buildings",
)
def list_buildings(
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[BuildingRead]:
    buildings = service.list_buildings(session, project=project, actor=actor, phase_id=phase_id)
    return [BuildingRead.model_validate(building) for building in buildings]


@router.post(
    "/{project_id}/inventory/buildings",
    response_model=BuildingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a building",
)
def create_building(
    payload: BuildingCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> BuildingRead:
    require_inventory_structure_writer(actor)
    phase = require_phase(session, project=project, phase_id=payload.phase_id, actor=actor)
    values = payload.model_dump(exclude_unset=True)
    values.pop("phase_id")
    building = service.create_building(
        session,
        project=project,
        phase=phase,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **values,
    )
    return BuildingRead.model_validate(building)


@router.patch(
    "/{project_id}/inventory/buildings/{building_id}",
    response_model=BuildingRead,
    summary="Update a building",
)
def update_building(
    building_id: uuid.UUID,
    payload: BuildingUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> BuildingRead:
    require_inventory_structure_writer(actor)
    building = service.get_building(session, project_id=project.id, building_id=building_id)
    require_phase(session, project=project, phase_id=building.phase_id, actor=actor)
    updated = service.update_building(
        session,
        building=building,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return BuildingRead.model_validate(updated)


@router.get("/{project_id}/inventory/floors", response_model=list[FloorRead], summary="List floors")
def list_floors(
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
    building_id: Annotated[uuid.UUID | None, Query()] = None,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[FloorRead]:
    floors = service.list_floors(
        session, project=project, actor=actor, building_id=building_id, phase_id=phase_id
    )
    return [FloorRead.model_validate(floor) for floor in floors]


@router.post(
    "/{project_id}/inventory/floors",
    response_model=FloorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a floor",
)
def create_floor(
    payload: FloorCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> FloorRead:
    require_inventory_structure_writer(actor)
    building = service.get_building(session, project_id=project.id, building_id=payload.building_id)
    require_phase(session, project=project, phase_id=building.phase_id, actor=actor)
    values = payload.model_dump(exclude_unset=True)
    values.pop("building_id")
    floor = service.create_floor(
        session,
        project=project,
        building=building,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **values,
    )
    return FloorRead.model_validate(floor)


@router.patch(
    "/{project_id}/inventory/floors/{floor_id}",
    response_model=FloorRead,
    summary="Update a floor",
)
def update_floor(
    floor_id: uuid.UUID,
    payload: FloorUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> FloorRead:
    require_inventory_structure_writer(actor)
    floor = service.get_floor(session, project_id=project.id, floor_id=floor_id)
    phase = service.phase_of_floor(session, floor)
    require_phase(session, project=project, phase_id=phase.id, actor=actor)
    updated = service.update_floor(
        session,
        floor=floor,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return FloorRead.model_validate(updated)


# --------------------------------------------------------------------------- #
# Units
# --------------------------------------------------------------------------- #


def _unit_summary(
    session: DbSession,
    project: Project,
    unit: Unit,
    labels: dict[uuid.UUID, dict[str, Any]],
    counts: dict[uuid.UUID, dict],
    actor: ActorContext,
) -> dict[str, Any]:
    """The derived view of one unit, assembled from the rows that hold the facts."""
    schedule = service.approved_schedule(session, unit_id=unit.id)
    lines = service.area_lines(session, project_id=project.id, schedule=schedule)
    internal = service.internal_area_type(session, project_id=project.id)
    internal_area = next(
        (line["raw_area"] for line in lines if internal and line["area_type_id"] == internal.id),
        None,
    )
    complete, percent, missing = service.completeness(session, unit=unit, actor=actor)
    blockers = service.release_blockers(session, unit=unit, actor=actor)
    return {
        # UnitDetail's fields, not UnitSummary's: the register renders the
        # narrower model from the same dictionary, and a read model that ignores
        # what it does not declare costs nothing to over-supply.
        **{name: getattr(unit, name) for name in UnitDetail.model_fields if hasattr(unit, name)},
        **labels.get(unit.id, {}),
        "internal_area": internal_area,
        "weighted_saleable_area": service.weighted_saleable_area(lines),
        "parking_count": counts.get(unit.id, {}).get("parking", 0),
        "storage_count": counts.get(unit.id, {}).get("storage", 0),
        "is_complete": complete,
        "completeness_percent": percent,
        "release_eligible": not blockers,
        "release_blockers": blockers,
        "missing_requirements": missing,
        "area_lines": lines,
        "area_schedule_id": schedule.id if schedule else None,
        "area_revision_code": schedule.revision_code if schedule else None,
    }


@router.get(
    "/{project_id}/inventory/units",
    response_model=UnitRegister,
    summary="The unit register",
)
def list_units(
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
    building_id: Annotated[uuid.UUID | None, Query()] = None,
    floor_id: Annotated[uuid.UUID | None, Query()] = None,
    commercial_status: Annotated[str | None, Query(max_length=32)] = None,
    unit_type_code: Annotated[str | None, Query(max_length=64)] = None,
    asset_class: Annotated[str | None, Query(max_length=32)] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    is_active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UnitRegister:
    filters = {
        "phase_id": phase_id,
        "building_id": building_id,
        "floor_id": floor_id,
        "commercial_status": commercial_status,
        "unit_type_code": unit_type_code,
        "asset_class": asset_class,
        "search": search,
        "is_active": is_active,
    }
    units = service.list_units(
        session, project=project, actor=actor, limit=limit, offset=offset, **filters
    )
    totals = service.unit_register_totals(session, project=project, actor=actor, **filters)
    unit_ids = [unit.id for unit in units]
    labels = service.hierarchy_labels(session, unit_ids=unit_ids)
    counts = service.sub_asset_counts(session, unit_ids=unit_ids)
    rows = [
        UnitSummary.model_validate(_unit_summary(session, project, unit, labels, counts, actor))
        for unit in units
    ]
    # The counts describe every unit matching the filter; `units` is the page.
    eligible = sum(1 for row in rows if row.release_eligible)
    return UnitRegister(units=rows, release_eligible_count=eligible, **totals)


@router.post(
    "/{project_id}/inventory/units",
    response_model=UnitDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a unit",
)
def create_unit(
    payload: UnitCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> UnitDetail:
    require_inventory_structure_writer(actor)
    floor = service.get_floor(session, project_id=project.id, floor_id=payload.floor_id)
    phase = service.phase_of_floor(session, floor)
    require_phase(session, project=project, phase_id=phase.id, actor=actor)
    values = payload.model_dump(exclude_unset=True)
    values.pop("floor_id")
    unit = service.create_unit(
        session,
        project=project,
        floor=floor,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **values,
    )
    return _unit_detail(session, project, unit, actor)


def _unit_detail(
    session: DbSession, project: Project, unit: Unit, actor: ActorContext
) -> UnitDetail:
    labels = service.hierarchy_labels(session, unit_ids=[unit.id])
    counts = service.sub_asset_counts(session, unit_ids=[unit.id])
    return UnitDetail.model_validate(_unit_summary(session, project, unit, labels, counts, actor))


@router.get(
    "/{project_id}/inventory/units/{unit_id}",
    response_model=UnitDetail,
    summary="Read a unit",
)
def read_unit(
    unit_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> UnitDetail:
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    return _unit_detail(session, project, unit, actor)


@router.patch(
    "/{project_id}/inventory/units/{unit_id}",
    response_model=UnitDetail,
    summary="Update a unit's physical facts",
)
def update_unit(
    unit_id: uuid.UUID,
    payload: UnitUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> UnitDetail:
    require_inventory_structure_writer(actor)
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    updated = service.update_unit(
        session,
        project=project,
        unit=unit,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _unit_detail(session, project, updated, actor)


@router.patch(
    "/{project_id}/inventory/units/{unit_id}/release-controls",
    response_model=UnitDetail,
    summary="Set the gates that decide whether a unit may be released",
)
def update_release_controls(
    unit_id: uuid.UUID,
    payload: ReleaseControlsRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> UnitDetail:
    changes = payload.model_dump(exclude_unset=True)
    # Each field has a different owning role, so the check is per field: a caller
    # may legitimately be allowed one of a request and refused another.
    require_inventory_release_writer(actor, list(changes))
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    updated = service.update_release_controls(
        session,
        project=project,
        unit=unit,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **changes,
    )
    return _unit_detail(session, project, updated, actor)


@router.post(
    "/{project_id}/inventory/units/{unit_id}/commercial-transitions",
    response_model=UnitDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Move a unit between the commercial states inventory owns",
)
def transition_unit(
    unit_id: uuid.UUID,
    payload: CommercialTransitionRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> UnitDetail:
    require_commercial_transition_writer(actor)
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    updated = service.transition_commercial_status(
        session,
        project=project,
        unit=unit,
        to_status=payload.to_status,
        effective_date=payload.effective_date,
        reason=payload.reason,
        notes=payload.notes,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        actor=actor,
    )
    return _unit_detail(session, project, updated, actor)


@router.get(
    "/{project_id}/inventory/units/{unit_id}/status-history",
    response_model=list[UnitStatusEventRead],
    summary="The recorded status history of a unit",
)
def unit_status_history(
    unit_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
    dimension: Annotated[str | None, Query(max_length=16)] = None,
) -> list[UnitStatusEventRead]:
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    events = service.list_status_events(session, unit_id=unit.id, dimension=dimension)
    return [UnitStatusEventRead.model_validate(event) for event in events]


# --------------------------------------------------------------------------- #
# Area types and schedules
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/inventory/area-types",
    response_model=list[AreaTypeRead],
    summary="The area types a project measures by",
)
def list_area_types(
    session: DbSession, actor: ActiveActor, project: InventoryProject
) -> list[AreaTypeRead]:
    return [
        AreaTypeRead.model_validate(area_type)
        for area_type in service.list_area_types(session, project_id=project.id)
    ]


@router.post(
    "/{project_id}/inventory/area-types",
    response_model=AreaTypeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Configure an area type",
)
def create_area_type(
    payload: AreaTypeCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> AreaTypeRead:
    require_project_configurer(actor)
    area_type = service.create_area_type(
        session,
        project=project,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return AreaTypeRead.model_validate(area_type)


@router.patch(
    "/{project_id}/inventory/area-types/{area_type_id}",
    response_model=AreaTypeRead,
    summary="Update an area type",
)
def update_area_type(
    area_type_id: uuid.UUID,
    payload: AreaTypeUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> AreaTypeRead:
    require_project_configurer(actor)
    area_type = service.get_area_type(session, project_id=project.id, area_type_id=area_type_id)
    updated = service.update_area_type(
        session,
        project=project,
        area_type=area_type,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return AreaTypeRead.model_validate(updated)


def _schedule_read(
    session: DbSession, project: Project, schedule: UnitAreaSchedule
) -> AreaScheduleRead:
    lines = service.area_lines(session, project_id=project.id, schedule=schedule)
    return AreaScheduleRead.model_validate(
        {
            **{
                field: getattr(schedule, field)
                for field in AreaScheduleRead.model_fields
                if hasattr(schedule, field)
            },
            "lines": lines,
            "weighted_saleable_area": service.weighted_saleable_area(lines),
        }
    )


@router.get(
    "/{project_id}/inventory/units/{unit_id}/area-schedules",
    response_model=list[AreaScheduleRead],
    summary="Every measured revision of a unit's areas",
)
def list_area_schedules(
    unit_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> list[AreaScheduleRead]:
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    return [
        _schedule_read(session, project, schedule)
        for schedule in service.list_area_schedules(session, unit_id=unit.id)
    ]


@router.post(
    "/{project_id}/inventory/units/{unit_id}/area-schedules",
    response_model=AreaScheduleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new measured revision",
)
def create_area_schedule(
    unit_id: uuid.UUID,
    payload: AreaScheduleCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> AreaScheduleRead:
    require_inventory_structure_writer(actor)
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    values = payload.model_dump(exclude_unset=True)
    lines = values.pop("values", [])
    schedule = service.create_area_schedule(
        session,
        project=project,
        unit=unit,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        values=lines,
        **values,
    )
    return _schedule_read(session, project, schedule)


@router.patch(
    "/{project_id}/inventory/units/{unit_id}/area-schedules/{schedule_id}",
    response_model=AreaScheduleRead,
    summary="Edit a draft revision",
)
def update_area_schedule(
    unit_id: uuid.UUID,
    schedule_id: uuid.UUID,
    payload: AreaScheduleUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> AreaScheduleRead:
    require_inventory_structure_writer(actor)
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    schedule = service.get_area_schedule(
        session, project_id=project.id, unit_id=unit.id, schedule_id=schedule_id
    )
    values = payload.model_dump(exclude_unset=True)
    lines = values.pop("values", None)
    updated = service.update_area_schedule(
        session,
        project=project,
        unit=unit,
        schedule=schedule,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        values=lines,
        **values,
    )
    return _schedule_read(session, project, updated)


@router.post(
    "/{project_id}/inventory/units/{unit_id}/area-schedules/{schedule_id}/approve",
    response_model=AreaScheduleRead,
    summary="Make a measured revision the current one",
)
def approve_area_schedule(
    unit_id: uuid.UUID,
    schedule_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> AreaScheduleRead:
    require_project_configurer(actor)
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    schedule = service.get_area_schedule(
        session, project_id=project.id, unit_id=unit.id, schedule_id=schedule_id
    )
    approved = service.approve_area_schedule(
        session,
        project=project,
        unit=unit,
        schedule=schedule,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
    )
    return _schedule_read(session, project, approved)


# --------------------------------------------------------------------------- #
# Sub-assets
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/inventory/sub-assets",
    response_model=list[SubAssetRead],
    summary="Parking, storage and other separately identifiable assets",
)
def list_sub_assets(
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
    asset_type: Annotated[str | None, Query(max_length=32)] = None,
    unit_id: Annotated[uuid.UUID | None, Query()] = None,
    floor_id: Annotated[uuid.UUID | None, Query()] = None,
    linked: Annotated[bool | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[SubAssetRead]:
    assets = service.list_sub_assets(
        session,
        project=project,
        actor=actor,
        asset_type=asset_type,
        unit_id=unit_id,
        floor_id=floor_id,
        linked=linked,
        is_active=is_active,
    )
    return [SubAssetRead.model_validate(asset) for asset in assets]


@router.post(
    "/{project_id}/inventory/sub-assets",
    response_model=SubAssetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a sub-asset",
)
def create_sub_asset(
    payload: SubAssetCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> SubAssetRead:
    require_inventory_structure_writer(actor)
    asset = service.create_sub_asset(
        session, project=project, actor=actor, **payload.model_dump(exclude_unset=True)
    )
    return SubAssetRead.model_validate(asset)


@router.get(
    "/{project_id}/inventory/sub-assets/{asset_id}",
    response_model=SubAssetRead,
    summary="Read a sub-asset",
)
def read_sub_asset(
    asset_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> SubAssetRead:
    return SubAssetRead.model_validate(
        service.get_sub_asset(session, project=project, actor=actor, asset_id=asset_id)
    )


@router.patch(
    "/{project_id}/inventory/sub-assets/{asset_id}",
    response_model=SubAssetRead,
    summary="Update a sub-asset",
)
def update_sub_asset(
    asset_id: uuid.UUID,
    payload: SubAssetUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> SubAssetRead:
    require_inventory_structure_writer(actor)
    asset = service.get_sub_asset(session, project=project, actor=actor, asset_id=asset_id)
    updated = service.update_sub_asset(
        session,
        project=project,
        asset=asset,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return SubAssetRead.model_validate(updated)


# --------------------------------------------------------------------------- #
# Phase access administration
# --------------------------------------------------------------------------- #


@router.patch(
    "/{project_id}/access/{user_id}/phase-scope",
    summary="Set how much of a project's inventory a member sees",
)
def set_phase_scope(
    user_id: uuid.UUID,
    payload: PhaseScopeRequest,
    session: DbSession,
    actor: SystemAdmin,
    project: AccessibleProject,
) -> dict[str, str]:
    membership = service.set_phase_scope(
        session,
        project=project,
        user_id=user_id,
        phase_scope=payload.phase_scope,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
    )
    return {"phase_scope": membership.phase_scope}


@router.get(
    "/{project_id}/access/{user_id}/phases",
    response_model=list[PhaseAccessRead],
    summary="Which phases a member has been granted",
)
def list_phase_access(
    user_id: uuid.UUID,
    session: DbSession,
    actor: SystemAdmin,
    project: AccessibleProject,
) -> list[PhaseAccessRead]:
    rows = service.list_phase_access(session, project_id=project.id, user_id=user_id)
    return [
        PhaseAccessRead.model_validate(
            {
                **{
                    field: getattr(access, field)
                    for field in PhaseAccessRead.model_fields
                    if hasattr(access, field)
                },
                "phase_code": phase.code,
                "phase_name": phase.name,
            }
        )
        for access, phase in rows
    ]


@router.put(
    "/{project_id}/access/{user_id}/phases/{phase_id}",
    response_model=PhaseAccessRead,
    summary="Grant a member one phase",
)
def grant_phase_access(
    user_id: uuid.UUID,
    phase_id: uuid.UUID,
    session: DbSession,
    actor: SystemAdmin,
    project: AccessibleProject,
) -> PhaseAccessRead:
    return _set_phase_access(session, project, actor, user_id, phase_id, True)


@router.patch(
    "/{project_id}/access/{user_id}/phases/{phase_id}",
    response_model=PhaseAccessRead,
    summary="Grant or revoke a member's access to one phase",
)
def change_phase_access(
    user_id: uuid.UUID,
    phase_id: uuid.UUID,
    payload: PhaseAccessRequest,
    session: DbSession,
    actor: SystemAdmin,
    project: AccessibleProject,
) -> PhaseAccessRead:
    return _set_phase_access(session, project, actor, user_id, phase_id, payload.is_active)


def _set_phase_access(
    session: DbSession,
    project: Project,
    actor: ActorContext,
    user_id: uuid.UUID,
    phase_id: uuid.UUID,
    is_active: bool,
) -> PhaseAccessRead:
    phase = session.scalars(
        select(Phase).where(Phase.id == phase_id, Phase.project_id == project.id)
    ).first()
    if phase is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Phase not found.")
    access = service.set_phase_access(
        session,
        project=project,
        phase=phase,
        user_id=user_id,
        is_active=is_active,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
    )
    return PhaseAccessRead.model_validate(
        {
            **{
                field: getattr(access, field)
                for field in PhaseAccessRead.model_fields
                if hasattr(access, field)
            },
            "phase_code": phase.code,
            "phase_name": phase.name,
        }
    )


# --------------------------------------------------------------------------- #
# Configurable field definitions
# --------------------------------------------------------------------------- #


def _definition_read(session: DbSession, definition: CustomFieldDefinition) -> CustomFieldRead:
    return CustomFieldRead.model_validate(
        {
            **{
                field: getattr(definition, field)
                for field in CustomFieldRead.model_fields
                if hasattr(definition, field)
            },
            "options": fields_service.options_of(session, definition.id),
        }
    )


@router.get(
    "/{project_id}/field-definitions",
    response_model=list[CustomFieldRead],
    summary="The configurable fields that apply in this project",
)
def list_field_definitions(
    session: DbSession,
    actor: ActiveActor,
    project: AccessibleProject,
    entity_type: Annotated[str | None, Query(max_length=32)] = None,
) -> list[CustomFieldRead]:
    definitions = fields_service.list_definitions(
        session, entity_type=entity_type, project_id=project.id
    )
    return [
        _definition_read(session, definition)
        for definition in definitions
        if fields_service.can_view(definition, actor)
    ]


@router.post(
    "/{project_id}/field-definitions",
    response_model=CustomFieldRead,
    status_code=status.HTTP_201_CREATED,
    summary="Define a configurable field",
)
def create_field_definition(
    payload: CustomFieldCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: AccessibleProject,
) -> CustomFieldRead:
    values = payload.model_dump(exclude_unset=True)
    _require_definition_authority(
        actor, scope_type=values["scope_type"], project=project, values=values
    )
    options = values.pop("options", [])
    definition = fields_service.create_definition(session, actor=actor, options=options, **values)
    return _definition_read(session, definition)


@router.patch(
    "/{project_id}/field-definitions/{definition_id}",
    response_model=CustomFieldRead,
    summary="Update a configurable field",
)
def update_field_definition(
    definition_id: uuid.UUID,
    payload: CustomFieldUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: AccessibleProject,
) -> CustomFieldRead:
    definition = fields_service.get_definition(session, definition_id)
    _require_definition_authority(
        actor,
        scope_type=definition.scope_type,
        project=project,
        values={"project_id": definition.project_id},
    )
    values = payload.model_dump(exclude_unset=True)
    options = values.pop("options", None)
    change_reason = values.pop("change_reason", None)
    updated = fields_service.update_definition(
        session,
        definition=definition,
        actor=actor,
        options=options,
        change_reason=change_reason,
        **values,
    )
    return _definition_read(session, updated)


def _require_definition_authority(
    actor: ActorContext, *, scope_type: str, project: Project, values: dict[str, Any]
) -> None:
    """Who may define a field at which scope.

    A System Administrator configures the whole system. A Project Manager
    configures their own project — and only their own: a project-scoped role
    that could edit a global definition would be changing every other project's
    records from inside one of them.
    """
    if actor.is_system_admin:
        return
    if "project_manager" not in actor.role_keys:
        from app.core.errors import PermissionDeniedError

        raise PermissionDeniedError("You do not have permission to perform this action.")
    if scope_type not in {"project", "unit_type"} or values.get("project_id") != project.id:
        from app.core.errors import PermissionDeniedError

        raise PermissionDeniedError(
            "A project manager can define fields for their own project only."
        )


# --------------------------------------------------------------------------- #
# Configurable values
# --------------------------------------------------------------------------- #


def _values_read(rows: list[dict[str, Any]]) -> list[CustomValueRead]:
    return [CustomValueRead.model_validate(row) for row in rows]


@router.get(
    "/{project_id}/custom-values",
    response_model=list[CustomValueRead],
    summary="The project's configurable values",
)
def read_project_values(
    session: DbSession, actor: ActiveActor, project: AccessibleProject
) -> list[CustomValueRead]:
    return _values_read(
        fields_service.read_values(session, entity_type="project", entity=project, actor=actor)
    )


@router.put(
    "/{project_id}/custom-values",
    response_model=list[CustomValueRead],
    summary="Write the project's configurable values",
)
def write_project_values(
    payload: CustomValuesRequest,
    session: DbSession,
    actor: ActiveActor,
    project: AccessibleProject,
) -> list[CustomValueRead]:
    require_project_writer(actor)
    fields_service.write_values(
        session,
        entity_type="project",
        entity=project,
        actor=actor,
        values=payload.values,
        change_reason=payload.change_reason,
    )
    session.commit()
    return _values_read(
        fields_service.read_values(session, entity_type="project", entity=project, actor=actor)
    )


@router.get(
    "/{project_id}/parcels/{parcel_id}/custom-values",
    response_model=list[CustomValueRead],
    summary="A parcel's configurable values",
)
def read_parcel_values(
    parcel_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: AccessibleProject,
) -> list[CustomValueRead]:
    parcel = _parcel(session, project, parcel_id)
    return _values_read(
        fields_service.read_values(session, entity_type="land_parcel", entity=parcel, actor=actor)
    )


@router.put(
    "/{project_id}/parcels/{parcel_id}/custom-values",
    response_model=list[CustomValueRead],
    summary="Write a parcel's configurable values",
)
def write_parcel_values(
    parcel_id: uuid.UUID,
    payload: CustomValuesRequest,
    session: DbSession,
    actor: ActiveActor,
    project: AccessibleProject,
) -> list[CustomValueRead]:
    require_project_writer(actor)
    parcel = _parcel(session, project, parcel_id)
    fields_service.write_values(
        session,
        entity_type="land_parcel",
        entity=parcel,
        actor=actor,
        values=payload.values,
        change_reason=payload.change_reason,
    )
    session.commit()
    return _values_read(
        fields_service.read_values(session, entity_type="land_parcel", entity=parcel, actor=actor)
    )


def _parcel(session: DbSession, project: Project, parcel_id: uuid.UUID) -> LandParcel:
    return fields_service.parcel_of(session, project_id=project.id, parcel_id=parcel_id)


@router.get(
    "/{project_id}/inventory/units/{unit_id}/custom-values",
    response_model=list[CustomValueRead],
    summary="A unit's configurable values",
)
def read_unit_values(
    unit_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> list[CustomValueRead]:
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    return _values_read(
        fields_service.read_values(session, entity_type="unit", entity=unit, actor=actor)
    )


@router.put(
    "/{project_id}/inventory/units/{unit_id}/custom-values",
    response_model=list[CustomValueRead],
    summary="Write a unit's configurable values",
)
def write_unit_values(
    unit_id: uuid.UUID,
    payload: CustomValuesRequest,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
) -> list[CustomValueRead]:
    require_inventory_structure_writer(actor)
    unit = require_unit(session, project=project, unit_id=unit_id, actor=actor)
    fields_service.write_values(
        session,
        entity_type="unit",
        entity=unit,
        actor=actor,
        values=payload.values,
        change_reason=payload.change_reason,
    )
    session.commit()
    return _values_read(
        fields_service.read_values(session, entity_type="unit", entity=unit, actor=actor)
    )


# --------------------------------------------------------------------------- #
# Bulk import
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/inventory/import/template",
    summary="A CSV template for the bulk inventory import",
)
def import_template(
    session: DbSession, actor: ActiveActor, project: InventoryProject
) -> dict[str, str]:
    return {"filename": "inventory-import.csv", "content": import_service.template_csv()}


@router.post(
    "/{project_id}/inventory/import/validate",
    response_model=ImportReport,
    summary="Check an inventory CSV without writing anything",
)
async def validate_import(
    request: Request,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
    mode: Annotated[str, Query(max_length=16)] = "create",
    create_missing_hierarchy: Annotated[bool, Query()] = False,
) -> ImportReport:
    require_inventory_structure_writer(actor)
    body = await _csv_body(request)
    return ImportReport.model_validate(
        import_service.validate(
            session,
            project=project,
            actor=actor,
            body=body,
            mode=mode,
            create_missing_hierarchy=create_missing_hierarchy,
        )
    )


@router.post(
    "/{project_id}/inventory/import/apply",
    response_model=ImportReport,
    summary="Apply an inventory CSV as one transaction",
)
async def apply_import(
    request: Request,
    session: DbSession,
    actor: ActiveActor,
    project: InventoryProject,
    mode: Annotated[str, Query(max_length=16)] = "create",
    create_missing_hierarchy: Annotated[bool, Query()] = False,
    approve_area_schedules: Annotated[bool, Query()] = False,
) -> ImportReport:
    require_inventory_structure_writer(actor)
    if approve_area_schedules:
        require_project_configurer(actor)
    body = await _csv_body(request)
    return ImportReport.model_validate(
        import_service.apply(
            session,
            project=project,
            actor=actor,
            body=body,
            mode=mode,
            create_missing_hierarchy=create_missing_hierarchy,
            approve_area_schedules=approve_area_schedules,
        )
    )


async def _csv_body(request: Request) -> bytes:
    """Read the raw CSV request body.

    Raw ``text/csv`` rather than multipart: the browser reads the file itself
    with ``File.text()``, so there is no upload parser to install and no new
    dependency for one screen.
    """
    body = await request.body()
    if len(body) > import_service.MAX_BYTES:
        raise ValidationError(
            f"That file is larger than the {import_service.MAX_BYTES // (1024 * 1024)} MB limit."
        )
    return body
