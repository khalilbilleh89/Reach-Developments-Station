"""
land.schemas

Pydantic request/response schemas for the Land Underwriting CRUD API.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.shared.enums.project import LandParcelStatus, LandScenarioType


# ---------------------------------------------------------------------------
# LandParcel schemas
# ---------------------------------------------------------------------------

class LandParcelCreate(BaseModel):
    project_id: Optional[str] = None
    parcel_name: str = Field(..., min_length=1, max_length=255)
    parcel_code: str = Field(..., min_length=1, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    # Identity & cadastral reference
    plot_number: Optional[str] = Field(None, max_length=100)
    cadastral_id: Optional[str] = Field(None, max_length=100)
    title_reference: Optional[str] = Field(None, max_length=255)
    location_link: Optional[str] = Field(None, max_length=1000)
    municipality: Optional[str] = Field(None, max_length=100)
    submarket: Optional[str] = Field(None, max_length=100)
    # Physical / dimensional attributes
    land_area_sqm: Optional[float] = Field(None, gt=0)
    frontage_m: Optional[float] = Field(None, gt=0)
    depth_m: Optional[float] = Field(None, gt=0)
    buildable_area_sqm: Optional[float] = Field(None, gt=0)
    sellable_area_sqm: Optional[float] = Field(None, gt=0)
    coverage_ratio: Optional[float] = Field(None, ge=0, le=1)
    density_ratio: Optional[float] = Field(None, ge=0)
    front_setback_m: Optional[float] = Field(None, ge=0)
    side_setback_m: Optional[float] = Field(None, ge=0)
    rear_setback_m: Optional[float] = Field(None, ge=0)
    zoning_category: Optional[str] = Field(None, max_length=100)
    permitted_far: Optional[float] = Field(None, gt=0)
    max_height_m: Optional[float] = Field(None, gt=0)
    max_floors: Optional[int] = Field(None, ge=1)
    corner_plot: bool = False
    utilities_available: bool = False
    access_notes: Optional[str] = None
    utilities_notes: Optional[str] = None
    # Acquisition economics
    acquisition_price: Optional[float] = Field(None, ge=0)
    transaction_cost: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=10)
    asking_price_per_sqm: Optional[float] = Field(None, ge=0)
    supported_price_per_sqm: Optional[float] = Field(None, ge=0)
    # Governance / provenance
    assumption_notes: Optional[str] = None
    source_notes: Optional[str] = None
    status: LandParcelStatus = LandParcelStatus.DRAFT


class LandParcelUpdate(BaseModel):
    parcel_name: Optional[str] = Field(None, min_length=1, max_length=255)
    country: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    # Identity & cadastral reference
    plot_number: Optional[str] = Field(None, max_length=100)
    cadastral_id: Optional[str] = Field(None, max_length=100)
    title_reference: Optional[str] = Field(None, max_length=255)
    location_link: Optional[str] = Field(None, max_length=1000)
    municipality: Optional[str] = Field(None, max_length=100)
    submarket: Optional[str] = Field(None, max_length=100)
    # Physical / dimensional attributes
    land_area_sqm: Optional[float] = Field(None, gt=0)
    frontage_m: Optional[float] = Field(None, gt=0)
    depth_m: Optional[float] = Field(None, gt=0)
    buildable_area_sqm: Optional[float] = Field(None, gt=0)
    sellable_area_sqm: Optional[float] = Field(None, gt=0)
    coverage_ratio: Optional[float] = Field(None, ge=0, le=1)
    density_ratio: Optional[float] = Field(None, ge=0)
    front_setback_m: Optional[float] = Field(None, ge=0)
    side_setback_m: Optional[float] = Field(None, ge=0)
    rear_setback_m: Optional[float] = Field(None, ge=0)
    zoning_category: Optional[str] = Field(None, max_length=100)
    permitted_far: Optional[float] = Field(None, gt=0)
    max_height_m: Optional[float] = Field(None, gt=0)
    max_floors: Optional[int] = Field(None, ge=1)
    corner_plot: Optional[bool] = None
    utilities_available: Optional[bool] = None
    access_notes: Optional[str] = None
    utilities_notes: Optional[str] = None
    # Acquisition economics
    acquisition_price: Optional[float] = Field(None, ge=0)
    transaction_cost: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=10)
    asking_price_per_sqm: Optional[float] = Field(None, ge=0)
    supported_price_per_sqm: Optional[float] = Field(None, ge=0)
    # Governance / provenance
    assumption_notes: Optional[str] = None
    source_notes: Optional[str] = None
    status: Optional[LandParcelStatus] = None


class LandParcelResponse(BaseModel):
    id: str
    project_id: Optional[str]
    parcel_name: str
    parcel_code: str
    country: Optional[str]
    city: Optional[str]
    district: Optional[str]
    address: Optional[str]
    # Identity & cadastral reference
    plot_number: Optional[str]
    cadastral_id: Optional[str]
    title_reference: Optional[str]
    location_link: Optional[str]
    municipality: Optional[str]
    submarket: Optional[str]
    # Physical / dimensional attributes
    land_area_sqm: Optional[float]
    frontage_m: Optional[float]
    depth_m: Optional[float]
    buildable_area_sqm: Optional[float]
    sellable_area_sqm: Optional[float]
    coverage_ratio: Optional[float]
    density_ratio: Optional[float]
    front_setback_m: Optional[float]
    side_setback_m: Optional[float]
    rear_setback_m: Optional[float]
    zoning_category: Optional[str]
    permitted_far: Optional[float]
    max_height_m: Optional[float]
    max_floors: Optional[int]
    corner_plot: bool
    utilities_available: bool
    access_notes: Optional[str]
    utilities_notes: Optional[str]
    # Acquisition economics
    acquisition_price: Optional[float]
    transaction_cost: Optional[float]
    currency: Optional[str]
    asking_price_per_sqm: Optional[float]
    supported_price_per_sqm: Optional[float]
    # Governance / provenance
    assumption_notes: Optional[str]
    source_notes: Optional[str]
    status: LandParcelStatus
    created_at: datetime
    updated_at: datetime
    # Computed land basis metrics (derived — never client-supplied)
    effective_land_basis: Optional[float] = None
    gross_land_price_per_sqm: Optional[float] = None
    effective_land_price_per_gross_sqm: Optional[float] = None
    effective_land_price_per_buildable_sqm: Optional[float] = None
    effective_land_price_per_sellable_sqm: Optional[float] = None
    supported_acquisition_price: Optional[float] = None
    residual_land_value: Optional[float] = None
    margin_impact: Optional[float] = None

    model_config = {"from_attributes": True}


class LandParcelList(BaseModel):
    items: List[LandParcelResponse]
    total: int


# ---------------------------------------------------------------------------
# LandAssumptions schemas
# ---------------------------------------------------------------------------

class LandAssumptionCreate(BaseModel):
    target_use: Optional[str] = Field(None, max_length=100)
    expected_sellable_ratio: Optional[float] = Field(None, gt=0, le=1)
    parking_ratio: Optional[float] = Field(None, ge=0, le=1)
    service_area_ratio: Optional[float] = Field(None, ge=0, le=1)
    notes: Optional[str] = None


class LandAssumptionUpdate(BaseModel):
    target_use: Optional[str] = Field(None, max_length=100)
    expected_sellable_ratio: Optional[float] = Field(None, gt=0, le=1)
    parking_ratio: Optional[float] = Field(None, ge=0, le=1)
    service_area_ratio: Optional[float] = Field(None, ge=0, le=1)
    notes: Optional[str] = None


class LandAssumptionResponse(BaseModel):
    id: str
    parcel_id: str
    target_use: Optional[str]
    expected_sellable_ratio: Optional[float]
    expected_buildable_area_sqm: Optional[float]
    expected_sellable_area_sqm: Optional[float]
    parking_ratio: Optional[float]
    service_area_ratio: Optional[float]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# LandValuation schemas
# ---------------------------------------------------------------------------

class LandValuationCreate(BaseModel):
    scenario_name: str = Field(..., min_length=1, max_length=255)
    scenario_type: LandScenarioType = LandScenarioType.BASE
    assumed_sale_price_per_sqm: Optional[float] = Field(None, gt=0)
    assumed_cost_per_sqm: Optional[float] = Field(None, gt=0)
    valuation_notes: Optional[str] = None


class LandValuationUpdate(BaseModel):
    scenario_name: Optional[str] = Field(None, min_length=1, max_length=255)
    scenario_type: Optional[LandScenarioType] = None
    assumed_sale_price_per_sqm: Optional[float] = Field(None, gt=0)
    assumed_cost_per_sqm: Optional[float] = Field(None, gt=0)
    valuation_notes: Optional[str] = None


class LandValuationResponse(BaseModel):
    id: str
    parcel_id: str
    scenario_name: str
    scenario_type: LandScenarioType
    assumed_sale_price_per_sqm: Optional[float]
    assumed_cost_per_sqm: Optional[float]
    expected_gdv: Optional[float]
    expected_cost: Optional[float]
    residual_land_value: Optional[float]
    land_value_per_sqm: Optional[float]
    max_land_bid: Optional[float]
    residual_margin: Optional[float]
    valuation_date: Optional[date]
    valuation_inputs: Optional[Dict[str, Any]]
    valuation_notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Zoning Regulation Engine schemas
# ---------------------------------------------------------------------------

class ZoningEvaluateRequest(BaseModel):
    """Request payload for POST /land/zoning/evaluate."""

    land_area: float = Field(..., gt=0, description="Total parcel area in sqm")
    far: float = Field(..., gt=0, description="Floor Area Ratio (e.g. 3.5)")
    coverage_ratio: float = Field(..., gt=0, le=1, description="Site coverage fraction (0–1)")
    max_height_m: float = Field(..., gt=0, description="Maximum permitted building height in metres")
    floor_height_m: float = Field(..., gt=0, description="Storey height in metres")
    parking_ratio: float = Field(..., ge=0, description="Parking spaces per unit")
    setback_front: float = Field(default=0.0, ge=0, description="Front setback in metres")
    setback_side: float = Field(default=0.0, ge=0, description="Side setback in metres")
    setback_rear: float = Field(default=0.0, ge=0, description="Rear setback in metres")
    avg_unit_size_sqm: Optional[float] = Field(
        default=None, gt=0, description="Average unit size in sqm (required for unit-capacity output)"
    )


class ZoningResultResponse(BaseModel):
    """Response payload for POST /land/zoning/evaluate."""

    max_buildable_area: float
    max_footprint_area: float
    max_floors: int
    setback_adjusted_area: float
    effective_footprint: float
    effective_buildable_area: float
    estimated_unit_capacity: Optional[int]
    parking_required: int


# ---------------------------------------------------------------------------
# LandValuationEngine schemas — engine-driven residual valuation
# ---------------------------------------------------------------------------

class LandValuationEngineRequest(BaseModel):
    scenario_name: str = Field(..., min_length=1, max_length=255)
    scenario_type: LandScenarioType = LandScenarioType.BASE
    gdv: float = Field(..., gt=0)
    construction_cost: float = Field(..., gt=0)
    soft_cost_percentage: float = Field(..., ge=0, le=1)
    developer_margin_target: float = Field(..., ge=0, le=1)
    sellable_area_sqm: float = Field(..., gt=0)
    valuation_notes: Optional[str] = None
