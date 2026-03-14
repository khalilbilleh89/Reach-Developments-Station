"""
finance.api

REST endpoints for project-level financial summaries.

Router prefix: /finance
Full path:     /api/v1/finance/...

Endpoints
---------
  GET /finance/projects/{project_id}/summary  — project financial summary
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.finance.schemas import ProjectFinanceSummaryResponse
from app.modules.finance.service import FinanceSummaryService

router = APIRouter(prefix="/finance", tags=["finance"])


def get_service(db: Session = Depends(get_db)) -> FinanceSummaryService:
    return FinanceSummaryService(db)


@router.get(
    "/projects/{project_id}/summary",
    response_model=ProjectFinanceSummaryResponse,
)
def get_project_finance_summary(
    project_id: str,
    service: Annotated[FinanceSummaryService, Depends(get_service)],
) -> ProjectFinanceSummaryResponse:
    """Return the aggregated financial summary for a project."""
    return service.get_project_summary(project_id)
