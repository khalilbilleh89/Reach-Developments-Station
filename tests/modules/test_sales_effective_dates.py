"""Effective dates: a transition cannot be dated later than it happened.

Every operation here changes the record's current state the moment it runs. A
future effective date would produce a unit that is contracted today and a
history saying the contract begins next week — two statements about one fact
that cannot both be true.

Backdating stays allowed where the chronology rules permit it. There is no
scheduler and no pending status, so a date in the future is not a promise this
module could keep, and it says so rather than accepting one.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit, UnitStatusEvent
from app.modules.sales.models import Reservation, ReservationStatusEvent, SaleContract
from tests.modules.conftest import record_legal, sales_url


def _tomorrow() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def _counts(db: Session) -> tuple[int, int, int]:
    """Status events, unit status events and audit entries as they stand."""
    db.expire_all()
    return (
        len(db.scalars(select(ReservationStatusEvent)).all()),
        len(db.scalars(select(UnitStatusEvent)).all()),
        len(db.scalars(select(AuditEvent)).all()),
    )


def test_a_reservation_cannot_be_activated_with_a_future_effective_date(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, db: Session
) -> None:
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-1"},
    )
    before = _counts(db)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/activate",
        json={"effective_date": _tomorrow()},
    )

    assert response.status_code == 422
    assert "takes effect immediately" in response.json()["detail"]
    reservation = db.scalars(select(Reservation).where(Reservation.id == reservation_id)).one()
    assert reservation.status == "deposit_pending"
    assert _counts(db) == before


def test_a_reservation_activates_on_today(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-1"},
    )

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/activate",
        json={"effective_date": date.today().isoformat()},
    )

    assert response.status_code == 200, response.text
    assert response.json()["reservation"]["status"] == "active"


def test_a_reservation_activates_on_a_backdated_effective_date(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    """Recording on Thursday what happened on Tuesday is ordinary business."""
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-1"},
    )

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/activate",
        json={"effective_date": (date.today() - timedelta(days=2)).isoformat()},
    )

    assert response.status_code == 200, response.text
    events = response.json()["events"]
    assert events[0]["effective_date"] == (date.today() - timedelta(days=2)).isoformat()


def test_a_backdate_before_the_units_last_movement_is_still_refused(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    """Chronology outranks permission to backdate: the unit was released later."""
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-1"},
    )

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/activate",
        json={"effective_date": "2025-01-01"},
    )

    assert response.status_code == 422
    assert "cannot be dated before it" in response.json()["detail"]


def test_a_reservation_cannot_be_extended_into_a_future_effective_date(
    sales_ops_client: TestClient, project_id: str, active_reservation: str, db: Session
) -> None:
    reservation = db.scalars(select(Reservation).where(Reservation.id == active_reservation)).one()
    later = (reservation.expires_on + timedelta(days=1)).isoformat()
    before = _counts(db)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/extend",
        json={"expires_on": later, "reason": "Buyer needs longer", "effective_date": _tomorrow()},
    )

    assert response.status_code == 422
    db.expire_all()
    assert (
        db.scalars(select(Reservation).where(Reservation.id == active_reservation)).one().status
        == "active"
    )
    assert _counts(db) == before


def test_a_reservation_cannot_be_cancelled_into_a_future_effective_date(
    sales_ops_client: TestClient, project_id: str, active_reservation: str, db: Session
) -> None:
    before = _counts(db)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/cancel",
        json={"reason": "Buyer withdrew", "effective_date": _tomorrow()},
    )

    assert response.status_code == 422
    db.expire_all()
    assert (
        db.scalars(select(Reservation).where(Reservation.id == active_reservation)).one().status
        == "active"
    )
    assert _counts(db) == before


def test_a_reservation_cannot_be_expired_into_a_future_effective_date(
    sales_ops_client: TestClient, project_id: str, active_reservation: str, db: Session
) -> None:
    reservation = db.scalars(select(Reservation).where(Reservation.id == active_reservation)).one()
    reservation.reservation_date = date.today() - timedelta(days=20)
    reservation.expires_on = date.today() - timedelta(days=1)
    db.commit()
    before = _counts(db)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/expire",
        json={"effective_date": _tomorrow()},
    )

    assert response.status_code == 422
    db.expire_all()
    assert (
        db.scalars(select(Reservation).where(Reservation.id == active_reservation)).one().status
        == "active"
    )
    assert _counts(db) == before


def test_a_contract_cannot_be_submitted_with_a_future_effective_date(
    sales_ops_client: TestClient, project_id: str, sale_id: str, db: Session
) -> None:
    before = _counts(db)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/submit",
        json={"effective_date": _tomorrow()},
    )

    assert response.status_code == 422
    db.expire_all()
    assert db.scalars(select(SaleContract).where(SaleContract.id == sale_id)).one().status == (
        "draft"
    )
    assert _counts(db) == before


def test_a_contract_cannot_be_activated_with_a_future_effective_date(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    project_id: str,
    submitted_sale: str,
    released_unit: str,
    db: Session,
) -> None:
    for event_type, event_date in (
        ("spa_drafted", "2026-02-01"),
        ("spa_issued", "2026-02-02"),
        ("buyer_signed", "2026-02-03"),
        ("seller_signed", "2026-02-04"),
    ):
        record_legal(legal_client, project_id, submitted_sale, event_type, event_date)
    before = _counts(db)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/activate",
        json={"effective_date": _tomorrow()},
    )

    assert response.status_code == 422
    db.expire_all()
    sale = db.scalars(select(SaleContract).where(SaleContract.id == submitted_sale)).one()
    unit = db.scalars(select(Unit).where(Unit.id == released_unit)).one()
    assert sale.status == "signature_pending"
    assert unit.commercial_status == "contract_pending"
    assert _counts(db) == before


def test_a_cancellation_cannot_return_the_unit_on_a_future_date(
    sales_ops_client: TestClient,
    project_id: str,
    active_sale: str,
    released_unit: str,
    db: Session,
) -> None:
    case = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/cancellation",
        json={"initiated_by_party": "buyer", "reason": "Buyer could not complete"},
    ).json()
    base = f"{sales_url(project_id)}/cancellations/{case['id']}"
    sales_ops_client.post(f"{base}/advance", json={"to_status": "termination_pending_approval"})
    sales_ops_client.post(f"{base}/advance", json={"to_status": "ready_for_unit_return"})
    before = _counts(db)

    response = sales_ops_client.post(f"{base}/complete", json={"unit_return_date": _tomorrow()})

    assert response.status_code == 422
    db.expire_all()
    unit = db.scalars(select(Unit).where(Unit.id == released_unit)).one()
    assert unit.commercial_status == "contracted"
    assert unit.pricing_approved is True
    assert _counts(db) == before


def test_a_handover_cannot_be_completed_on_a_future_date(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    collections_client: TestClient,
    delivery_client: TestClient,
    project_id: str,
    active_sale: str,
    released_unit: str,
    db: Session,
) -> None:
    handover = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/handover", json={}
    )
    handover_id = handover.json()["handover"]["id"]
    for client, clearance_type in (
        (legal_client, "legal"),
        (collections_client, "collection"),
        (delivery_client, "delivery"),
    ):
        client.post(
            f"{sales_url(project_id)}/handovers/{handover_id}/clearances/{clearance_type}",
            json={"evidence_reference": "OK"},
        )
    before = _counts(db)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete",
        json={"handover_date": _tomorrow(), "acceptance_document_reference": "ACC-1"},
    )

    assert response.status_code == 422
    db.expire_all()
    assert db.scalars(select(Unit).where(Unit.id == released_unit)).one().delivery_status == (
        "not_started"
    )
    assert _counts(db) == before


def test_a_legal_event_still_refuses_its_own_future_date(
    legal_client: TestClient, project_id: str, submitted_sale: str, db: Session
) -> None:
    """The timeline had this rule already, and keeps it."""
    before = _counts(db)

    response = legal_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/legal-events",
        json={"event_type": "spa_drafted", "event_date": _tomorrow()},
    )

    assert response.status_code == 422
    assert "future" in response.json()["detail"]
    assert _counts(db) == before
