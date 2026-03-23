"""
core.constants.error_codes

Canonical error code strings used by the global error handling framework.

These constants prevent string drift across modules and serve as the
authoritative source for the ``code`` field in all API error responses.
"""

RESOURCE_NOT_FOUND: str = "RESOURCE_NOT_FOUND"
VALIDATION_ERROR: str = "VALIDATION_ERROR"
PERMISSION_DENIED: str = "PERMISSION_DENIED"
CONFLICT: str = "CONFLICT"
INTERNAL_ERROR: str = "INTERNAL_ERROR"
