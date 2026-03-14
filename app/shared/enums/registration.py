"""Registration-related enumerations."""

from enum import Enum


class CaseStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    AWAITING_DOCUMENTS = "awaiting_documents"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
