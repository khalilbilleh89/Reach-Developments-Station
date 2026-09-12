"""Project-owned choices for inventory facts and matching pricing rules."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.models import InventoryOption
from app.modules.projects.service import lock_project


def list_options(session: Session, project_id: uuid.UUID) -> list[InventoryOption]:
    return list(
        session.scalars(
            select(InventoryOption)
            .where(InventoryOption.project_id == project_id)
            .order_by(InventoryOption.category, InventoryOption.sort_order, InventoryOption.label)
        )
    )


def require_option(
    session: Session, *, project_id: uuid.UUID, category: str, code: str
) -> InventoryOption:
    option = session.scalar(
        select(InventoryOption).where(
            InventoryOption.project_id == project_id,
            InventoryOption.category == category,
            InventoryOption.code == code.strip(),
        )
    )
    if option is None:
        raise ValidationError(f"No configured {category} choice '{code}' in this project.")
    if not option.is_active:
        raise ValidationError(f"That {category} choice is no longer active in this project.")
    return option


def _snapshot(option: InventoryOption) -> dict[str, Any]:
    return {
        key: getattr(option, key)
        for key in ("category", "code", "label", "sort_order", "is_active")
    }


def create_option(
    session: Session,
    *,
    project_id: uuid.UUID,
    actor: ActorContext,
    category: str,
    code: str,
    label: str,
    sort_order: int = 0,
) -> InventoryOption:
    lock_project(session, project_id)
    if session.scalar(
        select(InventoryOption.id).where(
            InventoryOption.project_id == project_id,
            InventoryOption.category == category,
            InventoryOption.code == code,
        )
    ):
        raise ConflictError("That code already exists in this project's category.")
    option = InventoryOption(
        project_id=project_id,
        category=category,
        code=code,
        label=label,
        sort_order=sort_order,
        is_active=True,
    )
    session.add(option)
    session.flush()
    record_event(
        session,
        action="inventory_option.created",
        entity_type="inventory_option",
        entity_id=option.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=None,
        after=_snapshot(option),
    )
    session.commit()
    session.refresh(option)
    return option


def update_option(
    session: Session,
    *,
    project_id: uuid.UUID,
    option_id: uuid.UUID,
    actor: ActorContext,
    changes: dict[str, Any],
) -> InventoryOption:
    lock_project(session, project_id)
    option = session.scalar(
        select(InventoryOption)
        .where(InventoryOption.project_id == project_id, InventoryOption.id == option_id)
        .execution_options(populate_existing=True)
    )
    if option is None:
        raise NotFoundError("Inventory choice not found.")
    before = _snapshot(option)
    for key, value in changes.items():
        if key not in {"label", "sort_order", "is_active"} or value is None:
            raise ValidationError("Only label, display order and active status may be changed.")
        setattr(option, key, value)
    record_event(
        session,
        action="inventory_option.updated",
        entity_type="inventory_option",
        entity_id=option.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=_snapshot(option),
    )
    session.commit()
    session.refresh(option)
    return option
