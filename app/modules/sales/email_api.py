"""Commercial email template routes, using existing Sales project access."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.sales import email
from app.modules.sales.email_schemas import EmailInput, EmailList, EmailRead, EmailUpdate
from app.modules.sales.permissions import SalesProject

router = APIRouter(prefix="/projects/{project_id}/emails", tags=["sales"])


@router.get("", response_model=EmailList)
def read_emails(session: DbSession, actor: ActiveActor, project: SalesProject) -> EmailList:
    return email.list_emails(session, project, actor)


@router.post("", response_model=EmailRead, status_code=201)
def create_email(
    payload: EmailInput, session: DbSession, actor: ActiveActor, project: SalesProject
) -> EmailRead:
    return email.create(session, project, actor, payload)


@router.put("/{email_id}", response_model=EmailRead)
def update_email(
    email_id: uuid.UUID,
    payload: EmailUpdate,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> EmailRead:
    return email.update(session, project, actor, email_id, payload)


@router.delete("/{email_id}", status_code=204)
def delete_email(
    email_id: uuid.UUID,
    version: Annotated[int, Query(ge=1)],
    reason: Annotated[str, Query(min_length=1, max_length=500)],
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> Response:
    email.delete(session, project, actor, email_id, version, reason)
    return Response(status_code=204)
