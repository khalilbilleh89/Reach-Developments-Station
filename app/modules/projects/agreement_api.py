"""Final drafts are uploaded atomically with metadata; file reads remain authorized."""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.projects import agreement_service as service
from app.modules.projects.agreement_schemas import (
    AgreementFields,
    AgreementRead,
    AgreementRemoval,
    AgreementUpdate,
    AgreementUpload,
)

router = APIRouter(prefix="/projects/{project_id}/agreements", tags=["agreements"])


@router.get("", response_model=list[AgreementRead])
def list_agreements(
    project_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> list[AgreementRead]:
    service.scope(session, project_id, actor)
    return service.list_agreements(session, project_id)


@router.post("", response_model=AgreementRead, status_code=201)
async def create_agreement(
    project_id: uuid.UUID,
    fields: Annotated[AgreementUpload, Query()],
    request: Request,
    session: DbSession,
    actor: ActiveActor,
) -> AgreementRead:
    # Authorize before accepting any bytes, but without the project row lock:
    # the client decides how slowly the body arrives, and holding the lock that
    # every project write takes for that long would stall the whole project.
    # The read transaction ends before streaming; the lock is taken, and
    # authorization repeated, only once the document is in memory.
    await run_in_threadpool(service.authorize_upload, session, project_id, actor)
    document = bytearray()
    async for chunk in request.stream():
        if len(document) + len(chunk) > service.MAX_DOCUMENT_BYTES:
            raise HTTPException(status_code=413, detail="Documents must be no larger than 10 MB.")
        document.extend(chunk)
    row = await run_in_threadpool(
        service.create_locked,
        session,
        project_id,
        actor,
        AgreementFields.model_validate(fields.model_dump(exclude={"filename"})),
        fields.filename,
        bytes(document),
    )
    return AgreementRead.model_validate(row)


@router.put("/{agreement_id}", response_model=AgreementRead)
def update_agreement(
    project_id: uuid.UUID,
    agreement_id: uuid.UUID,
    body: AgreementUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> AgreementRead:
    service.scope(session, project_id, actor, write=True)
    row = service.agreement(session, project_id, agreement_id)
    return AgreementRead.model_validate(service.update(session, row, actor, body))


@router.get("/{agreement_id}/document")
def download_agreement(
    project_id: uuid.UUID, agreement_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> Response:
    service.scope(session, project_id, actor)
    row = service.agreement(session, project_id, agreement_id)
    return Response(
        content=row.document,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.filename, safe='')}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{agreement_id}/delete", status_code=204)
def delete_agreement(
    project_id: uuid.UUID,
    agreement_id: uuid.UUID,
    body: AgreementRemoval,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.scope(session, project_id, actor, write=True)
    service.remove(
        session,
        service.agreement(session, project_id, agreement_id),
        actor,
        body.reason,
        body.expected_version,
    )
    return Response(status_code=204)
