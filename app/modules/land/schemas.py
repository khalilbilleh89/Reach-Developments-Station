"""
land.schemas

Pydantic request/response schemas for the Land Underwriting CRUD API.
"""

from datetime import datetime
from typing import List, Optional

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
    land_area_sqm: Optional[float] = Field(None, gt=0)
    frontage_m: Optional[float] = Field(None, gt=0)
    depth_m: Optional[float] = Field(None, gt=0)
    zoning_category: Optional[str] = Field(None, max_length=100)
    permitted_far: Optional[float] = Field(None, gt=0)
    max_height_m: Optional[float] = Field(None, gt=0)
    max_floors: Optional[int] = Field(None, ge=1)
    corner_plot: bool = False
    utilities_available: bool = False
    status: LandParcelStatus = LandParcelStatus.DRAFT


class LandParcelUpdate(BaseModel):
    parcel_name: Optional[str] = Field(None, min_length=1, max_length=255)
    country: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    land_area_sqm: Optional[float] = Field(None, gt=0)
    frontage_m: Optional[float] = Field(None, gt=0)
    depth_m: Optional[float] = Field(None, gt=0)
    zoning_category: Optional[str] = Field(None, max_length=100)
    permitted_far: Optional[float] = Field(None, gt=0)
    max_height_m: Optional[float] = Field(None, gt=0)
    max_floors: Optional[int] = Field(None, ge=1)
    corner_plot: Optional[bool] = None
    utilities_available: Optional[bool] = None
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
    land_area_sqm: Optional[float]
    frontage_m: Optional[float]
    depth_m: Optional[float]
    zoning_category: Optional[str]
    permitted_far: Optional[float]
    max_height_m: Optional[float]
    max_floors: Optional[int]
    corner_plot: bool
    utilities_available: bool
    status: LandParcelStatus
    created_at: datetime
    updated_at: datetime

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
    valuation_notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
