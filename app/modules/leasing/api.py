"""Global Leasing register with project-scoped sources and commands."""

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Query, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.leasing import service
from app.modules.leasing.schemas import (
    ClientChoice,
    Create,
    Detail,
    ProjectChoice,
    Register,
    Removal,
    Source,
    Stage,
    UnitChoices,
    Update,
)

router = APIRouter(tags=["leasing"])


@router.get("/leasing", response_model=Register)
def register(
    session: DbSession,
    actor: ActiveActor,
    project_id: uuid.UUID | None = None,
    search: str = Query("", max_length=160),
    stage: Stage | None = None,
    focus: Literal["expiring", "follow_up"] | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    as_at: date | None = None,
) -> Register:
    return service.register(
        session,
        actor,
        project_id,
        search,
        stage,
        focus,
        offset,
        limit,
        as_at or datetime.now(UTC).date(),
    )


@router.get("/leasing/projects", response_model=list[ProjectChoice])
def projects(session: DbSession, actor: ActiveActor) -> list[ProjectChoice]:
    return service.project_choices(session, actor)


@router.get("/projects/{project_id}/leasing/units", response_model=UnitChoices)
def units(
    project_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    search: str = Query("", max_length=160),
    offset: int = Query(0, ge=0),
) -> UnitChoices:
    return service.unit_choices(session, project_id, actor, search, offset)


@router.get("/projects/{project_id}/leasing/clients", response_model=list[ClientChoice])
def clients(
    project_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    search: str = Query("", max_length=160),
) -> list[ClientChoice]:
    return service.clients(session, project_id, actor, search)


@router.get("/projects/{project_id}/leasing/units/{unit_id}", response_model=Source)
def source(
    project_id: uuid.UUID, unit_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> Source:
    return service.source(session, project_id, unit_id, actor)


@router.post("/projects/{project_id}/leasing", response_model=Detail, status_code=201)
def create_instruction(
    project_id: uuid.UUID, body: Create, session: DbSession, actor: ActiveActor
) -> Detail:
    return service.create(session, project_id, actor, body)


@router.get("/projects/{project_id}/leasing/{record_id}", response_model=Detail)
def detail(
    project_id: uuid.UUID, record_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> Detail:
    return service.detail(session, project_id, record_id, actor)


@router.put("/projects/{project_id}/leasing/{record_id}", response_model=Detail)
def update_instruction(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    body: Update,
    session: DbSession,
    actor: ActiveActor,
) -> Detail:
    return service.change(
        session, project_id, record_id, actor, body.expected_version, body.reason, body
    )


@router.post("/projects/{project_id}/leasing/{record_id}/delete", status_code=204)
def delete_instruction(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    body: Removal,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.change(session, project_id, record_id, actor, body.expected_version, body.reason)
    return Response(status_code=204)
