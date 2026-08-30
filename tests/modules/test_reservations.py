"""Reservations: the first persistent commercial commitment.

A reservation freezes a quote and, once activated, holds a unit off the market.
These tests are about the three things that makes true — that the quote is
pricing's answer and not sales' arithmetic, that the commitment is exclusive,
and that nothing about either happens without a recorded reason and a recorded
actor.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Unit
from tests.modules.conftest import inventory_url, sales_url


def _detail(client: TestClient, project_id: str, reservation_id: str) -> dict:
    response = client.get(f"{sales_url(project_id)}/reservations/{reservation_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _unit(client: TestClient, project_id: str, unit_id: str) -> dict:
    return client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()


def _run_past_expiry(db: Session, reservation_id: str) -> None:
    """Put a live reservation's window in the past, as the calendar would.

    Both dates move: the table refuses an expiry before the reservation date,
    and a fixture that could produce a row the database would not accept is a
    fixture that proves nothing.
    """
    from app.modules.sales.models import Reservation

    today = date.today()
    reservation = db.scalars(select(Reservation).where(Reservation.id == reservation_id)).one()
    reservation.reservation_date = today - timedelta(days=20)
    reservation.expires_on = today - timedelta(days=1)
    db.commit()


def test_a_reservation_freezes_the_units_live_price(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, priced_unit: str
) -> None:
    """The quote comes from pricing, and the reservation stores what it said."""
    body = _detail(sales_ops_client, project_id, reservation_id)
    reservation = body["reservation"]

    assert reservation["unit_price_version_id"] == priced_unit
    assert Decimal(reservation["reference_price_ex_tax"]) > 0
    assert reservation["net_contract_price_ex_tax"] == reservation["gross_quoted_price_ex_tax"]
    assert body["quote_snapshot"]["unit_price_version_id"] == priced_unit


def test_creating_a_reservation_does_not_hold_the_unit(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    reservation_id: str,
    released_unit: str,
) -> None:
    """Preparation is not commitment: the unit is still on the market."""
    assert _unit(admin_client, project_id, released_unit)["commercial_status"] == "available"


def test_activation_commits_the_unit_and_records_the_movement(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    active_reservation: str,
    released_unit: str,
) -> None:
    body = _detail(sales_ops_client, project_id, active_reservation)

    assert body["reservation"]["status"] == "active"
    assert _unit(admin_client, project_id, released_unit)["commercial_status"] == "reserved"
    assert [event["to_status"] for event in body["events"]] == ["active"]


def test_activation_is_refused_until_the_deposit_gate_is_satisfied(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    """The project requires a deposit, so the commitment waits for the evidence."""
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/activate", json={}
    )

    assert response.status_code == 409
    assert "deposit" in response.json()["detail"].lower()


def test_a_deposit_is_confirmed_against_evidence_and_is_never_a_receipt(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-REF-9"},
    )

    assert response.status_code == 200, response.text
    reservation = response.json()["reservation"]
    assert reservation["deposit_gate_status"] == "confirmed"
    assert reservation["deposit_confirmation_reference"] == "BANK-REF-9"
    # Nothing on the reservation claims money arrived: the amount is what the
    # gate requires, not what was collected.
    assert "collected" not in str(reservation)
    assert "receipt" not in str(reservation).lower()


def test_only_the_cfo_may_waive_a_deposit(
    sales_ops_client: TestClient, cfo_client: TestClient, project_id: str, reservation_id: str
) -> None:
    base = f"{sales_url(project_id)}/reservations/{reservation_id}/waive-deposit"

    refused = sales_ops_client.post(base, json={"reason": "Long-standing client"})
    allowed = cfo_client.post(base, json={"reason": "Long-standing client"})

    assert refused.status_code == 403
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["reservation"]["deposit_gate_status"] == "waived"


def test_a_second_reservation_on_a_committed_unit_is_refused(
    sales_ops_client: TestClient,
    project_id: str,
    active_reservation: str,
    released_unit: str,
    buyer_id: str,
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={"unit_id": released_unit, "client_id": buyer_id},
    )

    assert response.status_code == 409
    assert "already holds this unit" in response.json()["detail"]


def test_a_reservation_cannot_be_activated_against_an_unavailable_unit(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    released_unit: str,
    buyer_id: str,
    reservation_id: str,
) -> None:
    """Given the unit is pulled back off the market, then the commitment is refused."""
    held = admin_client.post(
        f"{inventory_url(project_id)}/units/{released_unit}/commercial-transitions",
        json={"to_status": "held", "reason": "Structural query", "effective_date": "2026-01-03"},
    )
    assert held.status_code == 201, held.text
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-REF-2"},
    )

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/activate", json={}
    )

    assert response.status_code == 409
    assert "not available" in response.json()["detail"]


def test_buyer_shares_must_reconcile_before_a_unit_is_committed(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, buyer_id: str
) -> None:
    """Given a second buyer at half a share, then the shares total 1.5 and activation stops."""
    extra = sales_ops_client.post(
        f"{sales_url(project_id)}/clients/{buyer_id}/parties",
        json={
            "name_as_identification": "Omar Haddad",
            "share_fraction": "0.500000",
            "party_role": "joint_purchaser",
        },
    )
    assert extra.status_code == 201, extra.text
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-REF-3"},
    )

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/activate", json={}
    )

    assert response.status_code == 409
    assert "1.000000" in response.json()["detail"]


def test_share_reconciliation_is_reported_before_anyone_tries_to_commit(
    sales_ops_client: TestClient, project_id: str, buyer_id: str
) -> None:
    response = sales_ops_client.get(
        f"{sales_url(project_id)}/clients/{buyer_id}/share-reconciliation"
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"total_share_fraction": "1.000000", "reconciled": True}


def test_an_expired_reservation_must_be_closed_before_the_unit_is_reserved_again(
    sales_ops_client: TestClient,
    project_id: str,
    active_reservation: str,
    released_unit: str,
    buyer_id: str,
    db: Session,
) -> None:
    """Nothing expires a reservation on its own, so the next attempt says so."""
    _run_past_expiry(db, active_reservation)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={"unit_id": released_unit, "client_id": buyer_id},
    )

    assert response.status_code == 409
    assert "formally closed" in response.json()["detail"]


def test_a_reservation_past_its_expiry_is_shown_as_needing_closure(
    sales_ops_client: TestClient, project_id: str, active_reservation: str, db: Session
) -> None:
    _run_past_expiry(db, active_reservation)

    body = _detail(sales_ops_client, project_id, active_reservation)

    assert body["closure_required"] is True
    # Displayed, not acted on: reading the reservation changed nothing.
    assert body["reservation"]["status"] == "active"


def test_expiring_a_reservation_returns_the_unit_to_the_market(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    active_reservation: str,
    released_unit: str,
    db: Session,
) -> None:
    _run_past_expiry(db, active_reservation)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/expire", json={}
    )

    assert response.status_code == 200, response.text
    assert response.json()["reservation"]["status"] == "expired"
    assert _unit(admin_client, project_id, released_unit)["commercial_status"] == "available"


def test_a_reservation_that_has_not_expired_cannot_be_expired(
    sales_ops_client: TestClient, project_id: str, active_reservation: str
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/expire", json={}
    )

    assert response.status_code == 409
    assert "not expired" in response.json()["detail"]


def test_cancelling_a_reservation_needs_a_reason_and_releases_the_unit(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    active_reservation: str,
    released_unit: str,
) -> None:
    base = f"{sales_url(project_id)}/reservations/{active_reservation}/cancel"

    silent = sales_ops_client.post(base, json={})
    explained = sales_ops_client.post(base, json={"reason": "Buyer withdrew"})

    assert silent.status_code == 422
    assert explained.status_code == 200, explained.text
    assert explained.json()["reservation"]["status"] == "cancelled"
    assert _unit(admin_client, project_id, released_unit)["commercial_status"] == "available"


def test_a_released_unit_whose_pricing_was_withdrawn_is_held_not_offered(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    active_reservation: str,
    released_unit: str,
    db: Session,
) -> None:
    """Given the price was withdrawn while the unit was reserved, then it lands on held.

    Putting it straight back on the market would offer the next buyer a number
    nobody has re-agreed, so it goes to a state inventory owns and inventory's
    own release route is what brings it back.
    """
    unit = db.scalars(select(Unit).where(Unit.id == released_unit)).one()
    unit.pricing_approved = False
    db.commit()

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/cancel",
        json={"reason": "Buyer withdrew"},
    )

    assert response.status_code == 200, response.text
    assert _unit(admin_client, project_id, released_unit)["commercial_status"] == "held"


def test_extending_beyond_the_price_lock_is_refused_rather_than_repriced(
    sales_ops_client: TestClient, project_id: str, active_reservation: str, db: Session
) -> None:
    from app.modules.sales.models import Reservation

    reservation = db.scalars(select(Reservation).where(Reservation.id == active_reservation)).one()
    beyond_the_lock = reservation.price_locked_until + timedelta(days=1)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/extend",
        json={"expires_on": beyond_the_lock.isoformat(), "reason": "Buyer needs another week"},
    )

    assert response.status_code == 409
    assert "price lock" in response.json()["detail"]


def test_status_is_not_writable_through_the_patch_route(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    response = sales_ops_client.patch(
        f"{sales_url(project_id)}/reservations/{reservation_id}", json={"status": "active"}
    )

    assert response.status_code == 422


def test_a_reservation_has_no_delete_route(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    response = sales_ops_client.delete(f"{sales_url(project_id)}/reservations/{reservation_id}")

    # 405 where the router matches the path, 404 where the API namespace guard
    # claims it first. Either way there is no route that removes a commitment.
    assert response.status_code in {404, 405}
