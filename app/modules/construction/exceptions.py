"""
construction.exceptions

Domain-level exceptions for the Construction module.

These exceptions are transport-layer agnostic — they carry domain semantics
and are translated to HTTP responses at the API boundary.
"""


class ConstructionConflictError(Exception):
    """Raised when a construction operation violates a data integrity constraint."""
