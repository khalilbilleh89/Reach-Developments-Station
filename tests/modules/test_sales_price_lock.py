"""The price lock: what a frozen price survives, and what it does not.

A price lock is a promise. For its term this buyer pays this number, and Finance
putting a new list price live the following Wednesday does not change that —
that is commercial repricing, and it decides what the unit is offered at
tomorrow rather than what somebody already agreed yesterday.

What the lock is not is permission to sell a different flat. If the unit's
measured basis moves, the frozen price stops describing the thing being sold and
the contract has to wait for a new quote.

And a lock that has run out is a real, otherwise unresolvable position: the
reservation still holds the unit and no contract can be drawn up. The explicit
re-quote is the way through, on the record, with a reason.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.sales.models import Reservation
from tests.modules.conftest import (
    SETTINGS,
    approve_areas,
    inventory_url,
    pricing_url,
    sales_url,
)


def _replace_list_price(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    *,
    reason: str = "Launch escalation",
) -> str:
    """Put a new list price live on a unit the governed way, and return its id."""
    draft = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions",
        json={"change_reason": reason},
    )
    assert draft.status_code == 201, draft.text
    version_id = draft.json()["id"]
    base = f"{pricing_url(project_id)}/price-versions/{version_id}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})
    assert approved.status_code == 200, approved.text
    activated = cfo_client.post(f"{base}/activate")
    assert activated.status_code == 200, activated.text
    return version_id


def _expire_lock(db: Session, reservation_id: str) -> None:
    """Run the price lock out while leaving the reservation itself in force."""
    reservation = db.scalars(select(Reservation).where(Reservation.id == reservation_id)).one()
    reservation.reservation_date = date.today() - timedelta(days=60)
    reservation.price_locked_until = date.today() - timedelta(days=1)
    db.commit()


def test_a_new_list_price_does_not_void_a_locked_reservation(
    sales_ops_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    released_unit: str,
    active_reservation: str,
    priced_unit: str,
) -> None:
    """Given a replacement list price, then the locked reservation still sells."""
    reservation = sales_ops_client.get(
        f"{sales_url(project_id)}/reservations/{active_reservation}"
    ).json()["reservation"]
    replacement = _replace_list_price(finance_client, cfo_client, project_id, released_unit)
    assert replacement != priced_unit

    created = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": active_reservation}
    )
    assert created.status_code == 201, created.text
    sale_id = created.json()["sale"]["id"]
    submitted = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={}
    )

    assert submitted.status_code == 200, submitted.text
    sale = submitted.json()["sale"]
    # The contract is on the version the buyer agreed, not the one that has
    # since replaced it on the list.
    assert sale["unit_price_version_id"] == reservation["unit_price_version_id"]
    assert sale["unit_price_version_id"] != replacement
    assert sale["net_contract_price_ex_tax"] == reservation["net_contract_price_ex_tax"]


def test_the_replacement_price_remains_the_units_public_list_price(
    sales_ops_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    released_unit: str,
    active_reservation: str,
) -> None:
    """Nothing in pricing is rewritten to make the contract work."""
    replacement = _replace_list_price(finance_client, cfo_client, project_id, released_unit)
    created = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": active_reservation}
    )
    sale_id = created.json()["sale"]["id"]
    sales_ops_client.post(f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={})

    pricing = finance_client.get(f"{pricing_url(project_id)}/units/{released_unit}").json()

    assert pricing["active_price"]["id"] == replacement
    statuses = {version["id"]: version["status"] for version in pricing["history"]}
    assert statuses[replacement] == "active"
    # The version the contract sits on is superseded, and still readable.
    contracted = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{sale_id}").json()[
        "sale"
    ]["unit_price_version_id"]
    assert statuses[contracted] == "superseded"


def test_a_changed_unit_basis_still_blocks_the_contract(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    released_unit: str,
    active_reservation: str,
    area_types: dict[str, str],
) -> None:
    """A locked price is not permission to sell a materially different flat."""
    approve_areas(
        admin_client,
        project_id,
        released_unit,
        area_types,
        internal="140.0000",
        revision="R1",
    )

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": active_reservation}
    )

    assert response.status_code == 409
    assert "changed since the reservation was quoted" in response.json()["detail"]


def test_a_changed_unit_basis_blocks_submission_of_a_contract_already_drafted(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    released_unit: str,
    active_reservation: str,
    sale_id: str,
    area_types: dict[str, str],
) -> None:
    approve_areas(
        admin_client,
        project_id,
        released_unit,
        area_types,
        internal="140.0000",
        revision="R1",
    )

    response = sales_ops_client.post(f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={})

    assert response.status_code == 409
    assert "changed since the reservation was quoted" in response.json()["detail"]


def test_an_expired_price_lock_refuses_the_contract(
    sales_ops_client: TestClient, project_id: str, active_reservation: str, db: Session
) -> None:
    """And says what to do about it, rather than quietly repricing the buyer."""
    _expire_lock(db, active_reservation)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": active_reservation}
    )

    assert response.status_code == 409
    assert "price lock" in response.json()["detail"]
    assert "Re-quote" in response.json()["detail"]


def test_an_expired_price_lock_refuses_submission_of_an_existing_draft(
    sales_ops_client: TestClient,
    project_id: str,
    active_reservation: str,
    sale_id: str,
    db: Session,
) -> None:
    _expire_lock(db, active_reservation)

    response = sales_ops_client.post(f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={})

    assert response.status_code == 409
    assert "price lock" in response.json()["detail"]


def test_activation_still_refuses_a_reservation_quoted_from_a_superseded_price(
    sales_ops_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    released_unit: str,
    reservation_id: str,
) -> None:
    """The strong rule survives: nothing is committed on a price nobody offers."""
    _replace_list_price(finance_client, cfo_client, project_id, released_unit)
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-1"},
    )

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/activate", json={}
    )

    assert response.status_code == 409
    assert "price has changed" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# The controlled re-quote
# --------------------------------------------------------------------------- #


def test_an_expired_lock_can_be_requoted_without_releasing_the_unit(
    sales_ops_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    released_unit: str,
    active_reservation: str,
    db: Session,
) -> None:
    """The way out of the dead end: a new quote, a new lock, the same commitment."""
    replacement = _replace_list_price(finance_client, cfo_client, project_id, released_unit)
    _expire_lock(db, active_reservation)
    base = f"{sales_url(project_id)}/reservations/{active_reservation}"

    blocked = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": active_reservation}
    )
    assert blocked.status_code == 409

    response = sales_ops_client.post(
        f"{base}/requote", json={"reason": "Lock expired while the buyer arranged finance"}
    )

    assert response.status_code == 200, response.text
    reservation = response.json()["reservation"]
    assert reservation["status"] == "active"
    assert reservation["unit_price_version_id"] == replacement
    assert reservation["price_locked_until"] >= date.today().isoformat()
    unit = sales_ops_client.get(f"{inventory_url(project_id)}/units/{released_unit}").json()
    assert unit["commercial_status"] == "reserved"

    proceeds = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": active_reservation}
    )
    assert proceeds.status_code == 201, proceeds.text
    assert proceeds.json()["sale"]["unit_price_version_id"] == replacement


def test_a_requote_needs_a_reason(
    sales_ops_client: TestClient, project_id: str, active_reservation: str
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/requote", json={}
    )

    assert response.status_code == 422


def test_a_requote_is_recorded_with_its_reason_and_its_actor(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    active_reservation: str,
    sales_ops: object,
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/requote",
        json={"reason": "Buyer returned after the lock ran out"},
    )
    assert response.status_code == 200, response.text

    events = admin_client.get(
        "/api/v1/audit-events", params={"action": "reservation.requoted"}
    ).json()

    assert events["total"] == 1
    entry = events["items"][0]
    assert entry["reason"] == "Buyer returned after the lock ran out"
    assert entry["actor_user_id"] == str(sales_ops.id)


def test_a_requote_that_breaches_a_threshold_needs_approving_again(
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    country_pack_id: str,
    reservation_id: str,
) -> None:
    """An exception approved against last month's number says nothing about this one."""
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    sales_ops_client.post(
        f"{base}/adjustments",
        json={"adjustment_type": "fixed_discount", "amount": "5000.00"},
    )
    sales_ops_client.post(f"{base}/confirm-deposit", json={"evidence_reference": "BANK-1"})
    activated = sales_ops_client.post(f"{base}/activate", json={})
    assert activated.status_code == 200, activated.text
    assert activated.json()["reservation"]["exception_approval_status"] == "not_required"

    # The country tightens its review limit after the unit was committed.
    thresholds = admin_client.put(
        f"{SETTINGS}/country-packs/{country_pack_id}/approval-thresholds",
        json={
            "discount_review_amount": "1.00",
            "pricing_requires_commercial_approval": True,
        },
    )
    assert thresholds.status_code == 200, thresholds.text

    requoted = sales_ops_client.post(f"{base}/requote", json={"reason": "Lock ran out"})
    assert requoted.status_code == 200, requoted.text
    reservation = requoted.json()["reservation"]
    assert reservation["exception_approval_required"] is True
    assert reservation["exception_approval_status"] == "pending"
    assert reservation["exception_approved_by_user_id"] is None

    blocked = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": reservation_id}
    )
    assert blocked.status_code == 409
    assert "has not been approved" in blocked.json()["detail"]

    submitted = sales_ops_client.post(
        f"{base}/submit-exception", json={"reason": "Matching a competing scheme"}
    )
    assert submitted.status_code == 200, submitted.text
    refused_by_maker = sales_ops_client.post(
        f"{base}/approve-exception", json={"approved": True, "reason": "Mine to sign"}
    )
    assert refused_by_maker.status_code == 403
    approved = cfo_client.post(
        f"{base}/approve-exception", json={"approved": True, "reason": "Accepted"}
    )
    assert approved.status_code == 200, approved.text

    proceeds = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": reservation_id}
    )
    assert proceeds.status_code == 201, proceeds.text


