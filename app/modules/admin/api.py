"""
admin.api

Administrative API router.

Endpoints — Currency Governance
  GET  /api/v1/admin/currency-audit   — scan all projects for currency anomalies
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.admin.currency_audit_service import scan_currency_integrity
from app.modules.auth.security import require_roles

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_roles("admin"))],
)

DbDep = Annotated[Session, Depends(get_db)]


@router.get("/currency-audit")
def currency_audit(db: DbDep) -> dict[str, Any]:
    """Scan all project-linked financial records for currency anomalies.

    Returns a structured report of any detected issues.

    Issue types:
    - ``mismatch``           — record.currency differs from project.base_currency
    - ``suspicious_default`` — record.currency is the platform default but
                               project.base_currency is not
    - ``null_currency``      — record.currency is NULL or empty

    An empty ``issues`` list means no anomalies were detected.
    """
    issues = scan_currency_integrity(db)

    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue["type"]] = counts.get(issue["type"], 0) + 1

    return {
        "total_issues": len(issues),
        "counts_by_type": counts,
        "issues": issues,
    }
