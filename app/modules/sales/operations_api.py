"""Operations routes; authorization and transactions belong to the service."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.sales import operations
from app.modules.sales.operations_schemas import BuyerInput, OperationsRead, PipelineInput
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
