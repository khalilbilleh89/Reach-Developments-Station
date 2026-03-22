"""
core.constants.common

Cross-domain shared constants used across multiple platform modules.

Centralises status label strings and pagination defaults that are
referenced in more than one module to prevent drift between definitions.
"""

# ---------------------------------------------------------------------------
# Generic lifecycle status labels
# ---------------------------------------------------------------------------

STATUS_DRAFT = "draft"
STATUS_APPROVED = "approved"
STATUS_ARCHIVED = "archived"

# ---------------------------------------------------------------------------
# Pagination defaults
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SKIP = 0
DEFAULT_PAGE_LIMIT = 100

# ---------------------------------------------------------------------------
# Sort directions
# ---------------------------------------------------------------------------

SORT_ASC = "asc"
SORT_DESC = "desc"
