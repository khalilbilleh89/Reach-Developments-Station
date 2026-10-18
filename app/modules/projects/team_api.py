"""Project Team directory. These contacts never grant login or project access."""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.projects import team_service as service
from app.modules.projects.agreement_service import MAX_DOCUMENT_BYTES
from app.modules.projects.team_schemas import (
    JobDescriptionUpload,
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


@router.post("/{member_id}/job-description", response_model=TeamMemberRead, status_code=201)
async def upload_job_description(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    fields: Annotated[JobDescriptionUpload, Query()],
    request: Request,
    session: DbSession,
    actor: ActiveActor,
) -> TeamMemberRead:
    await run_in_threadpool(
        service.authorize_document_upload, session, project_id, member_id, actor, fields.version
    )
    document = bytearray()
    async for chunk in request.stream():
        if len(document) + len(chunk) > MAX_DOCUMENT_BYTES:
            raise HTTPException(status_code=413, detail="Documents must be no larger than 10 MB.")
        document.extend(chunk)
    return await run_in_threadpool(
        service.save_document,
        session,
        project_id,
        member_id,
        actor,
        fields.version,
        fields.filename,
        bytes(document),
    )


@router.get("/{member_id}/job-description")
def download_job_description(
    project_id: uuid.UUID, member_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> Response:
    row = service.download_document(session, project_id, member_id, actor)
    return Response(
        content=row.document,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.filename, safe='')}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{member_id}/job-description/delete", status_code=204)
def delete_job_description(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    body: TeamRemoval,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.remove_document(session, project_id, member_id, actor, body.version, body.reason)
    return Response(status_code=204)
