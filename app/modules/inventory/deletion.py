"""Administrator deletion of catalogue records, never their business transactions."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
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
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project


def delete_record(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    kind: str,
    identifier: uuid.UUID,
    reason: str,
) -> None:
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
    if isinstance(row, Unit) and row.commercial_status not in {"unreleased", "available", "held"}:
        raise ConflictError(
            "This unit has a sales commitment. Cancel it through Sales; "
            "its history cannot be deleted."
        )
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
        raise ConflictError(
            "This record is still referenced. Move or delete its child records first. "
            "Pricing, sales, financial and legal history must be retained; "
            "deactivate the record instead."
        ) from exc
