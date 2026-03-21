"""
finance.schemas

Pydantic response schemas for the finance summary API.

All fields represent aggregated financial state computed at query time;
no raw financial tables are exposed.
"""

from typing import List

from pydantic import BaseModel, Field


class ProjectFinanceSummaryResponse(BaseModel):
    """Aggregated financial summary for a single project."""

    project_id: str

    # Unit inventory counts
    total_units: int = Field(..., ge=0)
    units_sold: int = Field(..., ge=0)
    units_available: int = Field(..., ge=0)

    # Revenue aggregates (monetary amounts in the project currency)
    total_contract_value: float = Field(..., ge=0)
    total_collected: float = Field(..., ge=0)
    total_receivable: float = Field(..., ge=0)

    # Ratio metrics
    collection_ratio: float = Field(..., ge=0, le=1)

    # Pricing metrics
    average_unit_price: float = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Revenue recognition schemas
# ---------------------------------------------------------------------------


class RevenueRecognitionResponse(BaseModel):
    """Revenue recognition breakdown for a single contract.

    recognized_revenue + deferred_revenue always equals contract_total.
    """

    contract_id: str
    contract_total: float = Field(..., ge=0)
    recognized_revenue: float = Field(..., ge=0)
    deferred_revenue: float = Field(..., ge=0)
    recognition_percentage: float = Field(..., ge=0, le=100)


class ProjectRevenueSummaryResponse(BaseModel):
    """Aggregated revenue recognition summary for a project."""

    project_id: str
    total_contract_value: float = Field(..., ge=0)
    total_recognized_revenue: float = Field(..., ge=0)
    total_deferred_revenue: float = Field(..., ge=0)
    overall_recognition_percentage: float = Field(..., ge=0, le=100)
    contract_count: int = Field(..., ge=0)
    contracts: List[RevenueRecognitionResponse] = Field(default_factory=list)


class PortfolioRevenueOverviewResponse(BaseModel):
    """Portfolio-wide revenue recognition overview across all projects."""

    total_contract_value: float = Field(..., ge=0)
    total_recognized_revenue: float = Field(..., ge=0)
    total_deferred_revenue: float = Field(..., ge=0)
    overall_recognition_percentage: float = Field(..., ge=0, le=100)
    project_count: int = Field(..., ge=0)
    contract_count: int = Field(..., ge=0)
