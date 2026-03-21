"""
receivables.api

REST endpoints for the receivables module.

Router prefix: /receivables (plus contract and project-scoped routes)
Full paths:    /api/v1/contracts/{contract_id}/receivables/generate
               /api/v1/contracts/{contract_id}/receivables
               /api/v1/projects/{project_id}/receivables
               /api/v1/receivables/{receivable_id}
               /api/v1/receivables/{receivable_id}  (PATCH)
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.receivables.schemas import (
    GenerateReceivablesResponse,
    ReceivableListResponse,
    ReceivablePaymentUpdate,
    ReceivableResponse,
)
from app.modules.receivables.service import ReceivableService

router = APIRouter(tags=["receivables"], dependencies=[Depends(get_current_user_payload)])


def get_service(db: Session = Depends(get_db)) -> ReceivableService:
    return ReceivableService(db)


# ---------------------------------------------------------------------------
# Contract-scoped routes
# ---------------------------------------------------------------------------


@router.post(
    "/contracts/{contract_id}/receivables/generate",
    response_model=GenerateReceivablesResponse,
    status_code=201,
)
def generate_receivables(
    contract_id: str,
    service: Annotated[ReceivableService, Depends(get_service)],
) -> GenerateReceivablesResponse:
    """Generate one receivable per payment installment for a contract.

    Requires the contract to have a payment plan.  Raises 409 if receivables
    already exist for this contract.
    """
    return service.generate_for_contract(contract_id)


@router.get(
    "/contracts/{contract_id}/receivables",
    response_model=ReceivableListResponse,
)
def list_contract_receivables(
    contract_id: str,
    service: Annotated[ReceivableService, Depends(get_service)],
) -> ReceivableListResponse:
    """List all receivables for a contract."""
    return service.list_contract_receivables(contract_id)


# ---------------------------------------------------------------------------
# Project-scoped routes
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/receivables",
    response_model=ReceivableListResponse,
)
def list_project_receivables(
    project_id: str,
    service: Annotated[ReceivableService, Depends(get_service)],
) -> ReceivableListResponse:
    """List all receivables across all contracts in a project."""
    return service.list_project_receivables(project_id)


# ---------------------------------------------------------------------------
# Individual receivable routes
# ---------------------------------------------------------------------------


@router.get("/receivables/{receivable_id}", response_model=ReceivableResponse)
def get_receivable(
    receivable_id: str,
    service: Annotated[ReceivableService, Depends(get_service)],
) -> ReceivableResponse:
    """Get a single receivable by ID."""
    return service.get_receivable(receivable_id)


@router.patch("/receivables/{receivable_id}", response_model=ReceivableResponse)
def patch_receivable(
    receivable_id: str,
    payload: ReceivablePaymentUpdate,
    service: Annotated[ReceivableService, Depends(get_service)],
) -> ReceivableResponse:
    """Record a manual payment update for a receivable.

    amount_paid must be the new cumulative total (not an incremental delta).
    Balance and status are recalculated automatically.
    """
    return service.apply_payment_update(receivable_id, payload)
