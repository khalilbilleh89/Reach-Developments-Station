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
  POST   /api/v1/construction/milestones/{milestone_id}/cost

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
  GET    /api/v1/construction/scopes/{scope_id}/cost
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

  POST   /api/v1/construction/contractors
  GET    /api/v1/construction/contractors
  GET    /api/v1/construction/contractors/{contractor_id}
  PATCH  /api/v1/construction/contractors/{contractor_id}
  DELETE /api/v1/construction/contractors/{contractor_id}

  POST   /api/v1/construction/packages
  GET    /api/v1/construction/scopes/{scope_id}/packages
  GET    /api/v1/construction/packages/{package_id}
  PATCH  /api/v1/construction/packages/{package_id}
  DELETE /api/v1/construction/packages/{package_id}
  POST   /api/v1/construction/packages/{package_id}/assign-contractor
  POST   /api/v1/construction/packages/{package_id}/milestones/{milestone_id}
  GET    /api/v1/construction/scopes/{scope_id}/procurement-overview

  GET    /api/v1/construction/scopes/{scope_id}/risk-alerts
  GET    /api/v1/construction/scopes/{scope_id}/procurement-risk
  GET    /api/v1/construction/contractors/{contractor_id}/performance

  GET    /api/v1/construction/contractors/{contractor_id}/scorecard
  GET    /api/v1/construction/contractors/{contractor_id}/trend
  GET    /api/v1/construction/scopes/{scope_id}/contractor-scorecards
  GET    /api/v1/construction/scopes/{scope_id}/contractor-ranking

  GET    /api/v1/construction/projects/{project_id}/summary
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
    ContractorCreate,
    ContractorList,
    ContractorPerformanceSummaryResponse,
    ContractorResponse,
    ContractorScorecardResponse,
    ContractorTrendResponse,
    ContractorUpdate,
    CriticalPathResponse,
    EngineeringItemCreate,
    EngineeringItemList,
    EngineeringItemResponse,
    EngineeringItemUpdate,
    MilestoneCostUpdate,
    MilestoneDependencyCreate,
    MilestoneDependencyList,
    MilestoneDependencyResponse,
    MilestoneProgressUpdate,
    PackageAssignContractorRequest,
    ProcurementOverviewResponse,
    ProcurementPackageCreate,
    ProcurementPackageList,
    ProcurementPackageResponse,
    ProcurementPackageUpdate,
    ProcurementRiskOverviewResponse,
    ProgressUpdateCreate,
    ProgressUpdateList,
    ProgressUpdateResponse,
    ProjectConstructionRiskResponse,
    ProjectConstructionExecutiveSummaryResponse,
    ScopeContractorRankingResponse,
    ScopeContractorScorecardListResponse,
    ScopeMilestoneCostResponse,
    ScopeProgressResponse,
    ScopeRiskAlertListResponse,
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


# ── Milestone cost endpoints ─────────────────────────────────────────────────


