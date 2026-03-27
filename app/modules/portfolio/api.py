"""
portfolio.api

Portfolio Intelligence API router.

Endpoints:
  GET /api/v1/portfolio/dashboard — read-only portfolio dashboard

The endpoint assembles a coherent dashboard payload from existing source-of-truth
module data.  No source records are mutated.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.portfolio.schemas import PortfolioDashboardResponse
from app.modules.portfolio.service import PortfolioService

router = APIRouter(
    prefix="/portfolio",
    tags=["Portfolio Intelligence"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> PortfolioService:
    return PortfolioService(db)


ServiceDep = Annotated[PortfolioService, Depends(_service)]


@router.get("/dashboard", response_model=PortfolioDashboardResponse)
def get_dashboard(service: ServiceDep) -> PortfolioDashboardResponse:
    """Return the portfolio intelligence dashboard.

    Aggregates project, unit, sales, collections, and pipeline data into a
    single read-only dashboard response.  Suitable for executive views and
    portfolio monitoring.
    """
    return service.get_dashboard()
