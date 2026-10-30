"""Commercial FAQ routes, using existing Sales project access."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.core.xlsx import MAX_BYTES
from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.sales import faq, faq_import
from app.modules.sales.faq_schemas import FaqInput, FaqList, FaqRead, FaqUpdate
from app.modules.sales.permissions import SalesProject
from app.modules.sales.schemas import SalesImportReportRead

router = APIRouter(prefix="/projects/{project_id}/faqs", tags=["sales"])


@router.get("/import/template")
def faq_template(session: DbSession, actor: ActiveActor, project: SalesProject) -> Response:
    return Response(
        faq_import.template(session, project, actor),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="faq-template.xlsx"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/import/{operation}", response_model=SalesImportReportRead)
async def create_faq_import(
    operation: Literal["validate", "apply"],
    request: Request,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SalesImportReportRead:
    faq.require_writer(session, project, actor)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Upload an Excel file up to 5 MB.")
        body.extend(chunk)
    return await run_in_threadpool(
        faq_import.process, session, project, actor, bytes(body), apply=operation == "apply"
    )


@router.get("", response_model=FaqList)
def read_faqs(session: DbSession, actor: ActiveActor, project: SalesProject) -> FaqList:
    return faq.list_faqs(session, project, actor)


@router.post("", response_model=FaqRead, status_code=201)
def create_faq(
    payload: FaqInput, session: DbSession, actor: ActiveActor, project: SalesProject
) -> FaqRead:
    return faq.create(session, project, actor, payload)


@router.put("/{faq_id}", response_model=FaqRead)
def update_faq(
    faq_id: uuid.UUID,
    payload: FaqUpdate,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> FaqRead:
    return faq.update(session, project, actor, faq_id, payload)


@router.delete("/{faq_id}", status_code=204)
def delete_faq(
    faq_id: uuid.UUID,
    version: Annotated[int, Query(ge=1)],
    reason: Annotated[str, Query(min_length=1, max_length=500)],
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> Response:
    faq.delete(session, project, actor, faq_id, version, reason)
    return Response(status_code=204)
