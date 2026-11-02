"""Remove many buyers, Agents or transactions at once, under each record's own rules.

Every ticked record goes through exactly the removal it would get from its own
row: the same permission, the same dependency checks, its own transaction and
its own audit event. A record that must be kept is reported with the reason it
was kept and never blocks the others. Nothing is erased that the single-record
path would retain — a buyer or Agent with history stays, a signed or collected
sale still needs Cancellation, and a removed sale or reservation keeps its
history as cancelled.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.modules.access.dependencies import ActorContext
from app.modules.projects.models import Project
from app.modules.sales import agents, deletion, permissions, removal, service
from app.modules.sales.models import SaleContract
from app.modules.sales.schemas import (
    BulkRemovalRead,
    BulkSkippedRead,
    BulkTransactionItem,
)

#: Errors that mean "keep this one and say why"; anything else is a fault.
_KEPT = (ConflictError, NotFoundError, ValidationError)


def _each(
    session: Session, keys: Iterable[uuid.UUID], remove: Callable[[uuid.UUID], None]
) -> BulkRemovalRead:
    removed: list[uuid.UUID] = []
    skipped: list[BulkSkippedRead] = []
    for key in keys:
        try:
            remove(key)
        except _KEPT as exc:
            # A refused record may have taken locks or flushed nothing yet;
            # either way the next record starts from a clean transaction.
            session.rollback()
            skipped.append(BulkSkippedRead(id=key, message=exc.detail))
        else:
            removed.append(key)
    return BulkRemovalRead(removed=removed, skipped=skipped)


def _reason(reason: str, *, noun: str) -> str:
    if not reason.strip():
        raise ValidationError(f"Give a reason for deleting these {noun}.")
    return reason.strip()


def delete_clients(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    client_ids: list[uuid.UUID],
    reason: str,
) -> BulkRemovalRead:
    """Delete buyers with no transaction history; keep and explain the rest."""
    if not actor.is_system_admin:
        raise PermissionDeniedError("Only an administrator may delete buyers.")
    reason = _reason(reason, noun="buyers")
    return _each(
        session,
        client_ids,
        lambda key: deletion.delete_client(
            session, project=project, actor=actor, client_id=key, reason=reason
        ),
    )


def delete_agents(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    agent_ids: list[uuid.UUID],
    reason: str,
) -> BulkRemovalRead:
    """Delete Agents with no buyer, transaction, commission or attribution history."""
    permissions.require_client_writer(actor)
    reason = _reason(reason, noun="Agents")
    return _each(
        session,
        agent_ids,
        lambda key: agents.delete_agent(
            session, project=project, actor=actor, agent_id=key, reason=reason
        ),
    )


def remove_transactions(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    items: list[BulkTransactionItem],
    reason: str,
) -> BulkRemovalRead:
    """Close unsigned sales and live reservations as cancelled, as their own pages do."""
    if not actor.is_master_admin:
        raise PermissionDeniedError("Only Master Administrator may remove transactions.")
    reason = _reason(reason, noun="transactions")
    kinds = {item.id: item.kind for item in items}

    def remove(key: uuid.UUID) -> None:
        if kinds[key] == "reservation":
            service.cancel_reservation(
                session, project=project, reservation_id=key, actor=actor, reason=reason
            )
            return
        status = session.scalar(
            select(SaleContract.status).where(
                SaleContract.id == key, SaleContract.project_id == project.id
            )
        )
        if status is None:
            raise NotFoundError("Sale not found.")
        # The single-record path treats a repeat as done; a list must say so.
        if status == "cancelled":
            raise ConflictError("This sale was already removed.")
        removal.remove_sale(session, project=project, actor=actor, sale_id=key, reason=reason)

    return _each(session, kinds, remove)
