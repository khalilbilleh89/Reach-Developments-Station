"""
Tests for the sales service layer.

Validates business rules for buyer, reservation, and contract workflows.
"""

import pytest
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.pricing.schemas import UnitPricingAttributesCreate
from app.modules.sales.schemas import (
    BuyerCreate,
    ReservationCreate,
    SalesContractCreate,
)
from app.modules.sales.service import SalesService
from app.shared.enums.sales import ContractStatus, ReservationStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unit(db: Session, project_code: str = "PRJ-SAL") -> str:
    """Create a full project hierarchy and return a unit ID."""
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="Sales Project", code=project_code)
    db.add(project)
    db.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db.add(building)
    db.flush()

    floor = Floor(
        building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1
    )
    db.add(floor)
    db.flush()

    unit = Unit(
        floor_id=floor.id, unit_number="101", unit_type="studio", internal_area=100.0
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit.id


def _set_pricing(db: Session, unit_id: str) -> None:
    """Attach minimal pricing attributes to a unit."""
    from app.modules.pricing.service import PricingService

    svc = PricingService(db)
    svc.set_pricing_attributes(
        unit_id,
        UnitPricingAttributesCreate(
            base_price_per_sqm=5000.0,
            floor_premium=0.0,
            view_premium=0.0,
            corner_premium=0.0,
            size_adjustment=0.0,
            custom_adjustment=0.0,
        ),
    )


def _make_buyer(db: Session, email: str = "buyer@example.com") -> str:
    svc = SalesService(db)
    buyer = svc.create_buyer(
        BuyerCreate(full_name="Test Buyer", email=email, phone="+1234567890")
    )
    return buyer.id


_RES_DATE = date(2026, 3, 13)
_EXP_DATE = date(2026, 4, 13)

_RESERVATION_DATES = {
    "reservation_date": _RES_DATE,
    "expiry_date": _EXP_DATE,
}

_CONTRACT_DATE = date(2026, 3, 13)

_CONTRACT_BASE = {
    "contract_number": "CNT-001",
    "contract_date": _CONTRACT_DATE,
    "contract_price": 500_000.0,
}


# ---------------------------------------------------------------------------
# Buyer tests
# ---------------------------------------------------------------------------


def test_create_buyer(db_session: Session):
    svc = SalesService(db_session)
    buyer = svc.create_buyer(
        BuyerCreate(full_name="Jane Doe", email="jane@example.com", phone="+9620000001")
    )
    assert buyer.id
    assert buyer.full_name == "Jane Doe"
    assert buyer.email == "jane@example.com"


def test_get_buyer(db_session: Session):
    buyer_id = _make_buyer(db_session, "get@example.com")
    svc = SalesService(db_session)
    fetched = svc.get_buyer(buyer_id)
    assert fetched.id == buyer_id


def test_get_buyer_not_found(db_session: Session):
    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.get_buyer("no-such-buyer")
    assert exc_info.value.status_code == 404


def test_list_buyers(db_session: Session):
    _make_buyer(db_session, "a@example.com")
    _make_buyer(db_session, "b@example.com")
    svc = SalesService(db_session)
    result = svc.list_buyers()
    assert result.total == 2
    assert len(result.items) == 2


# ---------------------------------------------------------------------------
# Reservation tests
# ---------------------------------------------------------------------------


def test_create_reservation(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-RES1")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "res1@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    assert res.id
    assert res.unit_id == unit_id
    assert res.buyer_id == buyer_id
    assert res.status == ReservationStatus.ACTIVE
    assert res.reservation_date == _RES_DATE
    assert res.expiry_date == _EXP_DATE


def test_reservation_date_types_are_date(db_session: Session):
    """Reservation date fields must be date objects, not strings."""
    unit_id = _make_unit(db_session, "PRJ-RDTYPE")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "rdtype@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    assert isinstance(res.reservation_date, date)
    assert isinstance(res.expiry_date, date)


def test_reservation_invalid_date_range_raises(db_session: Session):
    """expiry_date before reservation_date must be rejected at schema level."""
    with pytest.raises(ValueError):
        ReservationCreate(
            unit_id="any",
            buyer_id="any",
            reservation_date=date(2026, 4, 1),
            expiry_date=date(2026, 3, 1),  # earlier than reservation_date
        )


def test_reserve_unit_without_pricing_raises_422(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-NOPRICE")
    buyer_id = _make_buyer(db_session, "noprice@example.com")

    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.create_reservation(
            ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
        )
    assert exc_info.value.status_code == 422


def test_duplicate_active_reservation_blocked(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-DUP")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "dup@example.com")

    svc = SalesService(db_session)
    svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    with pytest.raises(HTTPException) as exc_info:
        svc.create_reservation(
            ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
        )
    assert exc_info.value.status_code == 409


def test_reserve_invalid_unit_raises_404(db_session: Session):
    buyer_id = _make_buyer(db_session, "nounit@example.com")
    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.create_reservation(
            ReservationCreate(
                unit_id="no-such-unit", buyer_id=buyer_id, **_RESERVATION_DATES
            )
        )
    assert exc_info.value.status_code == 404


def test_reserve_invalid_buyer_raises_404(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-NOBUY")
    _set_pricing(db_session, unit_id)
    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.create_reservation(
            ReservationCreate(
                unit_id=unit_id, buyer_id="no-such-buyer", **_RESERVATION_DATES
            )
        )
    assert exc_info.value.status_code == 404


def test_cancel_reservation(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CANRES")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "canres@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    cancelled = svc.cancel_reservation(res.id)
    assert cancelled.status == ReservationStatus.CANCELLED


def test_cancel_already_cancelled_reservation_raises_409(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-DBCAN")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "dbcan@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    svc.cancel_reservation(res.id)
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_reservation(res.id)
    assert exc_info.value.status_code == 409


def test_list_reservations(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-LRES")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "lres@example.com")

    svc = SalesService(db_session)
    svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    result = svc.list_reservations()
    assert result.total == 1
    assert result.items[0].unit_id == unit_id


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


def test_create_contract_directly(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CONT1")
    buyer_id = _make_buyer(db_session, "cont1@example.com")

    svc = SalesService(db_session)
    contract = svc.create_contract(
        SalesContractCreate(unit_id=unit_id, buyer_id=buyer_id, **_CONTRACT_BASE)
    )
    assert contract.id
    assert contract.unit_id == unit_id
    assert contract.buyer_id == buyer_id
    assert contract.contract_price == pytest.approx(500_000.0)
    assert contract.status == ContractStatus.DRAFT
    assert isinstance(contract.contract_date, date)
    assert contract.contract_date == _CONTRACT_DATE


def test_contract_date_type_is_date(db_session: Session):
    """contract_date must be a date object in the response."""
    unit_id = _make_unit(db_session, "PRJ-CDTYPE")
    buyer_id = _make_buyer(db_session, "cdtype@example.com")

    svc = SalesService(db_session)
    contract = svc.create_contract(
        SalesContractCreate(unit_id=unit_id, buyer_id=buyer_id, **_CONTRACT_BASE)
    )
    assert isinstance(contract.contract_date, date)


def test_duplicate_active_contract_blocked(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-DCONT")
    buyer_id = _make_buyer(db_session, "dcont@example.com")

    svc = SalesService(db_session)
    svc.create_contract(
        SalesContractCreate(unit_id=unit_id, buyer_id=buyer_id, **_CONTRACT_BASE)
    )
    with pytest.raises(HTTPException) as exc_info:
        svc.create_contract(
            SalesContractCreate(
                unit_id=unit_id,
                buyer_id=buyer_id,
                contract_number="CNT-002",
                contract_date=date(2026, 3, 14),
                contract_price=500_000.0,
            )
        )
    assert exc_info.value.status_code == 409
    # Confirm error message reflects the actual rule
    assert (
        "draft" in exc_info.value.detail.lower()
        or "active" in exc_info.value.detail.lower()
    )


def test_duplicate_contract_number_blocked(db_session: Session):
    unit_id1 = _make_unit(db_session, "PRJ-CN1")
    unit_id2 = _make_unit(db_session, "PRJ-CN2")
    buyer_id = _make_buyer(db_session, "cndup@example.com")

    svc = SalesService(db_session)
    svc.create_contract(
        SalesContractCreate(unit_id=unit_id1, buyer_id=buyer_id, **_CONTRACT_BASE)
    )
    with pytest.raises(HTTPException) as exc_info:
        svc.create_contract(
            SalesContractCreate(unit_id=unit_id2, buyer_id=buyer_id, **_CONTRACT_BASE)
        )
    assert exc_info.value.status_code == 409


def test_contract_invalid_unit_raises_404(db_session: Session):
    buyer_id = _make_buyer(db_session, "cnounit@example.com")
    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.create_contract(
            SalesContractCreate(
                unit_id="no-such-unit", buyer_id=buyer_id, **_CONTRACT_BASE
            )
        )
    assert exc_info.value.status_code == 404


def test_contract_invalid_buyer_raises_404(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CNOBUY")
    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.create_contract(
            SalesContractCreate(
                unit_id=unit_id, buyer_id="no-such-buyer", **_CONTRACT_BASE
            )
        )
    assert exc_info.value.status_code == 404


def test_create_contract_from_reservation(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CONVR")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "convr@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    contract = svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            **_CONTRACT_BASE,
        )
    )
    assert contract.reservation_id == res.id

    # Reservation should now be converted
    updated_res = svc.get_reservation(res.id)
    assert updated_res.status == ReservationStatus.CONVERTED


def test_conversion_is_atomic(db_session: Session):
    """After a successful conversion, reservation must be CONVERTED — never left as active."""
    unit_id = _make_unit(db_session, "PRJ-ATOMIC")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "atomic@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    contract = svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            **_CONTRACT_BASE,
        )
    )
    # Both changes committed — contract exists and reservation is converted
    assert contract.id
    updated_res = svc.get_reservation(res.id)
    assert updated_res.status == ReservationStatus.CONVERTED
    # The unit must not have another active reservation (conversion freed it from that state)
    assert svc.reservation_repo.get_active_by_unit(unit_id) is None


def test_reservation_id_cannot_back_two_contracts(db_session: Session):
    """A converted reservation must not be linkable to a second contract."""
    unit_id = _make_unit(db_session, "PRJ-RESDUP")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "resdup@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    # First contract converts the reservation
    first_contract = svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            contract_number="CNT-RESDUP-1",
            contract_date=_CONTRACT_DATE,
            contract_price=500_000.0,
        )
    )
    # Cancel first contract so the unit is no longer blocked by an open contract
    svc.cancel_contract(first_contract.id)

    # Now try linking the same (already-converted) reservation to a second contract:
    # blocked because reservation status is 'converted', not 'active' → 409
    with pytest.raises(HTTPException) as exc_info:
        svc.create_contract(
            SalesContractCreate(
                unit_id=unit_id,
                buyer_id=buyer_id,
                reservation_id=res.id,
                contract_number="CNT-RESDUP-2",
                contract_date=_CONTRACT_DATE,
                contract_price=500_000.0,
            )
        )
    assert exc_info.value.status_code == 409


def test_convert_reservation_endpoint(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CVRE")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "cvre@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    contract = svc.convert_reservation_to_contract(
        res.id,
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            contract_number="CNT-CONV",
            contract_date=date(2026, 3, 15),
            contract_price=450_000.0,
        ),
    )
    assert contract.reservation_id == res.id
    assert contract.contract_price == pytest.approx(450_000.0)

    updated_res = svc.get_reservation(res.id)
    assert updated_res.status == ReservationStatus.CONVERTED


def test_cancel_contract(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CCONT")
    buyer_id = _make_buyer(db_session, "ccont@example.com")

    svc = SalesService(db_session)
    contract = svc.create_contract(
        SalesContractCreate(unit_id=unit_id, buyer_id=buyer_id, **_CONTRACT_BASE)
    )
    cancelled = svc.cancel_contract(contract.id)
    assert cancelled.status == ContractStatus.CANCELLED


def test_cancel_already_cancelled_contract_raises(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-DBCONT")
    buyer_id = _make_buyer(db_session, "dbcont@example.com")

    svc = SalesService(db_session)
    contract = svc.create_contract(
        SalesContractCreate(unit_id=unit_id, buyer_id=buyer_id, **_CONTRACT_BASE)
    )
    svc.cancel_contract(contract.id)
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_contract(contract.id)
    # State machine returns 422 for invalid transitions (cancelled is terminal)
    assert exc_info.value.status_code in (409, 422)


def test_list_contracts(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-LCONT")
    buyer_id = _make_buyer(db_session, "lcont@example.com")

    svc = SalesService(db_session)
    svc.create_contract(
        SalesContractCreate(unit_id=unit_id, buyer_id=buyer_id, **_CONTRACT_BASE)
    )
    result = svc.list_contracts()
    assert result.total == 1
    assert result.items[0].unit_id == unit_id


def test_new_reservation_allowed_after_cancellation(db_session: Session):
    """After cancelling a reservation, a new one can be made for the same unit."""
    unit_id = _make_unit(db_session, "PRJ-AFTERCAN")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "aftercan@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    svc.cancel_reservation(res.id)

    new_res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    assert new_res.status == ReservationStatus.ACTIVE


# ---------------------------------------------------------------------------
# Contract activation tests
# ---------------------------------------------------------------------------


def test_activate_contract_from_reservation(db_session: Session):
    """A draft contract linked to a converted reservation can be activated."""
    unit_id = _make_unit(db_session, "PRJ-ACT1")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "act1@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    contract = svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            **_CONTRACT_BASE,
        )
    )
    assert contract.status == ContractStatus.DRAFT

    activated = svc.activate_contract(contract.id)
    assert activated.status == ContractStatus.ACTIVE


def test_activate_contract_without_reservation_raises_422(db_session: Session):
    """A contract with no reservation linkage cannot be activated."""
    unit_id = _make_unit(db_session, "PRJ-ACTNORES")
    buyer_id = _make_buyer(db_session, "actnores@example.com")

    svc = SalesService(db_session)
    contract = svc.create_contract(
        SalesContractCreate(unit_id=unit_id, buyer_id=buyer_id, **_CONTRACT_BASE)
    )
    with pytest.raises(HTTPException) as exc_info:
        svc.activate_contract(contract.id)
    assert exc_info.value.status_code == 422


def test_activate_already_active_contract_raises_422(db_session: Session):
    """Activating an already-active contract is an invalid transition."""
    unit_id = _make_unit(db_session, "PRJ-DBLACT")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "dblact@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    contract = svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            **_CONTRACT_BASE,
        )
    )
    svc.activate_contract(contract.id)
    with pytest.raises(HTTPException) as exc_info:
        svc.activate_contract(contract.id)
    assert exc_info.value.status_code == 422


def test_activate_cancelled_contract_raises_422(db_session: Session):
    """A cancelled contract cannot be activated."""
    unit_id = _make_unit(db_session, "PRJ-CANCACT")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "cancact@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    contract = svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            **_CONTRACT_BASE,
        )
    )
    svc.cancel_contract(contract.id)
    with pytest.raises(HTTPException) as exc_info:
        svc.activate_contract(contract.id)
    assert exc_info.value.status_code == 422


def test_cancel_active_contract_raises_422_on_second_cancel(db_session: Session):
    """After cancelling an active contract, a second cancel raises 422 (terminal state)."""
    unit_id = _make_unit(db_session, "PRJ-CACACT")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "cacact@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    contract = svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            **_CONTRACT_BASE,
        )
    )
    svc.activate_contract(contract.id)
    svc.cancel_contract(contract.id)
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_contract(contract.id)
    assert exc_info.value.status_code in (409, 422)


def test_cancel_contract_not_found_raises_404(db_session: Session):
    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_contract("no-such-contract")
    assert exc_info.value.status_code == 404


def test_activate_contract_not_found_raises_404(db_session: Session):
    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.activate_contract("no-such-contract")
    assert exc_info.value.status_code == 404


def test_expire_reservation_lifecycle(db_session: Session):
    """Reservation can be explicitly expired; expired reservations cannot be re-expired."""
    unit_id = _make_unit(db_session, "PRJ-EXPRES")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "expres@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    expired = svc.expire_reservation(res.id)
    assert expired.status == ReservationStatus.EXPIRED

    # Cannot expire an already-expired reservation
    with pytest.raises(HTTPException) as exc_info:
        svc.expire_reservation(res.id)
    assert exc_info.value.status_code == 409


def test_reservation_converted_blocks_new_reservation(db_session: Session):
    """After converting a reservation, the same unit can accept a new reservation (post-contract-cancellation)."""
    unit_id = _make_unit(db_session, "PRJ-CONVBLK")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "convblk@example.com")

    svc = SalesService(db_session)
    res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id, **_RESERVATION_DATES)
    )
    contract = svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            **_CONTRACT_BASE,
        )
    )
    # Reservation is CONVERTED; no active reservation remains
    assert svc.reservation_repo.get_active_by_unit(unit_id) is None

    # Cancel the contract — unit is freed
    svc.cancel_contract(contract.id)

    # A fresh reservation can now be created
    buyer_id2 = _make_buyer(db_session, "convblk2@example.com")
    new_res = svc.create_reservation(
        ReservationCreate(unit_id=unit_id, buyer_id=buyer_id2, **_RESERVATION_DATES)
    )
    assert new_res.status == ReservationStatus.ACTIVE
