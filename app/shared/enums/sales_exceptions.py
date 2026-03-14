"""Sales-exception-related enumerations."""

from enum import Enum


class ExceptionType(str, Enum):
    DISCOUNT = "discount"
    PRICE_OVERRIDE = "price_override"
    INCENTIVE_PACKAGE = "incentive_package"
    PAYMENT_CONCESSION = "payment_concession"
    MARKETING_PROMO = "marketing_promo"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
