"""Bounded workbook upload and versioned Sales draft review endpoints."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as SchemaError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.errors import ValidationError
from app.core.xlsx import MAX_BYTES
from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.projects.schemas import StrictRequest
from app.modules.sales import import_drafts as service
from app.modules.sales.import_draft_models import SalesImportDraft
from app.modules.sales.permissions import SalesProject
from app.modules.sales.schemas import SalesImportReportRead

router = APIRouter(prefix="/projects/{project_id}/sales/import-drafts", tags=["sales"])


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_key: str
    unit_id: uuid.UUID
    version: int
    status: str
    payload: dict
    reservation_id: uuid.UUID | None
    created_at: datetime


class Review(StrictRequest):
    version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500, pattern=r"\S")


class Correction(Review):
    payload: dict = Field(max_length=20)


@router.get("/fields")
def draft_fields(actor: ActiveActor, project: SalesProject) -> dict[str, list[str]]:
    service.authorize(actor)
    return {name: columns[1:] for name, columns in service.workbook.COLUMNS.items()}


@router.get("/template")
def draft_template(session: DbSession, actor: ActiveActor, project: SalesProject) -> Response:
    return download(service.template(session, project, actor))


def download(content: bytes) -> Response:
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="sales-drafts.xlsx"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/workbook/{operation}", response_model=SalesImportReportRead)
async def import_sales_drafts(
    operation: Literal["validate", "apply"],
    request: Request,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> dict:
    service.authorize(actor)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "Upload an Excel file up to 5 MB.")
        body.extend(chunk)
    return await run_in_threadpool(
        service.process, session, project, actor, bytes(body), apply=operation == "apply"
    )


@router.get("", response_model=list[DraftRead])
def list_import_drafts(
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SalesImportDraft]:
    return service.list_drafts(session, project, actor, offset=offset)


@router.get("/by-reservation/{reservation_id}", response_model=DraftRead | None)
def draft_for_reservation(
    reservation_id: uuid.UUID, session: DbSession, actor: ActiveActor, project: SalesProject
) -> SalesImportDraft | None:
    service.authorize(actor)
    return session.scalar(
        select(SalesImportDraft).where(
            SalesImportDraft.project_id == project.id,
            SalesImportDraft.reservation_id == reservation_id,
        )
    )


@router.get("/{draft_id}", response_model=DraftRead)
def get_import_draft(
    draft_id: uuid.UUID, session: DbSession, actor: ActiveActor, project: SalesProject
) -> SalesImportDraft:
    return service.get_draft(session, project, actor, draft_id)


@router.get("/{draft_id}/workbook")
def export_import_draft(
    draft_id: uuid.UUID, session: DbSession, actor: ActiveActor, project: SalesProject
) -> Response:
    return download(
        service.template(
            session, project, actor, service.get_draft(session, project, actor, draft_id)
        )
    )


@router.put("/{draft_id}", response_model=DraftRead)
def edit_import_draft(
    draft_id: uuid.UUID,
    payload: Correction,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SalesImportDraft:
    try:
        return service.edit(
            session, project, actor, draft_id, payload.version, payload.payload, payload.reason
        )
    except SchemaError as exc:
        raise ValidationError(
            "Invalid draft fields: "
            + "; ".join(
                error["msg"] for error in exc.errors(include_input=False, include_url=False)
            )
        ) from exc


@router.post("/{draft_id}/add", response_model=DraftRead)
def add_import_draft(
    draft_id: uuid.UUID,
    payload: Review,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SalesImportDraft:
    try:
        return service.add_to_sales(
            session, project, actor, draft_id, payload.version, payload.reason
        )
    except SchemaError as exc:
        raise ValidationError(
            "Complete the required fields before adding: "
            + "; ".join(
                ".".join(map(str, error["loc"])) + ": " + error["msg"]
                for error in exc.errors(include_input=False, include_url=False)
            )
        ) from exc


@router.delete("/{draft_id}", status_code=204)
def delete_import_draft(
    draft_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
    version: Annotated[int, Query(ge=1)],
    reason: Annotated[str, Query(min_length=1, max_length=500, pattern=r"\S")],
) -> Response:
    service.delete_draft(session, project, actor, draft_id, version, reason)
    return Response(status_code=204)
