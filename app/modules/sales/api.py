"""
sales.api

REST API router for the Sales module.
Endpoints under /sales.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.sales.schemas import (
    BuyerCreate,
    BuyerListResponse,
    BuyerResponse,
    ContractPaymentRecordRequest,
    ContractPaymentScheduleListResponse,
    ContractPaymentScheduleResponse,
    ReservationCreate,
    ReservationListResponse,
    ReservationResponse,
    ReservationUpdate,
    SalesContractCreate,
    SalesContractListResponse,
    SalesContractResponse,
    SalesContractUpdate,
)
from app.modules.sales.service import ContractPaymentService, SalesService

router = APIRouter(prefix="/sales", tags=["Sales"], dependencies=[Depends(get_current_user_payload)])


def get_service(db: Session = Depends(get_db)) -> SalesService:
    return SalesService(db)


def get_payment_service(db: Session = Depends(get_db)) -> ContractPaymentService:
    return ContractPaymentService(db)


# ---------------------------------------------------------------------------
# Buyer endpoints
# ---------------------------------------------------------------------------

@router.post("/buyers", response_model=BuyerResponse, status_code=201)
def create_buyer(
    data: BuyerCreate,
    service: Annotated[SalesService, Depends(get_service)],
) -> BuyerResponse:
    """Register a new buyer."""
    return service.create_buyer(data)


@router.get("/buyers", response_model=BuyerListResponse)
def list_buyers(
    service: Annotated[SalesService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> BuyerListResponse:
    """List all buyers."""
    return service.list_buyers(skip=skip, limit=limit)


@router.get("/buyers/{buyer_id}", response_model=BuyerResponse)
def get_buyer(
    buyer_id: str,
    service: Annotated[SalesService, Depends(get_service)],
) -> BuyerResponse:
    """Get a buyer by ID."""
    return service.get_buyer(buyer_id)


# ---------------------------------------------------------------------------
# Reservation endpoints
# ---------------------------------------------------------------------------

@router.post("/reservations", response_model=ReservationResponse, status_code=201)
def create_reservation(
    data: ReservationCreate,
    service: Annotated[SalesService, Depends(get_service)],
) -> ReservationResponse:
    """Create a new reservation for a unit."""
    return service.create_reservation(data)


@router.get("/reservations", response_model=ReservationListResponse)
def list_reservations(
    service: Annotated[SalesService, Depends(get_service)],
    unit_id: Optional[str] = Query(default=None),
    buyer_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ReservationListResponse:
    """List reservations with optional filtering."""
    return service.list_reservations(
        unit_id=unit_id, buyer_id=buyer_id, skip=skip, limit=limit
    )


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: str,
    service: Annotated[SalesService, Depends(get_service)],
) -> ReservationResponse:
    """Get a reservation by ID."""
    return service.get_reservation(reservation_id)


@router.patch("/reservations/{reservation_id}", response_model=ReservationResponse)
def update_reservation(
    reservation_id: str,
    data: ReservationUpdate,
    service: Annotated[SalesService, Depends(get_service)],
) -> ReservationResponse:
    """Update an active reservation."""
    return service.update_reservation(reservation_id, data)


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: str,
    service: Annotated[SalesService, Depends(get_service)],
) -> ReservationResponse:
    """Cancel an active reservation."""
    return service.cancel_reservation(reservation_id)


@router.post(
    "/reservations/{reservation_id}/convert-to-contract",
    response_model=SalesContractResponse,
    status_code=201,
)
def convert_reservation_to_contract(
    reservation_id: str,
    data: SalesContractCreate,
    service: Annotated[SalesService, Depends(get_service)],
) -> SalesContractResponse:
    """Convert an active reservation to a sales contract."""
    return service.convert_reservation_to_contract(reservation_id, data)


# ---------------------------------------------------------------------------
# Contract endpoints
# ---------------------------------------------------------------------------

@router.post("/contracts", response_model=SalesContractResponse, status_code=201)
def create_contract(
    data: SalesContractCreate,
    service: Annotated[SalesService, Depends(get_service)],
) -> SalesContractResponse:
    """Create a new sales contract."""
    return service.create_contract(data)


@router.get("/contracts", response_model=SalesContractListResponse)
def list_contracts(
    service: Annotated[SalesService, Depends(get_service)],
    unit_id: Optional[str] = Query(default=None),
    buyer_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> SalesContractListResponse:
    """List contracts with optional filtering."""
    return service.list_contracts(
        unit_id=unit_id, buyer_id=buyer_id, skip=skip, limit=limit
    )


@router.get("/contracts/{contract_id}", response_model=SalesContractResponse)
def get_contract(
    contract_id: str,
    service: Annotated[SalesService, Depends(get_service)],
) -> SalesContractResponse:
    """Get a contract by ID."""
    return service.get_contract(contract_id)


@router.patch("/contracts/{contract_id}", response_model=SalesContractResponse)
def update_contract(
    contract_id: str,
    data: SalesContractUpdate,
    service: Annotated[SalesService, Depends(get_service)],
) -> SalesContractResponse:
    """Update a draft or active contract."""
    return service.update_contract(contract_id, data)


@router.post("/contracts/{contract_id}/cancel", response_model=SalesContractResponse)
def cancel_contract(
    contract_id: str,
    service: Annotated[SalesService, Depends(get_service)],
) -> SalesContractResponse:
    """Cancel a draft or active contract."""
    return service.cancel_contract(contract_id)


@router.post("/contracts/{contract_id}/activate", response_model=SalesContractResponse)
def activate_contract(
    contract_id: str,
    service: Annotated[SalesService, Depends(get_service)],
) -> SalesContractResponse:
    """Activate a draft contract.

    Rules:
      - Contract must be in DRAFT status.
      - Contract must have a linked reservation.
      - The linked reservation must be in CONVERTED status.

    Returns 404 if the contract does not exist.
    Returns 422 if the contract has no reservation or transition is invalid.
    Returns 409 if the reservation is not in CONVERTED status.
    """
    return service.activate_contract(contract_id)


@router.get("/units/{unit_id}/contracts", response_model=SalesContractListResponse)
def get_unit_contracts(
    unit_id: str,
    service: Annotated[SalesService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> SalesContractListResponse:
    """List all contracts for a specific unit."""
    return service.list_contracts(unit_id=unit_id, skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# Contract payment schedule endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/contracts/{contract_id}/payment-schedule",
    response_model=ContractPaymentScheduleListResponse,
)
def get_payment_schedule(
    contract_id: str,
    payment_service: Annotated[ContractPaymentService, Depends(get_payment_service)],
) -> ContractPaymentScheduleListResponse:
    """List the payment installment schedule for a contract."""
    return payment_service.list_schedule(contract_id)


@router.post(
    "/contracts/{contract_id}/generate-payment-schedule",
    response_model=ContractPaymentScheduleListResponse,
    status_code=201,
)
def generate_payment_schedule(
    contract_id: str,
    payment_service: Annotated[ContractPaymentService, Depends(get_payment_service)],
) -> ContractPaymentScheduleListResponse:
    """Generate the default payment schedule for a contract.

    Returns 409 if a schedule already exists.
    """
    return payment_service.generate_payment_schedule(contract_id)


@router.post(
    "/contracts/{contract_id}/payments",
    response_model=ContractPaymentScheduleResponse,
)
def record_payment(
    contract_id: str,
    data: ContractPaymentRecordRequest,
    payment_service: Annotated[ContractPaymentService, Depends(get_payment_service)],
) -> ContractPaymentScheduleResponse:
    """Record a payment against a specific installment.

    Returns 404 if the installment does not exist.
    Returns 409 if the installment is already paid or cancelled.
    """
    return payment_service.record_payment(contract_id, data)
