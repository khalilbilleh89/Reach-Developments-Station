"""Saved project strategy diagrams."""

import uuid

from fastapi import APIRouter, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.projects import matrix_service as service
from app.modules.projects.matrix_schemas import (
    MatrixDirectory,
    MatrixFields,
    MatrixPoint,
    MatrixRead,
    MatrixRemoval,
    MatrixUpdate,
)

router = APIRouter(prefix="/projects/{project_id}/matrices", tags=["matrix"])


@router.get("", response_model=MatrixDirectory)
def list_matrices(project_id: uuid.UUID, session: DbSession, actor: ActiveActor) -> MatrixDirectory:
    return service.directory(session, project_id, actor)


@router.post("", response_model=MatrixRead, status_code=201)
def create_matrix(
    project_id: uuid.UUID, body: MatrixFields, session: DbSession, actor: ActiveActor
) -> MatrixRead:
    return service.save(session, project_id, actor, body)


@router.post("/preview", response_model=list[MatrixPoint])
def preview_matrix(
    project_id: uuid.UUID, body: MatrixFields, session: DbSession, actor: ActiveActor
) -> list[MatrixPoint]:
    service.scope(session, project_id, actor)
    return service.points(body)


@router.put("/{matrix_id}", response_model=MatrixRead)
def update_matrix(
    project_id: uuid.UUID,
    matrix_id: uuid.UUID,
    body: MatrixUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> MatrixRead:
    return service.save(session, project_id, actor, body, matrix_id, body.version)


@router.post("/{matrix_id}/delete", status_code=204)
def delete_matrix(
    project_id: uuid.UUID,
    matrix_id: uuid.UUID,
    body: MatrixRemoval,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.remove(session, project_id, matrix_id, actor, body.version, body.reason)
    return Response(status_code=204)
