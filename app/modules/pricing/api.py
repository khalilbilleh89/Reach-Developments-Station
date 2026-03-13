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
    ProjectPriceSummaryResponse,
    UnitPricingAttributesCreate,
    UnitPricingAttributesResponse,
    UnitPriceResponse,
)
from app.modules.pricing.service import PricingService

router = APIRouter(prefix="/pricing", tags=["pricing"])


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
