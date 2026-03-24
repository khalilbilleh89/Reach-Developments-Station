"""
concept_design.api

REST API router for the Concept Design module.

Endpoints
---------
POST   /concept-options
GET    /concept-options
GET    /concept-options/{concept_option_id}
PATCH  /concept-options/{concept_option_id}
POST   /concept-options/{concept_option_id}/unit-mix
GET    /concept-options/{concept_option_id}/summary

PR-CONCEPT-052
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.concept_design.schemas import (
    ConceptOptionCreate,
    ConceptOptionListResponse,
    ConceptOptionResponse,
    ConceptOptionSummaryResponse,
    ConceptOptionUpdate,
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
