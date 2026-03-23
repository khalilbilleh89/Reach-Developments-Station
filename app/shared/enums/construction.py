"""Construction-related enumerations."""

from enum import Enum


class ConstructionStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"


class EngineeringStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    ON_HOLD = "on_hold"


class ContractorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"


class ContractorType(str, Enum):
    MAIN_CONTRACTOR = "main_contractor"
    SUBCONTRACTOR = "subcontractor"
    CONSULTANT = "consultant"
    SPECIALIST = "specialist"
    SUPPLIER = "supplier"


class ProcurementPackageType(str, Enum):
    CIVIL = "civil"
    STRUCTURAL = "structural"
    MEP = "mep"
    FINISHING = "finishing"
    EXTERNAL_WORKS = "external_works"
    FIT_OUT = "fit_out"
    SPECIALIST = "specialist"
    OTHER = "other"


class ProcurementPackageStatus(str, Enum):
    DRAFT = "draft"
    TENDERING = "tendering"
    EVALUATION = "evaluation"
    AWARDED = "awarded"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
