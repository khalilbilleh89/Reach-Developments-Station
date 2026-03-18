"""
construction.api

CRUD API router for the Construction domain.

Endpoints:
  POST   /api/v1/construction/scopes
  GET    /api/v1/construction/scopes
  GET    /api/v1/construction/scopes/{scope_id}
  PATCH  /api/v1/construction/scopes/{scope_id}
  DELETE /api/v1/construction/scopes/{scope_id}

  POST   /api/v1/construction/milestones
  GET    /api/v1/construction/milestones
  GET    /api/v1/construction/milestones/{milestone_id}
  PATCH  /api/v1/construction/milestones/{milestone_id}
  DELETE /api/v1/construction/milestones/{milestone_id}

  POST   /api/v1/construction/scopes/{scope_id}/engineering-items
  GET    /api/v1/construction/scopes/{scope_id}/engineering-items
  PATCH  /api/v1/construction/engineering-items/{item_id}
  DELETE /api/v1/construction/engineering-items/{item_id}
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.construction.exceptions import ConstructionConflictError
from app.modules.construction.schemas import (
    ConstructionMilestoneCreate,
    ConstructionMilestoneList,
    ConstructionMilestoneResponse,
    ConstructionMilestoneUpdate,
    ConstructionScopeCreate,
    ConstructionScopeList,
    ConstructionScopeResponse,
    ConstructionScopeUpdate,
    EngineeringItemCreate,
    EngineeringItemList,
    EngineeringItemResponse,
    EngineeringItemUpdate,
)
from app.modules.construction.service import ConstructionService

router = APIRouter(tags=["construction"])


def get_service(db: Session = Depends(get_db)) -> ConstructionService:
    return ConstructionService(db)


# ── Scope endpoints ──────────────────────────────────────────────────────────

@router.post("/construction/scopes", response_model=ConstructionScopeResponse, status_code=201)
def create_scope(
    data: ConstructionScopeCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionScopeResponse:
    """Create a new construction scope."""
    return service.create_scope(data)


@router.get("/construction/scopes", response_model=ConstructionScopeList)
def list_scopes(
    service: Annotated[ConstructionService, Depends(get_service)],
    project_id: Optional[str] = Query(default=None),
    phase_id: Optional[str] = Query(default=None),
    building_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ConstructionScopeList:
    """List construction scopes with optional filters."""
    return service.list_scopes(
        project_id=project_id,
        phase_id=phase_id,
        building_id=building_id,
        skip=skip,
        limit=limit,
    )


@router.get("/construction/scopes/{scope_id}", response_model=ConstructionScopeResponse)
def get_scope(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionScopeResponse:
    """Get a construction scope by ID."""
    return service.get_scope(scope_id)


@router.patch("/construction/scopes/{scope_id}", response_model=ConstructionScopeResponse)
def update_scope(
    scope_id: str,
    data: ConstructionScopeUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionScopeResponse:
    """Update a construction scope."""
    return service.update_scope(scope_id, data)


@router.delete("/construction/scopes/{scope_id}", status_code=204)
def delete_scope(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete a construction scope (cascades to milestones)."""
    service.delete_scope(scope_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Milestone endpoints ──────────────────────────────────────────────────────

@router.post("/construction/milestones", response_model=ConstructionMilestoneResponse, status_code=201)
def create_milestone(
    data: ConstructionMilestoneCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionMilestoneResponse:
    """Create a new construction milestone."""
    return service.create_milestone(data)


@router.get("/construction/milestones", response_model=ConstructionMilestoneList)
def list_milestones(
    service: Annotated[ConstructionService, Depends(get_service)],
    scope_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ConstructionMilestoneList:
    """List construction milestones with optional scope filter."""
    return service.list_milestones(scope_id=scope_id, skip=skip, limit=limit)


@router.get("/construction/milestones/{milestone_id}", response_model=ConstructionMilestoneResponse)
def get_milestone(
    milestone_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionMilestoneResponse:
    """Get a construction milestone by ID."""
    return service.get_milestone(milestone_id)


@router.patch("/construction/milestones/{milestone_id}", response_model=ConstructionMilestoneResponse)
def update_milestone(
    milestone_id: str,
    data: ConstructionMilestoneUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionMilestoneResponse:
    """Update a construction milestone (supports progress updates)."""
    return service.update_milestone(milestone_id, data)


@router.delete("/construction/milestones/{milestone_id}", status_code=204)
def delete_milestone(
    milestone_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete a construction milestone."""
    service.delete_milestone(milestone_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Engineering item endpoints ───────────────────────────────────────────────


@router.post(
    "/construction/scopes/{scope_id}/engineering-items",
    response_model=EngineeringItemResponse,
    status_code=201,
)
def create_engineering_item(
    scope_id: str,
    data: EngineeringItemCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> EngineeringItemResponse:
    """Create a new engineering item within a construction scope."""
    try:
        return service.create_engineering_item(scope_id, data)
    except ConstructionConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/construction/scopes/{scope_id}/engineering-items",
    response_model=EngineeringItemList,
)
def list_engineering_items(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> EngineeringItemList:
    """List engineering items for a construction scope."""
    return service.list_engineering_items(scope_id=scope_id, skip=skip, limit=limit)


@router.patch(
    "/construction/engineering-items/{item_id}",
    response_model=EngineeringItemResponse,
)
def update_engineering_item(
    item_id: str,
    data: EngineeringItemUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> EngineeringItemResponse:
    """Update an engineering item."""
    try:
        return service.update_engineering_item(item_id, data)
    except ConstructionConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/construction/engineering-items/{item_id}", status_code=204)
def delete_engineering_item(
    item_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete an engineering item."""
    service.delete_engineering_item(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
