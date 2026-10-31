"""A person's own register state: saved views and preferences.

Every route acts for the caller alone. There is no administrator view of
another person's saved views: they are working habits, not records.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.workspace import service
from app.modules.workspace.schemas import (
    PreferencesRead,
    PreferencesUpdate,
    SavedViewCreate,
    SavedViewRead,
    SavedViewUpdate,
)

router = APIRouter(prefix="/me", tags=["workspace"])


@router.get("/views", response_model=list[SavedViewRead], summary="The caller's saved views")
def list_saved_views(
    session: DbSession,
    actor: ActiveActor,
    screen: Annotated[str | None, Query(max_length=80)] = None,
) -> list[SavedViewRead]:
    return [SavedViewRead.model_validate(row) for row in service.list_views(session, actor, screen)]


@router.post(
    "/views",
    response_model=SavedViewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Save a view of a register",
)
def create_saved_view(
    payload: SavedViewCreate, session: DbSession, actor: ActiveActor
) -> SavedViewRead:
    return SavedViewRead.model_validate(service.create_view(session, actor, payload))


@router.patch(
    "/views/{view_id}", response_model=SavedViewRead, summary="Rename, pin or refilter a view"
)
def update_saved_view(
    view_id: uuid.UUID, payload: SavedViewUpdate, session: DbSession, actor: ActiveActor
) -> SavedViewRead:
    return SavedViewRead.model_validate(service.update_view(session, actor, view_id, payload))


@router.delete(
    "/views/{view_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a saved view"
)
def delete_saved_view(view_id: uuid.UUID, session: DbSession, actor: ActiveActor) -> Response:
    service.delete_view(session, actor, view_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/preferences", response_model=PreferencesRead, summary="The caller's register preferences"
)
def read_preferences(session: DbSession, actor: ActiveActor) -> PreferencesRead:
    return PreferencesRead.model_validate(service.read_preferences(session, actor))


@router.put("/preferences", response_model=PreferencesRead, summary="Set register preferences")
def update_preferences(
    payload: PreferencesUpdate, session: DbSession, actor: ActiveActor
) -> PreferencesRead:
    return PreferencesRead.model_validate(service.update_preferences(session, actor, payload))
