"""
concept_design.api

REST API router for the Concept Design module.

Endpoints
---------
POST   /concept-options
GET    /concept-options
GET    /concept-options/compare
GET    /concept-options/{concept_option_id}
PATCH  /concept-options/{concept_option_id}
DELETE /concept-options/{concept_option_id}
POST   /concept-options/{concept_option_id}/duplicate
POST   /concept-options/{concept_option_id}/unit-mix
GET    /concept-options/{concept_option_id}/summary
POST   /concept-options/{concept_option_id}/promote

PR-CONCEPT-052, PR-CONCEPT-053, PR-CONCEPT-054, PR-CONCEPT-057, PR-CONCEPT-058
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.concept_design.schemas import (
    ConceptOptionComparisonResponse,
    ConceptOptionCreate,
    ConceptOptionListResponse,
    ConceptOptionResponse,
    ConceptOptionSummaryResponse,
    ConceptOptionUpdate,
    ConceptPromotionRequest,
    ConceptPromotionResponse,
    ConceptUnitMixLineCreate,
    ConceptUnitMixLineResponse,
)
from app.modules.concept_design.service import ConceptDesignService

router = APIRouter(
    prefix="/concept-options",
    tags=["concept-design"],
    dependencies=[Depends(get_current_user_payload)],
)


def _get_service(db: Session = Depends(get_db)) -> ConceptDesignService:
    return ConceptDesignService(db)


# ---------------------------------------------------------------------------
# ConceptOption endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ConceptOptionResponse, status_code=201)
def create_concept_option(
    data: ConceptOptionCreate,
    service: Annotated[ConceptDesignService, Depends(_get_service)],
) -> ConceptOptionResponse:
    """Create a new concept design option.

    project_id and scenario_id are both optional — a concept option may be
    created before a project record exists.
    """
    return service.create_concept_option(data)


@router.get("", response_model=ConceptOptionListResponse)
def list_concept_options(
    service: Annotated[ConceptDesignService, Depends(_get_service)],
    project_id: Optional[str] = Query(default=None),
    scenario_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ConceptOptionListResponse:
    """List concept options, optionally filtered by project or scenario."""
    return service.list_concept_options(
        project_id=project_id,
        scenario_id=scenario_id,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Comparison endpoint — PR-CONCEPT-053
# ---------------------------------------------------------------------------

@router.get("/compare", response_model=ConceptOptionComparisonResponse)
def compare_concept_options(
    service: Annotated[ConceptDesignService, Depends(_get_service)],
    project_id: Optional[str] = Query(default=None),
    scenario_id: Optional[str] = Query(default=None),
) -> ConceptOptionComparisonResponse:
    """Return a structured side-by-side comparison of all concept options.

    Exactly one of ``project_id`` or ``scenario_id`` must be provided.
    Supplying both or neither returns HTTP 422.
    """
    return service.compare_concept_options(
        project_id=project_id,
        scenario_id=scenario_id,
    )


@router.get("/{concept_option_id}", response_model=ConceptOptionResponse)
def get_concept_option(
    concept_option_id: str,
    service: Annotated[ConceptDesignService, Depends(_get_service)],
) -> ConceptOptionResponse:
    """Retrieve a single concept option by ID."""
    return service.get_concept_option(concept_option_id)


@router.patch("/{concept_option_id}", response_model=ConceptOptionResponse)
def update_concept_option(
    concept_option_id: str,
    data: ConceptOptionUpdate,
    service: Annotated[ConceptDesignService, Depends(_get_service)],
) -> ConceptOptionResponse:
    """Partially update a concept option."""
    return service.update_concept_option(concept_option_id, data)


@router.delete("/{concept_option_id}", status_code=204)
def delete_concept_option(
    concept_option_id: str,
    service: Annotated[ConceptDesignService, Depends(_get_service)],
) -> Response:
    """Delete a concept option and its unit mix lines.

    Deletion is forbidden if the concept option has already been promoted
    (HTTP 409).  Promoted concepts are the immutable origin of project
    structure and cannot be removed.
    """
    service.delete_concept_option(concept_option_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Duplication endpoint — PR-CONCEPT-058
# ---------------------------------------------------------------------------

@router.post(
    "/{concept_option_id}/duplicate",
    response_model=ConceptOptionResponse,
    status_code=200,
)
def duplicate_concept_option(
    concept_option_id: str,
    service: Annotated[ConceptDesignService, Depends(_get_service)],
) -> ConceptOptionResponse:
    """Duplicate a concept option and its unit mix lines.

    The duplicate receives a generated name: ``"<original> (Copy)"``,
    ``"<original> (Copy 2)"``, etc.

    Duplication is forbidden for archived concept options (HTTP 409).
    Promoted options can be duplicated — the copy starts unpromoted.
    """
    return service.duplicate_concept_option(concept_option_id)


# ---------------------------------------------------------------------------
# Unit-mix endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{concept_option_id}/unit-mix",
    response_model=ConceptUnitMixLineResponse,
    status_code=201,
)
def add_unit_mix_line(
    concept_option_id: str,
    data: ConceptUnitMixLineCreate,
    service: Annotated[ConceptDesignService, Depends(_get_service)],
) -> ConceptUnitMixLineResponse:
    """Add a unit-mix line to a concept option."""
    return service.add_concept_mix_line(concept_option_id, data)


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/{concept_option_id}/summary",
    response_model=ConceptOptionSummaryResponse,
)
def get_concept_option_summary(
    concept_option_id: str,
    service: Annotated[ConceptDesignService, Depends(_get_service)],
) -> ConceptOptionSummaryResponse:
    """Return a concept option with all derived program metrics computed by the engine."""
    return service.get_concept_option_summary(concept_option_id)


# ---------------------------------------------------------------------------
# Promotion endpoint — PR-CONCEPT-054
# ---------------------------------------------------------------------------

@router.post(
    "/{concept_option_id}/promote",
    response_model=ConceptPromotionResponse,
    status_code=201,
)
def promote_concept_option(
    concept_option_id: str,
    data: ConceptPromotionRequest,
    service: Annotated[ConceptDesignService, Depends(_get_service)],
) -> ConceptPromotionResponse:
    """Promote a concept option into a structured downstream project phase.

    The selected concept option must be in ``active`` or ``draft`` status,
    must not have already been promoted, and must have ``building_count``,
    ``floor_count``, and at least one unit-mix line.

    If the concept option is already linked to a project, that project is
    used as the promotion target.  Otherwise ``target_project_id`` must be
    supplied in the request body.
    """
    return service.promote_concept_option(concept_option_id, data)
