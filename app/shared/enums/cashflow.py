"""Cashflow forecasting enumerations."""

from enum import Enum


class CashflowForecastBasis(str, Enum):
    SCHEDULED_COLLECTIONS = "scheduled_collections"
    ACTUAL_PLUS_SCHEDULED = "actual_plus_scheduled"
    BLENDED = "blended"


class CashflowForecastStatus(str, Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    ARCHIVED = "archived"


class CashflowPeriodType(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
