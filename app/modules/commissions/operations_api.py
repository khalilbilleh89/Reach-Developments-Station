"""Whole-project operations commission routes."""
# FastAPI validates explicit response contracts.
# ruff: noqa: ANN201

import uuid

from fastapi import APIRouter, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.commissions import operations
from app.modules.commissions.operations_schemas import (
    OperationsDelete,
    OperationsInput,
    OperationsOut,
    OperationsRegister,
    OperationsUpdate,
)
from app.modules.commissions.permissions import CommissionProject

router = APIRouter(prefix="/operations")


@router.get("", response_model=OperationsRegister)
def list_operations(project: CommissionProject, session: DbSession, actor: ActiveActor):
    return operations.register(session, project, actor)


@router.post("", response_model=OperationsOut, status_code=201)
def create_operations(
    project: CommissionProject, session: DbSession, actor: ActiveActor, payload: OperationsInput
):
    return operations.create(session, project, actor, payload)


@router.put("/{identifier}", response_model=OperationsOut)
def update_operations(
    project: CommissionProject,
    session: DbSession,
    actor: ActiveActor,
    identifier: uuid.UUID,
    payload: OperationsUpdate,
):
    return operations.update(session, project, actor, identifier, payload)


@router.post("/{identifier}/delete", status_code=204)
def delete_operations(
    project: CommissionProject,
    session: DbSession,
    actor: ActiveActor,
    identifier: uuid.UUID,
    payload: OperationsDelete,
):
    operations.delete(session, project, actor, identifier, payload.expected_version, payload.reason)
    return Response(status_code=204)
