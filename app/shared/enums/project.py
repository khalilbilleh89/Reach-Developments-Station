"""Project-related enumerations."""

from enum import Enum


class ProjectStatus(str, Enum):
    PIPELINE = "pipeline"
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class PhaseStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"


class BuildingStatus(str, Enum):
    PLANNED = "planned"
    UNDER_CONSTRUCTION = "under_construction"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class FloorStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class UnitStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    UNDER_CONTRACT = "under_contract"
    REGISTERED = "registered"


class UnitType(str, Enum):
    STUDIO = "studio"
    ONE_BEDROOM = "one_bedroom"
    TWO_BEDROOM = "two_bedroom"
    THREE_BEDROOM = "three_bedroom"
    FOUR_BEDROOM = "four_bedroom"
    VILLA = "villa"
    TOWNHOUSE = "townhouse"
    RETAIL = "retail"
    OFFICE = "office"
    PENTHOUSE = "penthouse"


class LandParcelStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    ARCHIVED = "archived"


class LandScenarioType(str, Enum):
    BASE = "base"
    UPSIDE = "upside"
    DOWNSIDE = "downside"
    INVESTOR = "investor"
