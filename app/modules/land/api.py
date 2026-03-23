"""
land.api

CRUD API router for the Land Underwriting domain.
Endpoints for LandParcel, LandAssumptions, and LandValuation.
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.land.schemas import (
    LandAssumptionCreate,
    LandAssumptionResponse,
    LandParcelCreate,
    LandParcelList,
    LandParcelResponse,
    LandParcelUpdate,
    LandValuationCreate,
    LandValuationEngineRequest,
    LandValuationResponse,
    ZoningEvaluateRequest,
    ZoningResultResponse,
)
from app.modules.land.service import LandService
from app.modules.land.zoning_service import ZoningService

router = APIRouter(prefix="/land", tags=["land"], dependencies=[Depends(get_current_user_payload)])


def get_service(db: Session = Depends(get_db)) -> LandService:
    return LandService(db)


# ---------------------------------------------------------------------------
# Parcel endpoints
# ---------------------------------------------------------------------------

@router.post("/parcels", response_model=LandParcelResponse, status_code=201)
def create_parcel(
    data: LandParcelCreate,
    service: Annotated[LandService, Depends(get_service)],
) -> LandParcelResponse:
    """Create a new land parcel."""
    return service.create_parcel(data)


@router.get("/parcels", response_model=LandParcelList)
def list_parcels(
    service: Annotated[LandService, Depends(get_service)],
    project_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> LandParcelList:
    """List land parcels, optionally filtered by project."""
    return service.list_parcels(project_id=project_id, skip=skip, limit=limit)


@router.get("/parcels/{parcel_id}", response_model=LandParcelResponse)
def get_parcel(
    parcel_id: str,
    service: Annotated[LandService, Depends(get_service)],
) -> LandParcelResponse:
    """Get a land parcel by ID."""
    return service.get_parcel(parcel_id)


@router.patch("/parcels/{parcel_id}", response_model=LandParcelResponse)
def update_parcel(
    parcel_id: str,
    data: LandParcelUpdate,
    service: Annotated[LandService, Depends(get_service)],
) -> LandParcelResponse:
    """Update a land parcel."""
    return service.update_parcel(parcel_id, data)


@router.delete("/parcels/{parcel_id}", status_code=204, response_class=Response)
def delete_parcel(
    parcel_id: str,
    service: Annotated[LandService, Depends(get_service)],
) -> Response:
    """Delete a land parcel."""
    service.delete_parcel(parcel_id)
    return Response(status_code=204)


@router.post("/parcels/{parcel_id}/assign-project/{project_id}", response_model=LandParcelResponse)
def assign_parcel_to_project(
    parcel_id: str,
    project_id: str,
    service: Annotated[LandService, Depends(get_service)],
) -> LandParcelResponse:
    """Assign a land parcel to a project."""
    return service.assign_to_project(parcel_id, project_id)


# ---------------------------------------------------------------------------
# Assumptions endpoints
# ---------------------------------------------------------------------------

@router.post("/parcels/{parcel_id}/assumptions", response_model=LandAssumptionResponse, status_code=201)
def create_assumptions(
    parcel_id: str,
    data: LandAssumptionCreate,
    service: Annotated[LandService, Depends(get_service)],
) -> LandAssumptionResponse:
    """Add development assumptions to a land parcel."""
    return service.create_assumptions(parcel_id, data)


@router.get("/parcels/{parcel_id}/assumptions", response_model=List[LandAssumptionResponse])
def get_assumptions(
    parcel_id: str,
    service: Annotated[LandService, Depends(get_service)],
) -> List[LandAssumptionResponse]:
    """Get all development assumptions for a land parcel."""
    return service.get_assumptions(parcel_id)


# ---------------------------------------------------------------------------
# Valuation endpoints
# ---------------------------------------------------------------------------

@router.post("/parcels/{parcel_id}/valuations", response_model=LandValuationResponse, status_code=201)
def create_valuation(
    parcel_id: str,
    data: LandValuationCreate,
    service: Annotated[LandService, Depends(get_service)],
) -> LandValuationResponse:
    """Create a valuation scenario for a land parcel."""
    return service.create_valuation(parcel_id, data)


@router.get("/parcels/{parcel_id}/valuations", response_model=List[LandValuationResponse])
def list_valuations(
    parcel_id: str,
    service: Annotated[LandService, Depends(get_service)],
) -> List[LandValuationResponse]:
    """List all valuation scenarios for a land parcel."""
    return service.list_valuations(parcel_id)


@router.post("/parcels/{parcel_id}/valuation", response_model=LandValuationResponse, status_code=201)
def run_valuation_engine(
    parcel_id: str,
    data: LandValuationEngineRequest,
    service: Annotated[LandService, Depends(get_service)],
) -> LandValuationResponse:
    """Run the land valuation engine for a parcel and persist the result.

    Computes residual land value using:
      land_value = GDV − (construction_cost + soft_costs) − target_profit
    """
    return service.calculate_land_valuation(parcel_id, data)


# ---------------------------------------------------------------------------
# Zoning evaluation endpoint
# ---------------------------------------------------------------------------

@router.post("/zoning/evaluate", response_model=ZoningResultResponse)
def evaluate_zoning(
    data: ZoningEvaluateRequest,
) -> ZoningResultResponse:
    """Evaluate zoning capacity from parcel and regulation parameters.

    Accepts zoning inputs (FAR, coverage ratio, height, setbacks, parking ratio)
    and returns derived development limits including maximum buildable area,
    effective footprint, floor count, and parking requirements.
    """
    return ZoningService().evaluate(data)
