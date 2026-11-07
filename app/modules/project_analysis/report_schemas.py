"""Chart-ready management report; values and geometry are server derived."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.modules.project_analysis.schemas import Context


class Point(BaseModel):
    label: str
    value: Decimal | None
    scale_percentage: Decimal = Decimal(0)
    share_percentage: Decimal | None = None


class Chart(BaseModel):
    key: str
    title: str
    category: str
    kind: Literal["bars", "columns", "donut"] = "bars"
    unit: str = "units"
    points: list[Point]
    insight: str
    source: str
    note: str | None = None


class Metric(BaseModel):
    label: str
    value: Decimal | None
    unit: str
    note: str


class AnalyticsReport(BaseModel):
    project_name: str
    generated_at: datetime
    context: Context
    threshold: Decimal
    currency: str
    metrics: list[Metric]
    charts: list[Chart]
    notices: list[str]
