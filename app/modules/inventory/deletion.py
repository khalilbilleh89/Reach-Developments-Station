"""Administrator deletion of catalogue records, never their business transactions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.models import (
    AreaType,
    Building,
    Floor,
    InventorySubAsset,
    Phase,
    Unit,
    UnitAreaSchedule,
    UnitAreaValue,
    UnitCustomFieldValue,
    UnitDocument,
    UnitFeature,
    UnitStatusEvent,
    UserPhaseAccess,
)
from app.modules.inventory.permissions import require_operational_project
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project


def list_removed_units(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    search: str | None,
    limit: int,
    offset: int,
) -> list[Unit]:
    """Only the owner may discover retained removals, within this project."""
    if not actor.is_master_admin:
        raise PermissionDeniedError("Only Master Administrator may view removed units.")
    statement = select(Unit).where(Unit.project_id == project.id, Unit.removed_at.is_not(None))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            Unit.unit_reference.ilike(pattern) | Unit.unit_number.ilike(pattern)
        )
    return list(
        session.scalars(
            statement.order_by(Unit.unit_reference, Unit.id).limit(limit).offset(offset)
        )
    )


def restore_unit(
    session: Session, *, project: Project, actor: ActorContext, identifier: uuid.UUID, reason: str
) -> Unit:
    """Recover the original identity and current visibility without rewriting history."""
    if not actor.is_master_admin:
        raise PermissionDeniedError("Only Master Administrator may restore a removed unit.")
    if not reason.strip():
        raise ValidationError("Give a reason for restoring this unit.")
    project = lock_project(session, project.id)
    unit = session.scalar(
        select(Unit)
        .where(Unit.id == identifier, Unit.project_id == project.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if unit is None:
        raise NotFoundError("Unit not found.")
    require_operational_project(project)
    if unit.removed_at is None:
        return unit
    active_hierarchy = session.scalar(
        select(Building.id)
        .select_from(Unit)
        .outerjoin(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == func.coalesce(Unit.building_id, Floor.building_id))
        .join(Phase, Phase.id == Building.phase_id)
        .where(
            Unit.id == unit.id,
            Unit.project_id == project.id,
            Building.project_id == project.id,
            Phase.project_id == project.id,
            (Unit.floor_id.is_(None) | Floor.is_active.is_(True)),
            Building.is_active.is_(True),
            Phase.is_active.is_(True),
        )
    )
    if active_hierarchy is None:
        raise ConflictError("Reactivate the unit's phase, building and floor before restoring it.")
    before = {"removed_at": unit.removed_at.isoformat(), "is_active": unit.is_active}
    unit.removed_at = None
    unit.is_active = True
    record_event(
        session,
        action="unit.restored",
        entity_type="unit",
        entity_id=unit.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=before,
        after={
            "project_id": str(project.id),
            "reference": unit.unit_reference,
            "removed_at": None,
            "is_active": True,
            "commercial_status": unit.commercial_status,
            "linked_history_retained": True,
        },
    )
    session.commit()
    session.refresh(unit)
    return unit


def delete_record(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    kind: str,
    identifier: uuid.UUID,
    reason: str,
    permanent: bool = False,
) -> None:
    if permanent and kind != "units":
        raise ValidationError("Explicit permanent deletion is supported for units only.")
    if kind == "units" and not actor.is_master_admin:
        raise PermissionDeniedError("Only Master Administrator may remove a unit.")
    if not actor.is_system_admin:
        raise PermissionDeniedError("Only an administrator may delete inventory records.")
    if not reason.strip():
        raise ValidationError("Give a reason for deleting this record.")
    model = {
        "units": Unit,
        "floors": Floor,
        "buildings": Building,
        "phases": Phase,
        "area-types": AreaType,
        "sub-assets": InventorySubAsset,
        "area-schedules": UnitAreaSchedule,
    }.get(kind)
    if model is None:
        raise NotFoundError("Inventory record not found.")
    lock_project(session, project.id)
    row = session.scalar(
        select(model)
        .where(
            model.id == identifier,
            model.project_id == project.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Inventory record not found.")
    if isinstance(row, Unit) and row.removed_at is not None and not permanent:
        return
    if isinstance(row, Unit) and row.commercial_status not in {"unreleased", "available", "held"}:
        if permanent:
            raise ConflictError(
                "This unit has a commercial commitment. Permanent deletion is blocked; "
                "its sales, financial and legal history must be retained."
            )
        remove_unit(session, project=project, actor=actor, identifier=identifier, reason=reason)
        return
    if isinstance(row, UnitAreaSchedule) and row.status != "draft":
        raise ConflictError("Approved measurements are retained. Create a new revision instead.")
    if isinstance(row, AreaType):
        from app.modules.pricing.option_usage import inventory_option_in_use

        if inventory_option_in_use(
            session, project_id=project.id, category="area_type", code=row.code
        ):
            raise ConflictError("This area type is used by pricing. Retire it to preserve history.")
    if isinstance(row, InventorySubAsset) and row.linked_unit_id is not None:
        from app.modules.pricing.option_usage import unit_has_price_history

        linked = session.get(Unit, row.linked_unit_id)
        if (
            linked is None
            or linked.commercial_status != "unreleased"
            or unit_has_price_history(session, project_id=project.id, unit_id=row.linked_unit_id)
        ):
            raise ConflictError(
                "This asset belongs to a released or priced unit. "
                "Review its unit and detach it before deleting the unused asset."
            )
    reference = next(
        (
            getattr(row, key)
            for key in ("unit_reference", "code", "asset_reference", "revision_code")
            if getattr(row, key, None)
        ),
        str(identifier),
    )
    try:
        if isinstance(row, Unit):
            schedules = select(UnitAreaSchedule.id).where(UnitAreaSchedule.unit_id == row.id)
            session.execute(
                delete(UnitAreaValue).where(UnitAreaValue.unit_area_schedule_id.in_(schedules))
            )
            session.execute(delete(UnitAreaSchedule).where(UnitAreaSchedule.unit_id == row.id))
            for child in (UnitCustomFieldValue, UnitDocument, UnitFeature, UnitStatusEvent):
                session.execute(delete(child).where(child.unit_id == row.id))
        elif isinstance(row, Phase):
            session.execute(delete(UserPhaseAccess).where(UserPhaseAccess.phase_id == row.id))
        elif isinstance(row, UnitAreaSchedule):
            session.execute(
                delete(UnitAreaValue).where(UnitAreaValue.unit_area_schedule_id == row.id)
            )
        session.delete(row)
        session.flush()
        record_event(
            session,
            action=f"{kind[:-1].replace('-', '_')}.deleted",
            entity_type=kind[:-1].replace("-", "_"),
            entity_id=identifier,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
            reason=reason.strip(),
            before={"project_id": str(project.id), "reference": reference},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if kind == "units" and permanent:
            # Report a safe business label, never a raw PostgreSQL exception.
            table = getattr(getattr(exc.orig, "diag", None), "table_name", None)
            label = {
                "unit_price_versions": "unit price versions",
                "unit_price_components": "unit price components",
                "reservations": "reservations",
                "sale_contracts": "sale contracts",
                "commission_grants": "commissions",
                "unit_stage_events": "construction progress",
                "unit_economics_allocations": "cost allocations",
                "unit_economics_unit_costs": "unit costs",
                "inventory_sub_assets": "parking or storage assets",
                "inventory_common_areas": "common-area allocations",
            }.get(table, "dependent business records")
            raise ConflictError(
                f"Permanent deletion is blocked by linked {label}. "
                "No records were deleted. Review those records first, or keep this unit "
                "in Removed units to preserve its history."
            ) from exc
        if kind == "units":
            remove_unit(session, project=project, actor=actor, identifier=identifier, reason=reason)
            return
        raise ConflictError(
            "This record is still referenced. Move or delete its child records first. "
            "Pricing, sales, financial and legal history must be retained; "
            "deactivate the record instead."
        ) from exc


def remove_unit(
    session: Session, *, project: Project, actor: ActorContext, identifier: uuid.UUID, reason: str
) -> None:
    """Owner-only retained removal, regardless of the commercial commitment.

    This is not contract cancellation or receipt reversal. Current registers
    share the removal marker; legal and financial evidence keeps its identity.
    """
    if not actor.is_master_admin:
        raise PermissionDeniedError("Only Master Administrator may remove a unit.")
    if not reason.strip():
        raise ValidationError("Give a reason for removing this unit.")
    lock_project(session, project.id)
    unit = session.scalar(
        select(Unit)
        .where(Unit.id == identifier, Unit.project_id == project.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if unit is None:
        raise NotFoundError("Unit not found.")
    if unit.removed_at is not None:
        return
    before = {"is_active": unit.is_active, "commercial_status": unit.commercial_status}
    unit.removed_at = datetime.now(UTC)
    unit.is_active = False
    record_event(
        session,
        action="unit.removed",
        entity_type="unit",
        entity_id=unit.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=before,
        after={
            "project_id": str(project.id),
            "reference": unit.unit_reference,
            "removed_at": unit.removed_at.isoformat(),
            "is_active": False,
            "removed_from": ["inventory", "current_sales"],
            "linked_history_retained": True,
        },
    )
    session.commit()
