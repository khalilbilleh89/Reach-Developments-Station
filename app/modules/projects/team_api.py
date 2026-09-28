"""Project Team directory. These contacts never grant login or project access."""

import uuid

from fastapi import APIRouter, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.projects import team_service as service
from app.modules.projects.team_schemas import (
    TeamDirectory,
    TeamFields,
    TeamMemberRead,
    TeamRemoval,
    TeamUpdate,
)

router = APIRouter(prefix="/projects/{project_id}/team", tags=["team"])


@router.get("", response_model=TeamDirectory)
def list_team(project_id: uuid.UUID, session: DbSession, actor: ActiveActor) -> TeamDirectory:
    return service.directory(session, project_id, actor)


@router.post("", response_model=TeamMemberRead, status_code=201)
def create_team_member(
    project_id: uuid.UUID, body: TeamFields, session: DbSession, actor: ActiveActor
) -> TeamMemberRead:
    return service.save(session, project_id, actor, body.model_dump())


@router.patch("/{member_id}", response_model=TeamMemberRead)
def update_team_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    body: TeamUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> TeamMemberRead:
    return service.save(session, project_id, actor, body.model_dump(exclude_unset=True), member_id)


@router.post("/{member_id}/delete", status_code=204)
def delete_team_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    body: TeamRemoval,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.remove(session, project_id, member_id, actor, body.version, body.reason)
    return Response(status_code=204)
