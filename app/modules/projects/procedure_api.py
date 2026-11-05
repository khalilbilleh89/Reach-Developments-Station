"""Saved project strategy diagrams."""

import uuid

from fastapi import APIRouter, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.projects import procedure_service as service
from app.modules.projects.procedure_schemas import (
    ProcedureDirectory,
    ProcedureFields,
    ProcedureRead,
    ProcedureRemoval,
    ProcedureUpdate,
)

router = APIRouter(prefix="/projects/{project_id}/procedures", tags=["procedure"])


@router.get("", response_model=ProcedureDirectory)
def list_procedures(
    project_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> ProcedureDirectory:
    return service.directory(session, project_id, actor)


@router.post("", response_model=ProcedureRead, status_code=201)
def create_procedure(
    project_id: uuid.UUID, body: ProcedureFields, session: DbSession, actor: ActiveActor
) -> ProcedureRead:
    return service.save(session, project_id, actor, body)


@router.put("/{procedure_id}", response_model=ProcedureRead)
def update_procedure(
    project_id: uuid.UUID,
    procedure_id: uuid.UUID,
    body: ProcedureUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> ProcedureRead:
    return service.save(session, project_id, actor, body, procedure_id, body.version)


@router.post("/{procedure_id}/delete", status_code=204)
def delete_procedure(
    project_id: uuid.UUID,
    procedure_id: uuid.UUID,
    body: ProcedureRemoval,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.remove(session, project_id, procedure_id, actor, body.version, body.reason)
    return Response(status_code=204)
