"""Delete unused buyer records without erasing any transaction they participated in."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import permissions
from app.modules.sales.models import Client, ClientParty


def delete_client(
    session: Session, *, project: Project, client_id: uuid.UUID, actor: ActorContext, reason: str
) -> None:
    if not actor.is_system_admin:
        raise PermissionDeniedError("Only an administrator may delete buyers.")
    if not reason.strip():
        raise ValidationError("Give a reason for deleting this buyer.")
    lock_project(session, project.id)
    permissions.require_visible_client(session, project=project, client_id=client_id, actor=actor)
    client = session.scalar(
        select(Client)
        .where(Client.id == client_id, Client.project_id == project.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    try:
        session.execute(delete(ClientParty).where(ClientParty.client_id == client_id))
        session.delete(client)
        session.flush()
        record_event(
            session,
            action="client.deleted",
            entity_type="client",
            entity_id=client_id,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
            reason=reason.strip(),
            before={"project_id": str(project.id), "client_number": client.client_number},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "This buyer has transaction history and cannot be deleted. Deactivate the buyer "
            "instead; their contracts and payments must be retained."
        ) from exc
