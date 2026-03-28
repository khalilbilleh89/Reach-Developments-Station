"""Tender comparison and cost variance enumerations."""

from enum import Enum


class ComparisonStage(str, Enum):
    BASELINE_VS_TENDER = "baseline_vs_tender"
    TENDER_VS_AWARD = "tender_vs_award"
    AWARD_VS_VARIATION = "award_vs_variation"
    BASELINE_VS_AWARD = "baseline_vs_award"
    BASELINE_VS_COMPLETION = "baseline_vs_completion"


class VarianceReason(str, Enum):
    QUANTITY_CHANGE = "quantity_change"
    UNIT_RATE_CHANGE = "unit_rate_change"
    SCOPE_CHANGE = "scope_change"
    VE_SAVING = "ve_saving"
    CONTINGENCY_SHIFT = "contingency_shift"
    OTHER = "other"
