"""Project technical-reports and authorized PDF review, independent of consultant appointments."""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.consultant_engineering import report_service as service
from app.modules.consultant_engineering.report_schemas import (
    ReportFields,
    ReportLink,
    ReportPreview,
    ReportRead,
    ReportRemoval,
    ReportUpdate,
    ReportUpload,
)

router = APIRouter(prefix="/projects/{project_id}/technical-reports", tags=["technical-reports"])


@router.get("", response_model=list[ReportRead])
def list_reports(project_id: uuid.UUID, session: DbSession, actor: ActiveActor) -> list[ReportRead]:
    service.scope(session, project_id, actor)
    return service.list_reports(session, project_id)


@router.post("", response_model=ReportRead, status_code=201)
async def create_report(
    project_id: uuid.UUID,
    fields: Annotated[ReportUpload, Query()],
    request: Request,
    session: DbSession,
    actor: ActiveActor,
) -> ReportRead:
    # Authorize before accepting any bytes, but without the project row lock:
    # the client decides how slowly the body arrives, and holding the lock that
    # every project write takes for that long would stall the whole project.
    # The read transaction ends before streaming; the lock is taken, and
    # authorization repeated, only once the document is in memory.
    await run_in_threadpool(service.authorize_upload, session, project_id, actor)
    document = bytearray()
    async for chunk in request.stream():
        if len(document) + len(chunk) > service.MAX_DOCUMENT_BYTES:
            raise HTTPException(status_code=413, detail="Documents must be no larger than 50 MB.")
        document.extend(chunk)
    # Inspect the PDF without rasterizing it. A large report preview must not
    # be a prerequisite for saving its original bytes. No project lock is held.
    data = bytes(document)
    del document
    await run_in_threadpool(service.validate_document, fields.filename, data)
    await run_in_threadpool(service.inspect_document, data)
    row = await run_in_threadpool(
        service.create_locked,
        session,
        project_id,
        actor,
        ReportFields.model_validate(fields.model_dump(exclude={"filename"})),
        fields.filename,
        data,
    )
    return ReportRead.model_validate(row)


@router.post("/links", response_model=ReportRead, status_code=201)
def create_report_link(
    project_id: uuid.UUID, body: ReportLink, session: DbSession, actor: ActiveActor
) -> ReportRead:
    return ReportRead.model_validate(service.create_link(session, project_id, actor, body))


@router.put("/{report_id}", response_model=ReportRead)
def update_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    body: ReportUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> ReportRead:
    service.scope(session, project_id, actor, write=True)
    row = service.report(session, project_id, report_id)
    return ReportRead.model_validate(service.update(session, row, actor, body))


@router.get("/{report_id}/document")
def download_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.scope(session, project_id, actor)
    row = service.report(session, project_id, report_id)
    if row.source_url is not None:
        raise HTTPException(
            status_code=422, detail="This report is a Drive link. Open it in Google Drive."
        )
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


@router.post("/{report_id}/delete", status_code=204)
def delete_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    body: ReportRemoval,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.scope(session, project_id, actor, write=True)
    service.remove(
        session,
        service.report(session, project_id, report_id),
        actor,
        body.reason,
        body.expected_version,
    )
    return Response(status_code=204)


@router.get("/{report_id}/preview", response_model=ReportPreview)
def preview_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict:
    service.scope(session, project_id, actor)
    row = service.report(session, project_id, report_id)
    if row.source_url is not None:
        raise HTTPException(
            status_code=422, detail="This report is a Drive link. Open it in Google Drive."
        )
    data = row.document
    session.rollback()  # Release the read transaction before rendering.
    response.headers["Cache-Control"] = "private, no-store"
    return service.preview(data, page)