@router.post(
    "/milestones/{milestone_id}/cost",
    response_model=ConstructionMilestoneResponse,
)
def update_milestone_cost(
    milestone_id: str,
    data: MilestoneCostUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ConstructionMilestoneResponse:
    """Record planned_cost and/or actual_cost on a construction milestone."""
    return service.update_milestone_cost(milestone_id, data)


@router.get(
    "/scopes/{scope_id}/cost",
    response_model=ScopeMilestoneCostResponse,
)
def get_scope_milestone_cost(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ScopeMilestoneCostResponse:
    """Return milestone-level cost variance overview for a construction scope."""
    return service.get_scope_milestone_cost(scope_id)


# ── Contractor endpoints (PR-CONSTR-043) ─────────────────────────────────────


@router.post("/contractors", response_model=ContractorResponse, status_code=201)
def create_contractor(
    data: ContractorCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ContractorResponse:
    """Create a new contractor record."""
    return service.create_contractor(data)


@router.get("/contractors", response_model=ContractorList)
def list_contractors(
    service: Annotated[ConstructionService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ContractorList:
    """List all contractors."""
    return service.list_contractors(skip=skip, limit=limit)


@router.get("/contractors/{contractor_id}", response_model=ContractorResponse)
def get_contractor(
    contractor_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ContractorResponse:
    """Get a contractor by ID."""
    return service.get_contractor(contractor_id)


@router.patch("/contractors/{contractor_id}", response_model=ContractorResponse)
def update_contractor(
    contractor_id: str,
    data: ContractorUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ContractorResponse:
    """Update a contractor record."""
    return service.update_contractor(contractor_id, data)


@router.delete("/contractors/{contractor_id}", status_code=204)
def delete_contractor(
    contractor_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete a contractor record."""
    service.delete_contractor(contractor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Procurement package endpoints (PR-CONSTR-043) ────────────────────────────


@router.post("/packages", response_model=ProcurementPackageResponse, status_code=201)
def create_procurement_package(
    data: ProcurementPackageCreate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProcurementPackageResponse:
    """Create a new procurement package within a construction scope."""
    return service.create_procurement_package(data)


@router.get(
    "/scopes/{scope_id}/packages",
    response_model=ProcurementPackageList,
)
def list_procurement_packages(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ProcurementPackageList:
    """List procurement packages for a construction scope."""
    return service.list_procurement_packages(scope_id=scope_id, skip=skip, limit=limit)


@router.get("/packages/{package_id}", response_model=ProcurementPackageResponse)
def get_procurement_package(
    package_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProcurementPackageResponse:
    """Get a procurement package by ID."""
    return service.get_procurement_package(package_id)


@router.patch("/packages/{package_id}", response_model=ProcurementPackageResponse)
def update_procurement_package(
    package_id: str,
    data: ProcurementPackageUpdate,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProcurementPackageResponse:
    """Update a procurement package."""
    return service.update_procurement_package(package_id, data)


@router.delete("/packages/{package_id}", status_code=204)
def delete_procurement_package(
    package_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> Response:
    """Delete a procurement package."""
    service.delete_procurement_package(package_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/packages/{package_id}/assign-contractor",
    response_model=ProcurementPackageResponse,
)
def assign_contractor_to_package(
    package_id: str,
    data: PackageAssignContractorRequest,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProcurementPackageResponse:
    """Assign a contractor to a procurement package."""
    return service.assign_contractor_to_package(package_id, data)


@router.post(
    "/packages/{package_id}/milestones/{milestone_id}",
    response_model=ProcurementPackageResponse,
    status_code=200,
)
def link_package_to_milestone(
    package_id: str,
    milestone_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProcurementPackageResponse:
    """Link a procurement package to a construction milestone."""
    return service.link_package_to_milestone(package_id, milestone_id)


@router.get(
    "/scopes/{scope_id}/procurement-overview",
    response_model=ProcurementOverviewResponse,
)
def get_scope_procurement_overview(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProcurementOverviewResponse:
    """Return procurement execution summary for a construction scope."""
    return service.get_scope_procurement_overview(scope_id)


# ── Risk Alert endpoints (PR-CONSTR-044) ─────────────────────────────────────


@router.get(
    "/scopes/{scope_id}/risk-alerts",
    response_model=ScopeRiskAlertListResponse,
)
def get_scope_risk_alerts(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ScopeRiskAlertListResponse:
    """Return construction execution risk alerts for a scope."""
    return service.get_scope_risk_alerts(scope_id)


@router.get(
    "/scopes/{scope_id}/procurement-risk",
    response_model=ProcurementRiskOverviewResponse,
)
def get_scope_procurement_risk(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProcurementRiskOverviewResponse:
    """Return procurement risk overview for a construction scope."""
    return service.get_scope_procurement_risk(scope_id)


@router.get(
    "/contractors/{contractor_id}/performance",
    response_model=ContractorPerformanceSummaryResponse,
)
def get_contractor_performance(
    contractor_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ContractorPerformanceSummaryResponse:
    """Return performance summary and risk alerts for a contractor."""
    return service.get_contractor_performance(contractor_id)


# ── Scorecard & Trend endpoints (PR-CONSTR-045) ───────────────────────────────


@router.get(
    "/contractors/{contractor_id}/scorecard",
    response_model=ContractorScorecardResponse,
)
def get_contractor_scorecard(
    contractor_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
    scope_id: Optional[str] = Query(default=None),
) -> ContractorScorecardResponse:
    """Return derived scorecard KPIs for a contractor."""
    return service.get_contractor_scorecard(contractor_id, scope_id=scope_id)


@router.get(
    "/contractors/{contractor_id}/trend",
    response_model=ContractorTrendResponse,
)
def get_contractor_trend(
    contractor_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
    scope_id: Optional[str] = Query(default=None),
) -> ContractorTrendResponse:
    """Return period-over-period trend analytics for a contractor."""
    return service.get_contractor_trend(contractor_id, scope_id=scope_id)


@router.get(
    "/scopes/{scope_id}/contractor-scorecards",
    response_model=ScopeContractorScorecardListResponse,
)
def list_scope_contractor_scorecards(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ScopeContractorScorecardListResponse:
    """Return scorecards for all contractors active in a construction scope."""
    return service.list_scope_contractor_scorecards(scope_id)


@router.get(
    "/scopes/{scope_id}/contractor-ranking",
    response_model=ScopeContractorRankingResponse,
)
def get_scope_contractor_ranking(
    scope_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ScopeContractorRankingResponse:
    """Return deterministic contractor ranking for a construction scope."""
    return service.get_scope_contractor_ranking(scope_id)


# ── Portfolio Risk Rollup (PR-CONSTR-050) ─────────────────────────────────────


@router.get(
    "/projects/{project_id}/risk",
    response_model=ProjectConstructionRiskResponse,
)
def get_project_construction_risk(
    project_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProjectConstructionRiskResponse:
    """Return project-level construction risk rollup aggregated from contractor scorecards."""
    return service.compute_project_construction_risk(project_id)


# ── Construction Executive Summary (PR-CONSTR-051) ────────────────────────────


@router.get(
    "/projects/{project_id}/summary",
    response_model=ProjectConstructionExecutiveSummaryResponse,
)
def get_project_construction_executive_summary(
    project_id: str,
    service: Annotated[ConstructionService, Depends(get_service)],
) -> ProjectConstructionExecutiveSummaryResponse:
    """Return a single executive-ready construction health summary for a project."""
    return service.compute_project_construction_executive_summary(project_id)
