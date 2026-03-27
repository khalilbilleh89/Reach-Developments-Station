"""
feasibility_feedback.api

Sales Absorption → Feasibility Feedback API router.

Endpoints:
  GET /api/v1/projects/{project_id}/feasibility-feedback
    — Read-only project-level feedback endpoint.

The endpoint composes live source data into a transparent feedback signal
indicating whether actual commercial performance is validating or undermining
project underwriting assumptions.

No source records are mutated.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.feasibility_feedback.schemas import ProjectFeasibilityFeedbackResponse
from app.modules.feasibility_feedback.service import FeasibilityFeedbackService

router = APIRouter(
    prefix="/projects",
    tags=["Feasibility Feedback"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> FeasibilityFeedbackService:
    return FeasibilityFeedbackService(db)


ServiceDep = Annotated[FeasibilityFeedbackService, Depends(_service)]


@router.get(
    "/{project_id}/feasibility-feedback",
    response_model=ProjectFeasibilityFeedbackResponse,
)
def get_project_feasibility_feedback(
    project_id: str,
    service: ServiceDep,
) -> ProjectFeasibilityFeedbackResponse:
    """Return sales absorption and collection feedback for a single project.

    Compares actual unit absorption and cash collection performance against
    transparent thresholds and surfaces a feedback badge with explanatory notes.

    The response is derived entirely from live source data and is read-only.
    No feasibility formulas are altered and no source records are mutated.

    Returns 404 if the project does not exist.
    """
    return service.get_project_feedback(project_id)
