"""Sales-related enumerations."""

from enum import Enum


class ReservationStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    CONVERTED = "converted"
    CANCELLED = "cancelled"


class ContractStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ContractPaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
