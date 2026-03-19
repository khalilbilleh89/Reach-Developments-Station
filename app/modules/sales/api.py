"""
sales.api

REST API router for the Sales module.
Endpoints under /sales.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.sales.schemas import (
    BuyerCreate,
    BuyerListResponse,
    BuyerResponse,
    ReservationCreate,
    ReservationListResponse,
    ReservationResponse,
    ReservationUpdate,
    SalesContractCreate,
    SalesContractListResponse,
    SalesContractResponse,
    SalesContractUpdate,
)
from app.modules.sales.service import SalesService

router = APIRouter(prefix="/sales", tags=["Sales"])


def get_service(db: Session = Depends(get_db)) -> SalesService:
    return SalesService(db)


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
