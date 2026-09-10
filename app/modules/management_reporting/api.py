"""Explicit capture plus authorized immutable reads. No mutation/delete API."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.management_reporting import board, comparison, repository, schemas, snapshot

router = APIRouter(prefix="/portfolio/reporting", tags=["management-reporting"])


@router.post("/snapshots", response_model=schemas.SnapshotOut, status_code=201)
def capture(actor: ActiveActor, payload: schemas.Create) -> schemas.SnapshotOut:
    return snapshot.capture(actor, payload)


@router.get("/snapshots", response_model=schemas.SnapshotPage)
def listing(
    session: DbSession,
    actor: ActiveActor,
    scope: schemas.Scope | None = None,
    project_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.SnapshotPage:
    return repository.page(
        session,
        actor,
        scope=scope,
        project_id=project_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@router.get("/comparisons", response_model=schemas.Comparison)
def compare(
    session: DbSession, actor: ActiveActor, from_snapshot_id: uuid.UUID, to_snapshot_id: uuid.UUID
) -> schemas.Comparison:
    prior = repository.detail(session, actor, from_snapshot_id)
    current = repository.detail(session, actor, to_snapshot_id)
    return comparison.compare(session, prior, current)


@router.get("/snapshots/{snapshot_id}", response_model=schemas.SnapshotOut)
def detail(session: DbSession, actor: ActiveActor, snapshot_id: uuid.UUID) -> schemas.SnapshotOut:
    return repository.detail(session, actor, snapshot_id)


@router.get("/snapshots/{snapshot_id}/board-pack", response_model=schemas.BoardPack)
def report(
    session: DbSession,
    actor: ActiveActor,
    snapshot_id: uuid.UUID,
    compare_to_snapshot_id: uuid.UUID | None = None,
) -> schemas.BoardPack:
    current = repository.detail(session, actor, snapshot_id)
    changes = None
    if compare_to_snapshot_id:
        prior = repository.detail(session, actor, compare_to_snapshot_id)
        changes = comparison.compare(session, prior, current)
    return board.board_pack(current, changes)
