import uuid

from fastapi import APIRouter, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.projects import escalation_service as service
from app.modules.projects.escalation_schemas import (
    EscalationFields,
    EscalationRead,
    EscalationRegister,
    EscalationRemoval,
    EscalationUpdate,
)

router = APIRouter(prefix="/projects/{project_id}/price-escalations", tags=["price-escalations"])


@router.get("", response_model=EscalationRegister)
def list_price_escalations(
    project_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> EscalationRegister:
    return service.directory(session, project_id, actor)


@router.post("", response_model=EscalationRead, status_code=201)
def create_price_escalation(
    project_id: uuid.UUID, body: EscalationFields, session: DbSession, actor: ActiveActor
) -> EscalationRead:
    return service.save(session, project_id, actor, body.model_dump())


@router.patch("/{entry_id}", response_model=EscalationRead)
def update_price_escalation(
    project_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: EscalationUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> EscalationRead:
    return service.save(session, project_id, actor, body.model_dump(exclude_unset=True), entry_id)


@router.post("/{entry_id}/delete", status_code=204)
def delete_price_escalation(
    project_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: EscalationRemoval,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.remove(session, project_id, entry_id, actor, body.version, body.reason)
    return Response(status_code=204)
