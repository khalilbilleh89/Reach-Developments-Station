"""Construction cost record enumerations."""

from enum import Enum


class CostCategory(str, Enum):
    HARD_COST = "hard_cost"
    SOFT_COST = "soft_cost"
    PRELIMINARIES = "preliminaries"
    INFRASTRUCTURE = "infrastructure"
    CONTINGENCY = "contingency"
    CONSULTANT_FEE = "consultant_fee"
    TENDER_ADJUSTMENT = "tender_adjustment"
    VARIATION = "variation"


class CostSource(str, Enum):
    ESTIMATE = "estimate"
    TENDER = "tender"
    CONTRACT = "contract"
    VARIATION = "variation"
    ACTUAL = "actual"


class CostStage(str, Enum):
    PRE_DESIGN = "pre_design"
    DESIGN = "design"
    TENDER = "tender"
    CONSTRUCTION = "construction"
    COMPLETION = "completion"
    POST_COMPLETION = "post_completion"
