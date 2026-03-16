"""
Tests for the reservations service layer.

Validates business rules for unit reservation lifecycle:
  - create_reservation
  - double-reservation blocking
  - cancel_reservation
  - expire_reservation
  - convert_to_contract
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.reservations.schemas import ReservationCreate, ReservationStatus
from app.modules.reservations.service import ReservationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unit(db: Session, project_code: str = "PRJ-RES") -> str:
    """Create a full project hierarchy and return a unit ID."""
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="Reservation Project", code=project_code)
    db.add(project)
    db.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db.add(building)
    db.flush()

    floor = Floor(building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1)
    db.add(floor)
    db.flush()

    unit = Unit(floor_id=floor.id, unit_number="101", unit_type="studio", internal_area=80.0)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit.id


_BASE_PAYLOAD = {
    "customer_name": "Alice Smith",
    "customer_phone": "+971501234567",
    "customer_email": "alice@example.com",
    "reservation_price": 750_000.0,
    "reservation_fee": 5_000.0,
    "currency": "AED",
}

_FUTURE_EXPIRY = datetime.now(timezone.utc) + timedelta(days=30)


def _make_create(unit_id: str, **overrides) -> ReservationCreate:
    data = {**_BASE_PAYLOAD, "unit_id": unit_id, **overrides}
    return ReservationCreate(**data)


# ---------------------------------------------------------------------------
# Create reservation
# ---------------------------------------------------------------------------


def test_create_reservation(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CRES")
    svc = ReservationService(db_session)

    res = svc.create_reservation(_make_create(unit_id, expires_at=_FUTURE_EXPIRY))

    assert res.id
    assert res.unit_id == unit_id
    assert res.customer_name == "Alice Smith"
    assert res.customer_phone == "+971501234567"
    assert res.customer_email == "alice@example.com"
    assert float(res.reservation_price) == 750_000.0
    assert float(res.reservation_fee) == 5_000.0
    assert res.currency == "AED"
    assert res.status == ReservationStatus.active


def test_create_reservation_invalid_unit_raises_404(db_session: Session):
    svc = ReservationService(db_session)

    with pytest.raises(HTTPException) as exc_info:
        svc.create_reservation(_make_create("no-such-unit"))

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Double-reservation blocking
# ---------------------------------------------------------------------------


def test_double_reservation_blocked(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-DUPRES")
    svc = ReservationService(db_session)

    svc.create_reservation(_make_create(unit_id))

    with pytest.raises(HTTPException) as exc_info:
        svc.create_reservation(_make_create(unit_id))

    assert exc_info.value.status_code == 409


def test_new_reservation_allowed_after_cancellation(db_session: Session):
    """After cancelling a reservation, a new one can be created for the same unit."""
    unit_id = _make_unit(db_session, "PRJ-AFCAN")
    svc = ReservationService(db_session)

    res = svc.create_reservation(_make_create(unit_id))
    svc.cancel_reservation(res.id)

    new_res = svc.create_reservation(_make_create(unit_id))
    assert new_res.status == ReservationStatus.active


# ---------------------------------------------------------------------------
# Get reservation
# ---------------------------------------------------------------------------


def test_get_reservation(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-GRES")
    svc = ReservationService(db_session)

    created = svc.create_reservation(_make_create(unit_id))
    fetched = svc.get_reservation(created.id)

    assert fetched.id == created.id
    assert fetched.unit_id == unit_id


def test_get_reservation_not_found(db_session: Session):
    svc = ReservationService(db_session)

    with pytest.raises(HTTPException) as exc_info:
        svc.get_reservation("no-such-id")

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Cancel reservation
# ---------------------------------------------------------------------------


def test_cancel_reservation(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CANR")
    svc = ReservationService(db_session)

    res = svc.create_reservation(_make_create(unit_id))
    cancelled = svc.cancel_reservation(res.id)

    assert cancelled.status == ReservationStatus.cancelled


def test_cancel_already_cancelled_raises_409(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-DBCAN")
    svc = ReservationService(db_session)

    res = svc.create_reservation(_make_create(unit_id))
    svc.cancel_reservation(res.id)

    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_reservation(res.id)

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Expire reservation
# ---------------------------------------------------------------------------


def test_expire_reservation(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-EXPR")
    svc = ReservationService(db_session)

    res = svc.create_reservation(_make_create(unit_id))
    expired = svc.expire_reservation(res.id)

    assert expired.status == ReservationStatus.expired


def test_expire_non_active_raises_409(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-EXPNA")
    svc = ReservationService(db_session)

    res = svc.create_reservation(_make_create(unit_id))
    svc.cancel_reservation(res.id)

    with pytest.raises(HTTPException) as exc_info:
        svc.expire_reservation(res.id)

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Convert to contract
# ---------------------------------------------------------------------------


def test_convert_reservation(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CONV")
    svc = ReservationService(db_session)

    res = svc.create_reservation(_make_create(unit_id))
    converted = svc.convert_to_contract(res.id)

    assert converted.status == ReservationStatus.converted


def test_convert_non_active_raises_409(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CONVNA")
    svc = ReservationService(db_session)

    res = svc.create_reservation(_make_create(unit_id))
    svc.cancel_reservation(res.id)

    with pytest.raises(HTTPException) as exc_info:
        svc.convert_to_contract(res.id)

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# List by project
# ---------------------------------------------------------------------------


def test_list_reservations_by_project(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-LIST")
    svc = ReservationService(db_session)

    svc.create_reservation(_make_create(unit_id))

    # Fetch the project_id from the unit hierarchy
    from app.modules.units.models import Unit
    from app.modules.floors.models import Floor
    from app.modules.buildings.models import Building
    from app.modules.phases.models import Phase

    unit = db_session.query(Unit).filter_by(id=unit_id).one()
    floor = db_session.query(Floor).filter_by(id=unit.floor_id).one()
    building = db_session.query(Building).filter_by(id=floor.building_id).one()
    phase = db_session.query(Phase).filter_by(id=building.phase_id).one()

    result = svc.list_reservations_by_project(phase.project_id)

    assert result.total == 1
    assert result.items[0].unit_id == unit_id


# ---------------------------------------------------------------------------
# Auto-expiry helper
# ---------------------------------------------------------------------------


def test_expire_overdue_reservations(db_session: Session):
    unit1_id = _make_unit(db_session, "PRJ-EOVD1")
    unit2_id = _make_unit(db_session, "PRJ-EOVD2")
    svc = ReservationService(db_session)

    past_expiry = datetime.now(timezone.utc) - timedelta(days=1)
    future_expiry = datetime.now(timezone.utc) + timedelta(days=30)

    # One overdue reservation
    overdue = svc.create_reservation(_make_create(unit1_id, expires_at=past_expiry))
    # One still-valid reservation
    svc.create_reservation(_make_create(unit2_id, expires_at=future_expiry))

    count = svc.expire_overdue_reservations()
    assert count == 1

    # Verify the overdue one is now expired
    refreshed = svc.get_reservation(overdue.id)
    assert refreshed.status == ReservationStatus.expired
