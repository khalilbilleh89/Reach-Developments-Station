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
  POST   /api/v1/construction/milestones/{milestone_id}/progress

  POST   /api/v1/construction/milestones/{milestone_id}/progress-updates
  GET    /api/v1/construction/milestones/{milestone_id}/progress-updates
  GET    /api/v1/construction/progress-updates/{update_id}
  DELETE /api/v1/construction/progress-updates/{update_id}

  POST   /api/v1/construction/scopes/{scope_id}/engineering-items
  GET    /api/v1/construction/scopes/{scope_id}/engineering-items
  PATCH  /api/v1/construction/engineering-items/{item_id}
  DELETE /api/v1/construction/engineering-items/{item_id}

  POST   /api/v1/construction/scopes/{scope_id}/cost-items
  GET    /api/v1/construction/scopes/{scope_id}/cost-items
  GET    /api/v1/construction/scopes/{scope_id}/cost-summary
  GET    /api/v1/construction/cost-items/{cost_item_id}
  PATCH  /api/v1/construction/cost-items/{cost_item_id}
  DELETE /api/v1/construction/cost-items/{cost_item_id}

  POST   /api/v1/construction/dependencies
  GET    /api/v1/construction/scopes/{scope_id}/dependencies
  GET    /api/v1/construction/dependencies/{dependency_id}
  DELETE /api/v1/construction/dependencies/{dependency_id}

  GET    /api/v1/construction/scopes/{scope_id}/schedule
  POST   /api/v1/construction/scopes/{scope_id}/schedule/recompute
  GET    /api/v1/construction/scopes/{scope_id}/critical-path
  GET    /api/v1/construction/scopes/{scope_id}/progress
  GET    /api/v1/construction/scopes/{scope_id}/variance
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.construction.exceptions import ConstructionConflictError
from app.modules.construction.schemas import (
    ConstructionCostItemCreate,
    ConstructionCostItemList,
    ConstructionCostItemResponse,
    ConstructionCostItemUpdate,
    ConstructionCostSummary,
    ConstructionDashboardResponse,
    ConstructionMilestoneCreate,
    ConstructionMilestoneList,
    ConstructionMilestoneResponse,
    ConstructionMilestoneUpdate,
    ConstructionScopeCreate,
    ConstructionScopeList,
    ConstructionScopeResponse,
    ConstructionScopeUpdate,
    CriticalPathResponse,
    EngineeringItemCreate,
    EngineeringItemList,
    EngineeringItemResponse,
    EngineeringItemUpdate,
    MilestoneDependencyCreate,
    MilestoneDependencyList,
    MilestoneDependencyResponse,
    MilestoneProgressUpdate,
    ProgressUpdateCreate,
    ProgressUpdateList,
    ProgressUpdateResponse,
    ScopeProgressResponse,
    ScopeScheduleResponse,
    ScopeVarianceResponse,
)
from app.modules.construction.service import ConstructionService

router = APIRouter(prefix="/construction", tags=["Construction"], dependencies=[Depends(get_current_user_payload)])


def get_service(db: Session = Depends(get_db)) -> ConstructionService:
    return ConstructionService(db)