def test_an_administrator_cannot_approve_a_requoted_exception_either(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    country_pack_id: str,
    reservation_id: str,
) -> None:
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    sales_ops_client.post(
        f"{base}/adjustments",
        json={"adjustment_type": "fixed_discount", "amount": "5000.00"},
    )
    sales_ops_client.post(f"{base}/confirm-deposit", json={"evidence_reference": "BANK-1"})
    sales_ops_client.post(f"{base}/activate", json={})
    admin_client.put(
        f"{SETTINGS}/country-packs/{country_pack_id}/approval-thresholds",
        json={
            "discount_review_amount": "1.00",
            "pricing_requires_commercial_approval": True,
        },
    )
    sales_ops_client.post(f"{base}/requote", json={"reason": "Lock ran out"})
    sales_ops_client.post(f"{base}/submit-exception", json={"reason": "Competing scheme"})

    response = admin_client.post(
        f"{base}/approve-exception",
        json={"approved": True, "reason": "Administrator override"},
    )

    assert response.status_code == 403


def test_a_requote_within_the_thresholds_needs_no_approval(
    sales_ops_client: TestClient, project_id: str, active_reservation: str
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/requote",
        json={"reason": "Lock ran out"},
    )

    assert response.status_code == 200, response.text
    reservation = response.json()["reservation"]
    assert reservation["exception_approval_required"] is False
    assert reservation["exception_approval_status"] == "not_required"


