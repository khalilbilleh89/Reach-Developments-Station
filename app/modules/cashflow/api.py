"""
cashflow.api

REST API router for the Cashflow Forecasting module.

Router prefix: /cashflow
Full prefix:   /api/v1/cashflow/...

Endpoints
---------
  POST  /api/v1/cashflow/forecasts
  GET   /api/v1/cashflow/forecasts/{forecast_id}
  GET   /api/v1/cashflow/forecasts/{forecast_id}/periods
  GET   /api/v1/cashflow/projects/{project_id}/forecasts
  GET   /api/v1/cashflow/projects/{project_id}/cashflow-summary
"""

from typing import Annotated, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.cashflow.schemas import (
    CashflowForecastCreate,
    CashflowForecastListResponse,
    CashflowForecastPeriodResponse,
    CashflowForecastResponse,
    CashflowForecastSummaryResponse,
)
from app.modules.cashflow.service import CashflowService

router = APIRouter(prefix="/cashflow", tags=["cashflow"])


def get_service(db: Session = Depends(get_db)) -> CashflowService:
    return CashflowService(db)


# ---------------------------------------------------------------------------
# Project-scoped views (declared before /{forecast_id} to avoid path conflicts)
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/forecasts",
    response_model=CashflowForecastListResponse,
)
def list_project_forecasts(
    project_id: str,
    service: Annotated[CashflowService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> CashflowForecastListResponse:
    """List all cashflow forecasts for a project."""
    return service.list_forecasts_by_project(project_id, skip=skip, limit=limit)


@router.get(
    "/projects/{project_id}/cashflow-summary",
    response_model=CashflowForecastSummaryResponse,
)
def get_project_cashflow_summary(
    project_id: str,
    service: Annotated[CashflowService, Depends(get_service)],
) -> CashflowForecastSummaryResponse:
    """Return project-level cashflow summary based on the latest forecast."""
    return service.get_project_cashflow_summary(project_id)


# ---------------------------------------------------------------------------
# Forecast CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/forecasts",
    response_model=CashflowForecastResponse,
    status_code=201,
)
def create_forecast(
    data: CashflowForecastCreate,
    service: Annotated[CashflowService, Depends(get_service)],
) -> CashflowForecastResponse:
    """Generate a new cashflow forecast for a project."""
    return service.create_forecast(data)


@router.get(
    "/forecasts/{forecast_id}",
    response_model=CashflowForecastResponse,
)
def get_forecast(
    forecast_id: str,
    service: Annotated[CashflowService, Depends(get_service)],
) -> CashflowForecastResponse:
    """Retrieve a cashflow forecast by ID."""
    return service.get_forecast(forecast_id)


@router.get(
    "/forecasts/{forecast_id}/periods",
    response_model=List[CashflowForecastPeriodResponse],
)
def list_forecast_periods(
    forecast_id: str,
    service: Annotated[CashflowService, Depends(get_service)],
) -> List[CashflowForecastPeriodResponse]:
    """List all time-bucket periods for a forecast (ordered by sequence)."""
    return service.list_forecast_periods(forecast_id)
