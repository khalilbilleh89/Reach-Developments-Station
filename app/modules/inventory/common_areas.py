"""Measured shared areas. Each physical area is recorded once, with retained audit."""

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.models import CommonArea, Unit
from app.modules.inventory.permissions import (
    require_inventory_structure_writer,
    require_operational_project,
    visible_phase_ids,
)
from app.modules.projects.schemas import StrictRequest
from app.modules.projects.service import lock_project


class AreaInput(StrictRequest):
    label: str = Field(min_length=1, max_length=200)
    category: Literal["common", "garage", "community", "roads_pavements"]
    area_sqm: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    apartment_id: uuid.UUID | None = None
    source_reference: str = Field(min_length=1, max_length=500)


class AreaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    label: str
    category: str
    area_sqm: Decimal
    apartment_id: uuid.UUID | None
    source_reference: str


def require_whole_project(session: Session, project_id: uuid.UUID, actor: ActorContext) -> None:
    if visible_phase_ids(session, project_id=project_id, actor=actor) is not None:
        raise PermissionDeniedError("Common Areas requires whole-project access.")


def list_areas(session: Session, project_id: uuid.UUID) -> list[CommonArea]:
    return list(
        session.scalars(
            select(CommonArea)
            .where(CommonArea.project_id == project_id)
            .order_by(CommonArea.category, CommonArea.label, CommonArea.id)
        )
    )


def save(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    payload: AreaInput,
    area_id: uuid.UUID | None = None,
) -> CommonArea:
    require_inventory_structure_writer(actor)
    project = lock_project(session, project_id)
    require_whole_project(session, project_id, actor)
    require_operational_project(project)
    values = payload.model_dump()
    for key in ("label", "source_reference"):
        values[key] = values[key].strip()
        if not values[key]:
            raise ValidationError("Name and source reference must not be blank.")
    duplicates = select(CommonArea.id).where(
        CommonArea.project_id == project_id, CommonArea.label == values["label"]
    )
    if area_id is not None:
        duplicates = duplicates.where(CommonArea.id != area_id)
    if session.scalar(duplicates) is not None:
        raise ConflictError("That area name is already recorded; edit its measurement instead.")
    if payload.apartment_id is not None:
        unit = session.scalar(
            select(Unit).where(
                Unit.id == payload.apartment_id,
                Unit.project_id == project_id,
                Unit.is_active.is_(True),
                Unit.asset_class == "apartment",
            )
        )
        if unit is None:
            raise NotFoundError("Active apartment not found in this project.")
        if payload.category != "common":
            raise ValidationError("Only common area may be allocated to an apartment.")
    row = None
    before = None
    if area_id is not None:
        row = session.scalar(
            select(CommonArea)
            .where(CommonArea.id == area_id, CommonArea.project_id == project_id)
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise NotFoundError("Common area record not found.")
        before = AreaRead.model_validate(row).model_dump(mode="json")
    if row is None:
        row = CommonArea(project_id=project_id, **values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    session.flush()
    record_event(
        session,
        action="common_area.updated" if area_id else "common_area.created",
        entity_type="common_area",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=AreaRead.model_validate(row).model_dump(mode="json"),
    )
    session.commit()
    session.refresh(row)
    return row


def delete(
    session: Session, project_id: uuid.UUID, actor: ActorContext, area_id: uuid.UUID, reason: str
) -> None:
    require_inventory_structure_writer(actor)
    project = lock_project(session, project_id)
    require_whole_project(session, project_id, actor)
    require_operational_project(project)
    if not reason.strip():
        raise ValidationError("A deletion reason is required.")
    row = session.scalar(
        select(CommonArea)
        .where(CommonArea.id == area_id, CommonArea.project_id == project_id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Common area record not found.")
    record_event(
        session,
        action="common_area.deleted",
        entity_type="common_area",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=AreaRead.model_validate(row).model_dump(mode="json"),
        after={"reason": reason.strip()},
    )
    session.delete(row)
    session.commit()