def test_a_requote_refreshes_a_draft_contract_already_drawn_from_it(
    sales_ops_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    released_unit: str,
    active_reservation: str,
    sale_id: str,
    db: Session,
) -> None:
    """A draft holds nothing, so it follows the reservation rather than stranding it."""
    replacement = _replace_list_price(finance_client, cfo_client, project_id, released_unit)
    _expire_lock(db, active_reservation)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/requote",
        json={"reason": "Lock ran out with the contract still in draft"},
    )
    assert response.status_code == 200, response.text

    sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{sale_id}").json()["sale"]
    assert sale["unit_price_version_id"] == replacement
    reservation = response.json()["reservation"]
    assert sale["net_contract_price_ex_tax"] == reservation["net_contract_price_ex_tax"]

    submitted = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={}
    )
    assert submitted.status_code == 200, submitted.text


def test_a_requote_is_refused_once_a_contract_has_taken_the_commitment(
    sales_ops_client: TestClient, project_id: str, active_reservation: str, submitted_sale: str
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/requote",
        json={"reason": "Too late"},
    )

    assert response.status_code == 409
    assert "Only a live reservation can be re-quoted." in response.json()["detail"]


def test_a_reservation_in_preparation_is_not_requoted(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    """It has the ordinary recalculate route; re-quote is for a live commitment."""
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/requote",
        json={"reason": "Wrong route"},
    )

    assert response.status_code == 409
    assert "Only a live reservation can be re-quoted." in response.json()["detail"]


def test_a_live_reservations_adjustments_are_still_frozen(
    sales_ops_client: TestClient, project_id: str, active_reservation: str
) -> None:
    """Re-quote is the only route to a committed reservation's commercial terms."""
    adjustment = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/adjustments",
        json={"adjustment_type": "fixed_discount", "amount": "1000.00"},
    )
    recalculate = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/recalculate", json={}
    )

    assert adjustment.status_code == 409
    assert recalculate.status_code == 409
    assert "no longer in preparation" in recalculate.json()["detail"]


def test_a_requote_leaves_the_price_versions_alone(
    sales_ops_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    released_unit: str,
    active_reservation: str,
    priced_unit: str,
) -> None:
    replacement = _replace_list_price(finance_client, cfo_client, project_id, released_unit)

    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{active_reservation}/requote",
        json={"reason": "Aligning with the new list price"},
    )

    pricing = finance_client.get(f"{pricing_url(project_id)}/units/{released_unit}").json()
    statuses = {version["id"]: version["status"] for version in pricing["history"]}
    assert statuses[replacement] == "active"
    assert statuses[priced_unit] == "superseded"
    assert len(pricing["history"]) == 2


@pytest.mark.parametrize("adjustment_amount", ["2500.00"])
def test_a_requote_re_runs_the_reservations_own_recorded_inputs(
    sales_ops_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    released_unit: str,
    reservation_id: str,
    adjustment_amount: str,
) -> None:
    """The concession the buyer was given follows them onto the new price."""
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/adjustments",
        json={"adjustment_type": "fixed_discount", "amount": adjustment_amount},
    )
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-1"},
    )
    activated = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/activate", json={}
    )
    assert activated.status_code == 200, activated.text
    _replace_list_price(finance_client, cfo_client, project_id, released_unit)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/requote",
        json={"reason": "New list price"},
    )

    assert response.status_code == 200, response.text
    reservation = response.json()["reservation"]
    assert reservation["cash_discount_amount"] == adjustment_amount
    assert Decimal(reservation["net_contract_price_ex_tax"]) == Decimal(
        reservation["gross_quoted_price_ex_tax"]
    ) - Decimal(adjustment_amount)
