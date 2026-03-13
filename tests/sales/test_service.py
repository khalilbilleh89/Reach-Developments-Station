"""
Tests for the sales service layer.

Validates business rules for buyer, reservation, and contract workflows.
"""

import pytest
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

    floor = Floor(building_id=building.id, level=1)
    db.add(floor)
    db.flush()

    unit = Unit(floor_id=floor.id, unit_number="101", unit_type="studio", internal_area=100.0)
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


_RESERVATION_DATES = {
    "reservation_date": "2026-03-13",
    "expiry_date": "2026-04-13",
}

_CONTRACT_BASE = {
    "contract_number": "CNT-001",
    "contract_date": "2026-03-13",
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
            ReservationCreate(unit_id="no-such-unit", buyer_id=buyer_id, **_RESERVATION_DATES)
        )
    assert exc_info.value.status_code == 404


def test_reserve_invalid_buyer_raises_404(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-NOBUY")
    _set_pricing(db_session, unit_id)
    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.create_reservation(
            ReservationCreate(unit_id=unit_id, buyer_id="no-such-buyer", **_RESERVATION_DATES)
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
                contract_date="2026-03-14",
                contract_price=500_000.0,
            )
        )
    assert exc_info.value.status_code == 409


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
            SalesContractCreate(unit_id="no-such-unit", buyer_id=buyer_id, **_CONTRACT_BASE)
        )
    assert exc_info.value.status_code == 404


def test_contract_invalid_buyer_raises_404(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CNOBUY")
    svc = SalesService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.create_contract(
            SalesContractCreate(unit_id=unit_id, buyer_id="no-such-buyer", **_CONTRACT_BASE)
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
            contract_date="2026-03-15",
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


def test_cancel_already_cancelled_contract_raises_409(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-DBCONT")
    buyer_id = _make_buyer(db_session, "dbcont@example.com")

    svc = SalesService(db_session)
    contract = svc.create_contract(
        SalesContractCreate(unit_id=unit_id, buyer_id=buyer_id, **_CONTRACT_BASE)
    )
    svc.cancel_contract(contract.id)
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_contract(contract.id)
    assert exc_info.value.status_code == 409


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
