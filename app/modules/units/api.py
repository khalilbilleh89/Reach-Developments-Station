"""
units.api

CRUD API router for the Unit entity.

Provides two route groups:
  /api/v1/floors/{floor_id}/units           — floor-scoped unit listing and creation
  /api/v1/units                             — flat list with optional ?floor_id= filter
  /api/v1/units/{unit_id}                   — individual unit operations (get, update, delete)
  /api/v1/units/{unit_id}/pricing           — per-unit formal pricing record (get, put)
  /api/v1/units/{unit_id}/pricing-attributes — per-unit qualitative pricing attributes (get, put)
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.pricing.schemas import UnitPricingCreate, UnitPricingResponse
from app.modules.pricing.service import UnitPricingService
from app.modules.pricing_attributes.schemas import (
    UnitQualitativeAttributesCreate,
    UnitQualitativeAttributesResponse,
)
from app.modules.pricing_attributes.service import UnitPricingAttributesService
from app.modules.units.schemas import (
    UnitCreate,
    UnitCreateForFloor,
    UnitDynamicAttributesSaveRequest,
    UnitDynamicAttributeValueResponse,
    UnitList,
    UnitResponse,
    UnitUpdate,
)
from app.modules.units.service import UnitDynamicAttributeService, UnitService

router = APIRouter(tags=["units"])


def get_service(db: Session = Depends(get_db)) -> UnitService:
    return UnitService(db)


# ── Floor-scoped endpoints ────────────────────────────────────────────────────


@router.get("/floors/{floor_id}/units", response_model=UnitList)
def list_units_by_floor(
    floor_id: str,
    service: Annotated[UnitService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> UnitList:
    """List all units for a specific floor."""
    return service.list_units(floor_id=floor_id, skip=skip, limit=limit)


@router.post("/floors/{floor_id}/units", response_model=UnitResponse, status_code=201)
def create_unit_for_floor(
    floor_id: str,
    data: UnitCreateForFloor,
    service: Annotated[UnitService, Depends(get_service)],
) -> UnitResponse:
    """Create a new unit within a specific floor."""
    full_data = UnitCreate(**data.model_dump(), floor_id=floor_id)
    return service.create_unit(full_data)


# ── Flat unit endpoints ───────────────────────────────────────────────────────


@router.post("/units", response_model=UnitResponse, status_code=201)
def create_unit(
    data: UnitCreate,
    service: Annotated[UnitService, Depends(get_service)],
) -> UnitResponse:
    """Create a new unit."""
    return service.create_unit(data)


@router.get("/units", response_model=UnitList)
def list_units(
    service: Annotated[UnitService, Depends(get_service)],
    floor_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> UnitList:
    """List units, optionally filtered by floor."""
    return service.list_units(floor_id=floor_id, skip=skip, limit=limit)


@router.get("/units/{unit_id}", response_model=UnitResponse)
def get_unit(
    unit_id: str,
    service: Annotated[UnitService, Depends(get_service)],
) -> UnitResponse:
    """Get a unit by ID."""
    return service.get_unit(unit_id)


@router.patch("/units/{unit_id}", response_model=UnitResponse)
def update_unit(
    unit_id: str,
    data: UnitUpdate,
    service: Annotated[UnitService, Depends(get_service)],
) -> UnitResponse:
    """Update a unit."""
    return service.update_unit(unit_id, data)


@router.delete("/units/{unit_id}", status_code=204)
def delete_unit(
    unit_id: str,
    service: Annotated[UnitService, Depends(get_service)],
) -> Response:
    """Delete a unit by ID."""
    service.delete_unit(unit_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Per-unit pricing record endpoints ─────────────────────────────────────────


def get_pricing_service(db: Session = Depends(get_db)) -> UnitPricingService:
    return UnitPricingService(db)


@router.get(
    "/units/{unit_id}/pricing",
    response_model=UnitPricingResponse,
    tags=["unit-pricing"],
)
def get_unit_pricing(
    unit_id: str,
    service: Annotated[UnitPricingService, Depends(get_pricing_service)],
) -> UnitPricingResponse:
    """Get the formal pricing record for a unit.

    Returns 404 if the unit does not exist or has no pricing record yet.
    """
    return service.get_unit_pricing(unit_id)


@router.put(
    "/units/{unit_id}/pricing",
    response_model=UnitPricingResponse,
    tags=["unit-pricing"],
)
def save_unit_pricing(
    unit_id: str,
    data: UnitPricingCreate,
    service: Annotated[UnitPricingService, Depends(get_pricing_service)],
) -> UnitPricingResponse:
    """Create or update the formal pricing record for a unit.

    Computes final_price = base_price + manual_adjustment server-side.
    Rejects the request if the resulting final_price would be negative.
    """
    return service.save_unit_pricing(unit_id, data)


# ── Per-unit qualitative pricing attributes endpoints ─────────────────────────


def get_pricing_attributes_service(
    db: Session = Depends(get_db),
) -> UnitPricingAttributesService:
    return UnitPricingAttributesService(db)


@router.get(
    "/units/{unit_id}/pricing-attributes",
    response_model=UnitQualitativeAttributesResponse,
    tags=["unit-pricing-attributes"],
)
def get_unit_pricing_attributes(
    unit_id: str,
    service: Annotated[UnitPricingAttributesService, Depends(get_pricing_attributes_service)],
) -> UnitQualitativeAttributesResponse:
    """Get the qualitative pricing attributes for a unit.

    Returns 404 if the unit does not exist or has no attributes record yet.
    """
    return service.get_attributes(unit_id)


@router.put(
    "/units/{unit_id}/pricing-attributes",
    response_model=UnitQualitativeAttributesResponse,
    tags=["unit-pricing-attributes"],
)
def save_unit_pricing_attributes(
    unit_id: str,
    data: UnitQualitativeAttributesCreate,
    response: Response,
    service: Annotated[UnitPricingAttributesService, Depends(get_pricing_attributes_service)],
) -> UnitQualitativeAttributesResponse:
    """Create or update the qualitative pricing attributes for a unit.

    Returns 201 when a new attributes record is created, 200 when updated.
    """
    result, created = service.save_attributes(unit_id, data)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return result


# ── Per-unit dynamic attribute value endpoints ────────────────────────────────


def get_dynamic_attribute_service(
    db: Session = Depends(get_db),
) -> UnitDynamicAttributeService:
    return UnitDynamicAttributeService(db)


@router.get(
    "/units/{unit_id}/dynamic-attributes",
    response_model=list[UnitDynamicAttributeValueResponse],
    tags=["unit-dynamic-attributes"],
)
def list_unit_dynamic_attributes(
    unit_id: str,
    service: Annotated[UnitDynamicAttributeService, Depends(get_dynamic_attribute_service)],
) -> list[UnitDynamicAttributeValueResponse]:
    """List all project-defined dynamic attribute selections for a unit.

    Returns an empty list when the unit has no dynamic attribute values set yet.
    Returns 404 if the unit does not exist.
    """
    return service.list_dynamic_attributes(unit_id)


@router.put(
    "/units/{unit_id}/dynamic-attributes",
    response_model=list[UnitDynamicAttributeValueResponse],
    tags=["unit-dynamic-attributes"],
)
def save_unit_dynamic_attributes(
    unit_id: str,
    data: UnitDynamicAttributesSaveRequest,
    service: Annotated[UnitDynamicAttributeService, Depends(get_dynamic_attribute_service)],
) -> list[UnitDynamicAttributeValueResponse]:
    """Create or update project-defined dynamic attribute selections for a unit.

    Each item in ``attributes`` must reference:
      - a definition that belongs to the same project as the unit
      - an option that belongs to that definition

    Saving a new option for an existing definition replaces the previous selection.
    Returns 404 on unknown unit, definition, or option.
    Returns 422 when project-scope or definition-option integrity is violated.
    """
    return service.save_dynamic_attributes(unit_id, data)


# ── Project-scoped bulk pricing endpoints ─────────────────────────────────────


@router.get(
    "/projects/{project_id}/unit-pricing",
    response_model=dict[str, UnitPricingResponse],
    tags=["unit-pricing"],
)
def get_project_unit_pricing(
    project_id: str,
    service: Annotated[UnitPricingService, Depends(get_pricing_service)],
) -> dict[str, UnitPricingResponse]:
    """Get all formal pricing records for units in a project, keyed by unit_id.

    Returns an empty map when no units in the project have pricing records.
    """
    return service.get_project_pricing(project_id)


@router.get(
    "/projects/{project_id}/unit-pricing-attributes",
    response_model=dict[str, UnitQualitativeAttributesResponse],
    tags=["unit-pricing-attributes"],
)
def get_project_unit_pricing_attributes(
    project_id: str,
    service: Annotated[UnitPricingAttributesService, Depends(get_pricing_attributes_service)],
) -> dict[str, UnitQualitativeAttributesResponse]:
    """Get all qualitative pricing attributes for units in a project, keyed by unit_id.

    Returns an empty map when no units in the project have attributes set.
    """
    return service.get_project_pricing_attributes(project_id)
