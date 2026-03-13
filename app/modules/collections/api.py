"""
collections.api

REST endpoints for payment receipts and contract receivables.

Router prefix: /collections
Full path:     /api/v1/collections/...

Endpoints
---------
Receipts
  POST  /receipts                              — record a receipt
  GET   /receipts/{receipt_id}                 — get a receipt by id
  GET   /contracts/{contract_id}/receipts      — list receipts for a contract

Receivables
  GET   /contracts/{contract_id}/receivables   — get receivables for a contract
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.collections.schemas import (
    ContractReceivablesResponse,
    PaymentReceiptCreate,
    PaymentReceiptListResponse,
    PaymentReceiptResponse,
)
from app.modules.collections.service import CollectionsService

router = APIRouter(prefix="/collections", tags=["collections"])


def get_service(db: Session = Depends(get_db)) -> CollectionsService:
    return CollectionsService(db)


# ---------------------------------------------------------------------------
# Receipt endpoints
# ---------------------------------------------------------------------------


@router.post("/receipts", response_model=PaymentReceiptResponse, status_code=201)
def record_receipt(
    data: PaymentReceiptCreate,
    service: Annotated[CollectionsService, Depends(get_service)],
) -> PaymentReceiptResponse:
    """Record a payment receipt against a scheduled installment."""
    return service.record_receipt(data)


@router.get("/receipts/{receipt_id}", response_model=PaymentReceiptResponse)
def get_receipt(
    receipt_id: str,
    service: Annotated[CollectionsService, Depends(get_service)],
) -> PaymentReceiptResponse:
    """Get a single payment receipt by ID."""
    return service.get_receipt(receipt_id)


@router.get(
    "/contracts/{contract_id}/receipts",
    response_model=PaymentReceiptListResponse,
)
def list_receipts_for_contract(
    contract_id: str,
    service: Annotated[CollectionsService, Depends(get_service)],
) -> PaymentReceiptListResponse:
    """List all payment receipts for a contract."""
    return service.get_receipts_for_contract(contract_id)


# ---------------------------------------------------------------------------
# Receivables endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/contracts/{contract_id}/receivables",
    response_model=ContractReceivablesResponse,
)
def get_receivables_for_contract(
    contract_id: str,
    service: Annotated[CollectionsService, Depends(get_service)],
) -> ContractReceivablesResponse:
    """Get the receivables summary for a contract."""
    return service.get_receivables_for_contract(contract_id)