# ── Dashboard endpoint ───────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/dashboard",
    response_model=ConstructionDashboardResponse,
)
def get_project_construction_dashboard(
    project_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionDashboardResponse:
    """Get aggregated construction dashboard for a project."""
    return service.get_project_construction_dashboard(project_id)


# ── Scope endpoints ──────────────────────────────────────────────────────────

@router.post("/scopes", response_model=ConstructionScopeResponse, status_code=201)
def create_scope(
    data: ConstructionScopeCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionScopeResponse:
    """Create a new construction scope."""
    return service.create_scope(data)


@router.get("/scopes", response_model=ConstructionScopeList)
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


@router.get("/scopes/{scope_id}", response_model=ConstructionScopeResponse)
def get_scope(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionScopeResponse:
    """Get a construction scope by ID."""
    return service.get_scope(scope_id)


@router.patch("/scopes/{scope_id}", response_model=ConstructionScopeResponse)
def update_scope(
    scope_id: str,
    data: ConstructionScopeUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionScopeResponse:
    """Update a construction scope."""
    return service.update_scope(scope_id, data)


@router.delete("/scopes/{scope_id}", status_code=204)
def delete_scope(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete a construction scope (cascades to milestones)."""
    service.delete_scope(scope_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Milestone endpoints ──────────────────────────────────────────────────────

@router.post("/milestones", response_model=ConstructionMilestoneResponse, status_code=201)
def create_milestone(
    data: ConstructionMilestoneCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionMilestoneResponse:
    """Create a new construction milestone."""
    return service.create_milestone(data)


@router.get("/milestones", response_model=ConstructionMilestoneList)
def list_milestones(
    service: Annotated[ConstructionService, Depends(get_service)],
    scope_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ConstructionMilestoneList:
    """List construction milestones with optional scope filter."""
    return service.list_milestones(scope_id=scope_id, skip=skip, limit=limit)


@router.get("/milestones/{milestone_id}", response_model=ConstructionMilestoneResponse)
def get_milestone(
    milestone_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionMilestoneResponse:
    """Get a construction milestone by ID."""
    return service.get_milestone(milestone_id)


@router.patch("/milestones/{milestone_id}", response_model=ConstructionMilestoneResponse)
def update_milestone(
    milestone_id: str,
    data: ConstructionMilestoneUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionMilestoneResponse:
    """Update a construction milestone (supports progress updates)."""
    return service.update_milestone(milestone_id, data)


@router.delete("/milestones/{milestone_id}", status_code=204)
def delete_milestone(
    milestone_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete a construction milestone."""
    service.delete_milestone(milestone_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/milestones/{milestone_id}/progress",
    response_model=ConstructionMilestoneResponse,
)
def update_milestone_progress(
    milestone_id: str,
    data: MilestoneProgressUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionMilestoneResponse:
    """Record actual progress (progress_percent, actual_start_day, actual_finish_day)
    on a construction milestone."""
    return service.update_milestone_progress(milestone_id, data)


# ── Progress update endpoints ────────────────────────────────────────────────


@router.post(
    "/milestones/{milestone_id}/progress-updates",
    response_model=ProgressUpdateResponse,
    status_code=201,
)
def create_progress_update(
    milestone_id: str,
    data: ProgressUpdateCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProgressUpdateResponse:
    """Record a progress update for a construction milestone."""
    return service.create_progress_update(milestone_id, data)


@router.get(
    "/milestones/{milestone_id}/progress-updates",
    response_model=ProgressUpdateList,
)
def list_progress_updates(
    milestone_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ProgressUpdateList:
    """List all progress updates for a construction milestone."""
    return service.list_progress_updates(milestone_id=milestone_id, skip=skip, limit=limit)


@router.get(
    "/progress-updates/{update_id}",
    response_model=ProgressUpdateResponse,
)
def get_progress_update(
    update_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProgressUpdateResponse:
    """Get a specific progress update by ID."""
    return service.get_progress_update(update_id)


@router.delete("/progress-updates/{update_id}", status_code=204)
def delete_progress_update(
    update_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete a progress update."""
    service.delete_progress_update(update_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Engineering item endpoints ───────────────────────────────────────────────


@router.post(
    "/scopes/{scope_id}/engineering-items",
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
    "/scopes/{scope_id}/engineering-items",
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
    "/engineering-items/{item_id}",
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


@router.delete("/engineering-items/{item_id}", status_code=204)
def delete_engineering_item(
    item_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete an engineering item."""
    service.delete_engineering_item(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Cost item endpoints ──────────────────────────────────────────────────────


@router.post(
    "/scopes/{scope_id}/cost-items",
    response_model=ConstructionCostItemResponse,
    status_code=201,
)
def create_cost_item(
    scope_id: str,
    data: ConstructionCostItemCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionCostItemResponse:
    """Create a new cost line item within a construction scope."""
    return service.create_cost_item(scope_id, data)


@router.get(
    "/scopes/{scope_id}/cost-items",
    response_model=ConstructionCostItemList,
)
def list_cost_items(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    category: Optional[str] = Query(default=None),
) -> ConstructionCostItemList:
    """List cost items for a construction scope with optional category filter."""
    return service.list_cost_items(
        scope_id=scope_id, skip=skip, limit=limit, category=category
    )


@router.get(
    "/scopes/{scope_id}/cost-summary",
    response_model=ConstructionCostSummary,
)
def get_scope_cost_summary(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionCostSummary:
    """Get aggregated cost summary (budget/committed/actual/variance) for a scope."""
    return service.get_scope_cost_summary(scope_id)


@router.get(
    "/cost-items/{cost_item_id}",
    response_model=ConstructionCostItemResponse,
)
def get_cost_item(
    cost_item_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionCostItemResponse:
    """Get a specific cost item by ID."""
    return service.get_cost_item(cost_item_id)


@router.patch(
    "/cost-items/{cost_item_id}",
    response_model=ConstructionCostItemResponse,
)
def update_cost_item(
    cost_item_id: str,
    data: ConstructionCostItemUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionCostItemResponse:
    """Update a cost item."""
    return service.update_cost_item(cost_item_id, data)


@router.delete("/cost-items/{cost_item_id}", status_code=204)
def delete_cost_item(
    cost_item_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete a cost item."""
    service.delete_cost_item(cost_item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Dependency endpoints ─────────────────────────────────────────────────────


@router.post("/dependencies", response_model=MilestoneDependencyResponse, status_code=201)
def create_dependency(
    data: MilestoneDependencyCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> MilestoneDependencyResponse:
    """Create a finish-to-start dependency between two construction milestones."""
    return service.create_dependency(data)


@router.get(
    "/scopes/{scope_id}/dependencies",
    response_model=MilestoneDependencyList,
)
def list_scope_dependencies(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> MilestoneDependencyList:
    """List all milestone dependencies for a construction scope."""
    return service.list_dependencies_for_scope(scope_id)


@router.get(
    "/dependencies/{dependency_id}",
    response_model=MilestoneDependencyResponse,
)
def get_dependency(
    dependency_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> MilestoneDependencyResponse:
    """Get a specific milestone dependency by ID."""
    return service.get_dependency(dependency_id)


@router.delete("/dependencies/{dependency_id}", status_code=204)
def delete_dependency(
    dependency_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete a milestone dependency."""
    service.delete_dependency(dependency_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Schedule endpoints ───────────────────────────────────────────────────────


@router.get(
    "/scopes/{scope_id}/schedule",
    response_model=ScopeScheduleResponse,
)
def get_scope_schedule(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ScopeScheduleResponse:
    """Compute and return the full CPM schedule for a construction scope."""
    return service.get_scope_schedule(scope_id)


@router.post(
    "/scopes/{scope_id}/schedule/recompute",
    response_model=ScopeScheduleResponse,
)
def recompute_scope_schedule(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ScopeScheduleResponse:
    """Recompute and return the CPM schedule for a construction scope."""
    return service.get_scope_schedule(scope_id)


@router.get(
    "/scopes/{scope_id}/critical-path",
    response_model=CriticalPathResponse,
)
def get_critical_path(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> CriticalPathResponse:
    """Return the critical path summary for a construction scope."""
    return service.get_critical_path(scope_id)


@router.get(
    "/scopes/{scope_id}/progress",
    response_model=ScopeProgressResponse,
)
def get_scope_progress(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ScopeProgressResponse:
    """Return aggregated milestone progress overview for a construction scope."""
    return service.get_scope_progress(scope_id)


@router.get(
    "/scopes/{scope_id}/variance",
    response_model=ScopeVarianceResponse,
)
def get_scope_variance(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ScopeVarianceResponse:
    """Return schedule variance analysis (planned vs actual) for a construction scope."""
    return service.get_scope_schedule_variance(scope_id)
