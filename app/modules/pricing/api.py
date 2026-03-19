"""
pricing.api

REST API router for the Pricing Engine module.
Endpoints under /pricing.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.pricing.schemas import (
    PricingReadinessResponse,
    ProjectPriceSummaryResponse,
    UnitPricingAttributesCreate,
    UnitPricingAttributesResponse,
    UnitPricingDetailResponse,
    UnitPriceResponse,
)
from app.modules.pricing.service import PricingService

router = APIRouter(prefix="/pricing", tags=["Pricing"])


def get_service(db: Session = Depends(get_db)) -> PricingService:
    return PricingService(db)


# ---------------------------------------------------------------------------
# Pricing attributes endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/unit/{unit_id}/attributes",
    response_model=UnitPricingAttributesResponse,
    status_code=201,
)
def set_unit_pricing_attributes(
    unit_id: str,
    data: UnitPricingAttributesCreate,
    service: Annotated[PricingService, Depends(get_service)],
) -> UnitPricingAttributesResponse:
    """Create or replace pricing attributes for a unit."""
    return service.set_pricing_attributes(unit_id, data)


@router.get(
    "/unit/{unit_id}/attributes",
    response_model=UnitPricingAttributesResponse,
)
def get_unit_pricing_attributes(
    unit_id: str,
    service: Annotated[PricingService, Depends(get_service)],
) -> UnitPricingAttributesResponse:
    """Get the pricing attributes for a unit."""
    return service.get_pricing_attributes(unit_id)


@router.get(
    "/unit/{unit_id}/readiness",
    response_model=PricingReadinessResponse,
)
def get_unit_pricing_readiness(
    unit_id: str,
    service: Annotated[PricingService, Depends(get_service)],
) -> PricingReadinessResponse:
    """Return explicit pricing readiness for a unit.

    Reports whether all required numerical pricing engine inputs are present,
    and lists any missing fields if they are not.  Use this endpoint on the
    pricing inspection page instead of relying on the 422 response from the
    price calculation endpoint — that approach does not distinguish between
    partially configured units and completely unconfigured units, and it
    cannot report which specific fields are still missing.
    """
    return service.get_pricing_readiness(unit_id)


@router.get(
    "/unit/{unit_id}/detail",
    response_model=UnitPricingDetailResponse,
)
def get_unit_pricing_detail(
    unit_id: str,
    service: Annotated[PricingService, Depends(get_service)],
) -> UnitPricingDetailResponse:
    """Return the assembled pricing detail for a unit.

    Combines all pricing layers into one coherent response:
      - engine_inputs: stored numerical pricing engine inputs.
      - pricing_readiness: current readiness state (missing fields, etc.).
      - pricing_record: stored commercial pricing record (approved price, status, etc.).

    Qualitative attributes (view type, corner unit, etc.) are managed by the
    pricing_attributes module and are returned by GET /units/{id}/pricing-attributes.
    """
    return service.get_unit_pricing_detail(unit_id)


# ---------------------------------------------------------------------------
# Price calculation endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/unit/{unit_id}",
    response_model=UnitPriceResponse,
)
def get_unit_price(
    unit_id: str,
    service: Annotated[PricingService, Depends(get_service)],
) -> UnitPriceResponse:
    """Retrieve the calculated price for a unit using stored attributes."""
    return service.calculate_unit_price(unit_id)


@router.post(
    "/unit/{unit_id}/calculate",
    response_model=UnitPriceResponse,
)
def calculate_unit_price(
    unit_id: str,
    service: Annotated[PricingService, Depends(get_service)],
) -> UnitPriceResponse:
    """Execute the pricing calculation for a unit and return the result."""
    return service.calculate_unit_price(unit_id)


@router.get(
    "/project/{project_id}",
    response_model=ProjectPriceSummaryResponse,
)
def get_project_price_summary(
    project_id: str,
    service: Annotated[PricingService, Depends(get_service)],
) -> ProjectPriceSummaryResponse:
    """Get a pricing summary for all priced units in a project."""
    return service.calculate_project_price_summary(project_id)
