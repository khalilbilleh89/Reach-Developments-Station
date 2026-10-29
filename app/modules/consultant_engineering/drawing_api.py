"""Project drawings and authorized PDF review, independent of consultant appointments."""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.consultant_engineering import drawing_service as service
from app.modules.consultant_engineering.drawing_schemas import (
    DrawingFields,
    DrawingPreview,
    DrawingRead,
    DrawingRemoval,
    DrawingUpdate,
    DrawingUpload,
)

router = APIRouter(prefix="/projects/{project_id}/drawings", tags=["drawings"])


@router.get("", response_model=list[DrawingRead])
def list_drawings(
    project_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> list[DrawingRead]:
    service.scope(session, project_id, actor)
    return service.list_drawings(session, project_id)


@router.post("", response_model=DrawingRead, status_code=201)
async def create_drawing(
    project_id: uuid.UUID,
    fields: Annotated[DrawingUpload, Query()],
    request: Request,
    session: DbSession,
    actor: ActiveActor,
) -> DrawingRead:
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
        DrawingFields.model_validate(fields.model_dump(exclude={"filename"})),
        fields.filename,
        bytes(document),
    )
    return DrawingRead.model_validate(row)


@router.put("/{drawing_id}", response_model=DrawingRead)
def update_drawing(
    project_id: uuid.UUID,
    drawing_id: uuid.UUID,
    body: DrawingUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> DrawingRead:
    service.scope(session, project_id, actor, write=True)
    row = service.drawing(session, project_id, drawing_id)
    return DrawingRead.model_validate(service.update(session, row, actor, body))


@router.get("/{drawing_id}/document")
def download_drawing(
    project_id: uuid.UUID,
    drawing_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.scope(session, project_id, actor)
    row = service.drawing(session, project_id, drawing_id)
    return Response(
        content=row.document,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.filename, safe='')}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox",
        },
    )


@router.post("/{drawing_id}/delete", status_code=204)
def delete_drawing(
    project_id: uuid.UUID,
    drawing_id: uuid.UUID,
    body: DrawingRemoval,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.scope(session, project_id, actor, write=True)
    service.remove(
        session,
        service.drawing(session, project_id, drawing_id),
        actor,
        body.reason,
        body.expected_version,
    )
    return Response(status_code=204)


@router.get("/{drawing_id}/preview", response_model=DrawingPreview)
def preview_drawing(
    project_id: uuid.UUID,
    drawing_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict:
    service.scope(session, project_id, actor)
    row = service.drawing(session, project_id, drawing_id)
    data = row.document
    session.rollback()  # Release the read transaction before rendering.
    response.headers["Cache-Control"] = "private, no-store"
    return service.preview(data, page)
