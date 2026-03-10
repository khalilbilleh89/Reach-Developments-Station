"""Registration-related enumerations."""

from enum import Enum


class RegistrationStatus(str, Enum):
    INITIATED = "initiated"
    DOCUMENTS_SUBMITTED = "documents_submitted"
    SUBMITTED_TO_AUTHORITY = "submitted_to_authority"
    TITLE_ISSUED = "title_issued"
    CANCELLED = "cancelled"
