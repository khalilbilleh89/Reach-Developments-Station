"""
finance.constants

Shared constants for the finance module.

Centralises status lists and other invariants used across multiple services
to prevent drift if additional statuses are introduced in the future.
"""

from app.shared.enums.sales import ContractPaymentStatus

# Installment statuses that represent collectible outstanding receivables.
# CANCELLED installments are not receivable obligations and are excluded.
RECEIVABLE_STATUSES = [
    ContractPaymentStatus.PENDING.value,
    ContractPaymentStatus.OVERDUE.value,
]
