"""
cashflow.schemas

Pydantic request/response schemas for the Cashflow Forecasting module.

Schema families
---------------
  Forecast creation  — CashflowForecastCreate
  Forecast response  — CashflowForecastResponse / CashflowForecastListResponse
  Period response    — CashflowForecastPeriodResponse
  Summary response   — CashflowForecastSummaryResponse
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.core.constants.currency import DEFAULT_CURRENCY
from app.shared.enums.cashflow import (
    CashflowForecastBasis,
    CashflowForecastStatus,
    CashflowPeriodType,
)


# ---------------------------------------------------------------------------
# Forecast schemas
# ---------------------------------------------------------------------------


class CashflowForecastCreate(BaseModel):
    project_id: str
    forecast_name: str = Field(..., max_length=200)
    start_date: date
    end_date: date
    period_type: CashflowPeriodType = CashflowPeriodType.MONTHLY
    forecast_basis: CashflowForecastBasis = CashflowForecastBasis.ACTUAL_PLUS_SCHEDULED
    opening_balance: float = Field(default=0.0, ge=0)
    collection_factor: Optional[float] = Field(default=None, gt=0, le=1)
    expected_outflows_schedule: Optional[Dict[str, float]] = Field(
        default=None,
        description=(
            "Optional map of period-start ISO date → expected outflow amount. "
            "Periods not listed default to zero outflows."
        ),
    )
    generated_by: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def dates_valid(self) -> "CashflowForecastCreate":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

    @model_validator(mode="after")
    def blended_requires_factor(self) -> "CashflowForecastCreate":
        if (
            self.forecast_basis == CashflowForecastBasis.BLENDED
            and self.collection_factor is None
        ):
            raise ValueError(
                "collection_factor is required when forecast_basis is 'blended'"
            )
        return self


class CashflowForecastResponse(BaseModel):
    id: str
    project_id: str
    forecast_name: str
    forecast_basis: CashflowForecastBasis
    start_date: date
    end_date: date
    period_type: CashflowPeriodType
    status: CashflowForecastStatus
    opening_balance: float
    collection_factor: Optional[float]
    assumptions_json: Optional[str]
    generated_at: Optional[datetime]
    generated_by: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    currency: Optional[str] = Field(
        None,
        description=(
            "ISO 4217 currency code for all monetary values in this forecast. "
            "Sourced from the project base_currency and populated by the service layer."
        ),
    )

    model_config = {"from_attributes": True}


class CashflowForecastListResponse(BaseModel):
    total: int
    items: List[CashflowForecastResponse]


# ---------------------------------------------------------------------------
# Period schemas
# ---------------------------------------------------------------------------


class CashflowForecastPeriodResponse(BaseModel):
    id: str
    cashflow_forecast_id: str
    sequence: int
    period_start: date
    period_end: date
    opening_balance: float
    expected_inflows: float
    actual_inflows: float
    expected_outflows: float
    net_cashflow: float
    closing_balance: float
    receivables_due: float
    receivables_overdue: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    currency: str = Field(
        DEFAULT_CURRENCY,
        description=(
            "ISO 4217 currency code for all monetary values in this period row. "
            "Inherited from the forecast's project base_currency."
        ),
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Summary schema
# ---------------------------------------------------------------------------


class CashflowForecastSummaryResponse(BaseModel):
    project_id: str
    total_forecasts: int
    latest_forecast_id: Optional[str]
    latest_forecast_name: Optional[str]
    latest_generated_at: Optional[datetime]
    total_expected_inflows: float
    total_actual_inflows: float
    total_expected_outflows: float
    total_net_cashflow: float
    closing_balance: float
    currency: Optional[str] = Field(
        None,
        description=(
            "ISO 4217 currency code for all monetary values in this summary. "
            "Sourced from the project base_currency and populated by the service layer."
        ),
    )
