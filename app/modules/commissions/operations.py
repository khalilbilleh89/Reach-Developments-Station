"""Client-linked fixed commissions, independent of sales distribution and cash."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.commissions.models import OperationsCommission
from app.modules.commissions.operations_schemas import (
    ClientOption,
    OperationsInput,
    OperationsOut,
    OperationsRegister,
    OperationsUpdate,
)
from app.modules.commissions.permissions import require_preparer
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import service as sales


def register(session: Session, project: Project, actor: ActorContext) -> OperationsRegister:
    rows = session.scalars(
        select(OperationsCommission)
        .where(
            OperationsCommission.project_id == project.id,
            OperationsCommission.is_deleted.is_(False),
        )
        .order_by(OperationsCommission.created_at.desc(), OperationsCommission.id)
    )
    clients = sales.list_clients(session, project=project, actor=actor, is_active=True)
    return OperationsRegister(
        items=[OperationsOut.model_validate(row) for row in rows],
        clients=[
            ClientOption(id=row.id, display_name=row.display_name, client_number=row.client_number)
            for row in clients
        ],
        currency_id=project.base_currency_id,
    )


def _row(
    session: Session, project: Project, identifier: uuid.UUID, version: int
) -> OperationsCommission:
    row = session.scalar(
        select(OperationsCommission)
        .where(
            OperationsCommission.project_id == project.id,
            OperationsCommission.id == identifier,
            OperationsCommission.is_deleted.is_(False),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Operations commission not found.")
    if row.version != version:
        raise ConflictError(
            "This operations commission changed. Reopen it before saving or deleting."
        )
    return row


def _client_name(
    session: Session, project: Project, actor: ActorContext, client_id: uuid.UUID
) -> str:
    client = sales.get_client(session, project=project, actor=actor, client_id=client_id)
    if not client.is_active:
        raise ConflictError("Choose an active client.")
    return client.display_name


def _audit(
    session: Session,
    actor: ActorContext,
    row: OperationsCommission,
    action: str,
    before: dict | None = None,
    reason: str | None = None,
) -> None:
    record_event(
        session,
        action=f"operations_commission.{action}",
        entity_type="operations_commission",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after={
            **OperationsOut.model_validate(row).model_dump(mode="json"),
            "is_deleted": row.is_deleted,
        },
        reason=reason,
    )


def create(
    session: Session, project: Project, actor: ActorContext, payload: OperationsInput
) -> OperationsOut:
    require_preparer(actor)
    project = lock_project(session, project.id)
    name = _client_name(session, project, actor, payload.client_id)
    row = OperationsCommission(
        project_id=project.id,
        currency_id=project.base_currency_id,
        client_display=name,
        **payload.model_dump(),
    )
    session.add(row)
    session.flush()
    _audit(session, actor, row, "created")
    result = OperationsOut.model_validate(row)
    session.commit()
    return result


def update(
    session: Session,
    project: Project,
    actor: ActorContext,
    identifier: uuid.UUID,
    payload: OperationsUpdate,
) -> OperationsOut:
    require_preparer(actor)
    lock_project(session, project.id)
    row = _row(session, project, identifier, payload.expected_version)
    before = OperationsOut.model_validate(row).model_dump(mode="json")
    # Retired clients remain valid on existing entries; new selections must be active.
    if row.client_id != payload.client_id:
        row.client_display = _client_name(session, project, actor, payload.client_id)
    for key, value in payload.model_dump(exclude={"expected_version"}).items():
        setattr(row, key, value)
    row.version += 1
    _audit(session, actor, row, "updated", before)
    result = OperationsOut.model_validate(row)
    session.commit()
    return result


def delete(
    session: Session,
    project: Project,
    actor: ActorContext,
    identifier: uuid.UUID,
    version: int,
    reason: str,
) -> None:
    require_preparer(actor)
    lock_project(session, project.id)
    row = _row(session, project, identifier, version)
    before = OperationsOut.model_validate(row).model_dump(mode="json")
    row.is_deleted = True
    row.version += 1
    _audit(session, actor, row, "deleted", before, reason)
    session.commit()
