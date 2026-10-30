"""Operations routes; authorization and transactions belong to the service."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.core.xlsx import MAX_BYTES
from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.sales import operations, operations_import
from app.modules.sales.operations_schemas import (
    BuyerInput,
    OperationsImportReport,
    OperationsRead,
    PipelineInput,
)
from app.modules.sales.permissions import SalesProject

router = APIRouter(prefix="/projects/{project_id}/operations", tags=["sales"])


@router.get("", response_model=OperationsRead)
def read_operations(
    session: DbSession, actor: ActiveActor, project: SalesProject
) -> OperationsRead:
    return operations.read(session, project, actor)


@router.put("/pipeline", status_code=204)
def save_pipeline(
    payload: PipelineInput, session: DbSession, actor: ActiveActor, project: SalesProject
) -> Response:
    operations.save_configuration(session, project, actor, payload)
    return Response(status_code=204)


@router.delete("/stages/{stage_id}", status_code=204)
def delete_stage(
    stage_id: uuid.UUID,
    version: Annotated[int, Query(ge=0)],
    reason: Annotated[str, Query(min_length=1, max_length=1000)],
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> Response:
    operations.delete_stage(session, project, actor, stage_id, version, reason)
    return Response(status_code=204)


@router.put("/buyers/{client_id}", status_code=204)
def save_buyer(
    client_id: uuid.UUID,
    payload: BuyerInput,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> Response:
    operations.save_buyer(session, project, actor, client_id, payload)
    return Response(status_code=204)


@router.delete("/buyers/{client_id}", status_code=204)
def delete_buyer_progress(
    client_id: uuid.UUID,
    version: Annotated[int, Query(ge=0)],
    reason: Annotated[str, Query(min_length=1, max_length=1000)],
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> Response:
    operations.delete_buyer_progress(session, project, actor, client_id, version, reason)
    return Response(status_code=204)


@router.get("/import/template")
def operations_template(session: DbSession, actor: ActiveActor, project: SalesProject) -> Response:
    return Response(
        content=operations_import.template(session, project, actor),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="operations-clients.xlsx"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/import/{operation}", response_model=OperationsImportReport)
async def import_operations(
    operation: Literal["validate", "apply"],
    request: Request,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
    reason: Annotated[str, Query(max_length=1000)] = "",
) -> dict:
    operations.require_access(session, project, actor)
    if not operations.allowed(actor, operations.EDIT_ROLES):
        raise HTTPException(status_code=403, detail="You cannot import Operations progress.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Upload an Excel file up to 5 MB.")
        body.extend(chunk)
    return await run_in_threadpool(
        operations_import.process,
        session,
        project,
        actor,
        bytes(body),
        apply=operation == "apply",
        reason=reason,
    )
