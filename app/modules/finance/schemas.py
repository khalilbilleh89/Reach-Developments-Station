"""
finance.schemas

Pydantic response schemas for the finance summary API.

All fields represent aggregated financial state computed at query time;
no raw financial tables are exposed.
"""

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
