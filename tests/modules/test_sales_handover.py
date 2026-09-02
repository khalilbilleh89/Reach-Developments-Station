"""Handover: three departments' answers before anyone gets the keys.

The whole point of the gate is that one office cannot clear another's concern.
Sales Operations completes the handover and signs none of the three sign-offs;
Legal, Collections and the delivery side each answer for their own.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Unit
from tests.modules.conftest import (
    collection_account,
    collections_url,
    inventory_url,
    record_legal,
    sales_url,
    settle_and_clear_collections,
)


def _handover(client: TestClient, project_id: str, sale_id: str) -> dict:
    response = client.get(f"{sales_url(project_id)}/contracts/{sale_id}/handover")
    assert response.status_code == 200, response.text
    return response.json()


def _open(client: TestClient, project_id: str, sale_id: str) -> str:
    response = client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/handover",
        json={"scheduled_handover_date": "2026-06-01"},
    )
    assert response.status_code == 201, response.text
    return response.json()["handover"]["id"]


def _clear_all(
    legal_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    delivery_client: TestClient,
    project_id: str,
    sale_id: str,
    handover_id: str,
) -> None:
    """Open all three gates.

    Legal and delivery are still attestations and go through the generic route:
    their concerns are judgements this system holds no arithmetic for. The
    collection clearance is no longer one — from PR-MVP-07 it is checked against
    the receivables ledger — so it is granted from the Collections account,
    against a ledger that has actually been settled.
    """
    for client, clearance_type in ((legal_client, "legal"), (delivery_client, "delivery")):
        response = client.post(
            f"{sales_url(project_id)}/handovers/{handover_id}/clearances/{clearance_type}",
            json={"evidence_reference": f"{clearance_type.upper()}-OK"},
        )
        assert response.status_code == 200, response.text
    settle_and_clear_collections(collections_client, finance_client, project_id, sale_id)


def test_a_handover_starts_with_three_ungiven_clearances(
    sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    _open(sales_ops_client, project_id, active_sale)

    body = _handover(sales_ops_client, project_id, active_sale)

    assert body["handover"]["status"] == "preparation"
    assert {item["clearance_type"] for item in body["clearances"]} == {
        "legal",
        "collection",
        "delivery",
    }
    assert {item["status"] for item in body["clearances"]} == {"pending"}


def test_a_handover_needs_an_active_contract(
    sales_ops_client: TestClient, project_id: str, submitted_sale: str
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/handover", json={}
    )

    assert response.status_code == 409
    assert "active contract" in response.json()["detail"]


def test_sales_operations_cannot_sign_off_the_other_teams_concerns(
    sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    handover_id = _open(sales_ops_client, project_id, active_sale)

    for clearance_type in ("legal", "collection", "delivery"):
        response = sales_ops_client.post(
            f"{sales_url(project_id)}/handovers/{handover_id}/clearances/{clearance_type}",
            json={"evidence_reference": "Trying it on"},
        )
        assert response.status_code == 403, clearance_type


def test_collections_cannot_grant_the_legal_clearance(
    sales_ops_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    handover_id = _open(sales_ops_client, project_id, active_sale)

    response = collections_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/clearances/legal",
        json={"evidence_reference": "Not mine to give"},
    )

    assert response.status_code == 403


def test_completion_lists_everything_that_is_still_missing(
    sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    handover_id = _open(sales_ops_client, project_id, active_sale)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete", json={}
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    for expected in (
        "Legal clearance not given",
        "Collection clearance not given",
        "Delivery clearance not given",
        "Handover date not recorded",
        "Acceptance document reference not recorded",
    ):
        assert expected in detail


def test_a_handover_cannot_be_completed_by_a_patch(
    sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    handover_id = _open(sales_ops_client, project_id, active_sale)

    response = sales_ops_client.patch(
        f"{sales_url(project_id)}/handovers/{handover_id}", json={"status": "handed_over"}
    )

    assert response.status_code == 409
    assert "its own action" in response.json()["detail"]


def test_a_completed_handover_moves_the_units_delivery_status(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    collections_client: TestClient,
    delivery_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    active_sale: str,
    released_unit: str,
    finance_client: TestClient,
    active_plan: tuple[str, str],
) -> None:
    handover_id = _open(sales_ops_client, project_id, active_sale)
    _clear_all(
        legal_client,
        collections_client,
        finance_client,
        delivery_client,
        project_id,
        active_sale,
        handover_id,
    )

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete",
        json={
            "handover_date": "2026-06-01",
            "acceptance_document_reference": "ACC-2026-0001",
            "keys_reference": "KEY-101",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["handover"]["status"] == "handed_over"
    unit = admin_client.get(f"{inventory_url(project_id)}/units/{released_unit}").json()
    assert unit["delivery_status"] == "handed_over"
    # Commercial and legal are untouched: four dimensions, four answers.
    assert unit["commercial_status"] == "contracted"


def test_revoking_a_clearance_blocks_the_handover_and_keeps_the_history(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    collections_client: TestClient,
    delivery_client: TestClient,
    project_id: str,
    active_sale: str,
    finance_client: TestClient,
    active_plan: tuple[str, str],
) -> None:
    handover_id = _open(sales_ops_client, project_id, active_sale)
    _clear_all(
        legal_client,
        collections_client,
        finance_client,
        delivery_client,
        project_id,
        active_sale,
        handover_id,
    )

    # Nobody withdraws this clearance by hand any more. From PR-MVP-07 the
    # ledger withdraws it: reversing a confirmed receipt reopens the receivable,
    # and a gate that stayed open over a reopened balance is the contradiction
    # the integration exists to prevent.
    receipts = collections_client.get(
        f"{collections_url(project_id)}/sales/{active_sale}/receipts"
    ).json()
    reversed_ = finance_client.post(
        f"{collections_url(project_id)}/receipts/{receipts[0]['id']}/reverse",
        json={"reason": "Cheque returned unpaid"},
    )
    assert reversed_.status_code == 200, reversed_.text

    body = _handover(sales_ops_client, project_id, active_sale)
    statuses = [
        (item["clearance_type"], item["status"])
        for item in body["clearances"]
        if item["clearance_type"] == "collection"
    ]
    assert ("collection", "revoked") in statuses
    assert ("collection", "pending") in statuses
    assert "Collection clearance not given" in body["blockers"]


def test_a_project_may_switch_a_clearance_off_and_the_gate_follows(
    admin_client: TestClient,
    sales_ops_client: TestClient,
    legal_client: TestClient,
    delivery_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    """Five named booleans, and nothing that could express anything else."""
    policy = admin_client.put(
        f"{sales_url(project_id)}/policy",
        json={
            "handover_requires_collection_clearance": False,
            "handover_requires_legal_clearance": True,
            "handover_requires_delivery_clearance": True,
            "handover_requires_title_transfer": False,
            "title_transfer_requires_collection_clearance": True,
            "reservation_requires_deposit_confirmation": True,
        },
    )
    assert policy.status_code == 200, policy.text
    handover_id = _open(sales_ops_client, project_id, active_sale)
    for client, clearance_type in ((legal_client, "legal"), (delivery_client, "delivery")):
        client.post(
            f"{sales_url(project_id)}/handovers/{handover_id}/clearances/{clearance_type}",
            json={"evidence_reference": "OK"},
        )

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete",
        json={"handover_date": "2026-06-01", "acceptance_document_reference": "ACC-1"},
    )

    assert response.status_code == 200, response.text


def test_a_project_may_require_title_transfer_before_handover(
    admin_client: TestClient,
    sales_ops_client: TestClient,
    legal_client: TestClient,
    collections_client: TestClient,
    delivery_client: TestClient,
    project_id: str,
    active_sale: str,
    finance_client: TestClient,
    active_plan: tuple[str, str],
) -> None:
    policy = admin_client.put(
        f"{sales_url(project_id)}/policy",
        json={
            "handover_requires_collection_clearance": True,
            "handover_requires_legal_clearance": True,
            "handover_requires_delivery_clearance": True,
            "handover_requires_title_transfer": True,
            "title_transfer_requires_collection_clearance": False,
            "reservation_requires_deposit_confirmation": True,
        },
    )
    assert policy.status_code == 200, policy.text
    handover_id = _open(sales_ops_client, project_id, active_sale)
    _clear_all(
        legal_client,
        collections_client,
        finance_client,
        delivery_client,
        project_id,
        active_sale,
        handover_id,
    )

    blocked = sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete",
        json={"handover_date": "2026-06-01", "acceptance_document_reference": "ACC-1"},
    )
    assert blocked.status_code == 409
    assert "Title has not transferred" in blocked.json()["detail"]

    for event_type, event_date in (
        ("land_registry_lodged", "2026-02-10"),
        ("registered", "2026-02-20"),
        ("title_transferred", "2026-03-01"),
    ):
        record_legal(legal_client, project_id, active_sale, event_type, event_date)

    allowed = sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete",
        json={"handover_date": "2026-06-01", "acceptance_document_reference": "ACC-1"},
    )
    assert allowed.status_code == 200, allowed.text


def test_an_open_cancellation_blocks_a_handover(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    collections_client: TestClient,
    delivery_client: TestClient,
    project_id: str,
    active_sale: str,
    finance_client: TestClient,
    active_plan: tuple[str, str],
) -> None:
    handover_id = _open(sales_ops_client, project_id, active_sale)
    _clear_all(
        legal_client,
        collections_client,
        finance_client,
        delivery_client,
        project_id,
        active_sale,
        handover_id,
    )
    opened = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/cancellation",
        json={"initiated_by_party": "buyer", "reason": "Buyer could not complete"},
    )
    assert opened.status_code == 201, opened.text

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete",
        json={"handover_date": "2026-06-01", "acceptance_document_reference": "ACC-1"},
    )

    assert response.status_code == 409
    assert "cancellation case is open" in response.json()["detail"]


def test_a_handed_over_unit_cannot_then_be_taken_back_by_a_cancellation(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    collections_client: TestClient,
    delivery_client: TestClient,
    project_id: str,
    active_sale: str,
    finance_client: TestClient,
    active_plan: tuple[str, str],
) -> None:
    handover_id = _open(sales_ops_client, project_id, active_sale)
    _clear_all(
        legal_client,
        collections_client,
        finance_client,
        delivery_client,
        project_id,
        active_sale,
        handover_id,
    )
    sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete",
        json={"handover_date": "2026-06-01", "acceptance_document_reference": "ACC-1"},
    )
    case = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/cancellation",
        json={"initiated_by_party": "buyer", "reason": "Changed their mind"},
    ).json()
    base = f"{sales_url(project_id)}/cancellations/{case['id']}"
    sales_ops_client.post(f"{base}/advance", json={"to_status": "termination_pending_approval"})
    sales_ops_client.post(f"{base}/advance", json={"to_status": "ready_for_unit_return"})

    response = sales_ops_client.post(f"{base}/complete", json={})

    assert response.status_code == 409
    assert "already been handed over" in response.json()["detail"]


def test_reversing_a_receipt_after_handover_reopens_the_financial_clearance(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    collections_client: TestClient,
    delivery_client: TestClient,
    finance_client: TestClient,
    db: Session,
    project_id: str,
    active_sale: str,
    released_unit: str,
    unit_id: str,
    active_plan: tuple[str, str],
) -> None:
    """The keys stay with the buyer. The sign-off does not.

    A handover cannot be undone and this system will not pretend otherwise — the
    unit was handed over, and the delivery record says so for good. But the
    collection clearance is a statement about the ledger, and when a reversed
    receipt reopens the ledger that statement has stopped being true.

    Leaving it reading ``cleared`` is the one outcome that would let a reversal
    vanish from every screen an operator looks at. So the financial gate is
    withdrawn, with an actor, a time and a reason on it, while the handover
    itself is untouched — and no new pending clearance is queued, because a gate
    on a completed handover would read as though the unit were waiting to be
    handed over a second time.
    """
    del released_unit, active_plan
    handover_id = _open(sales_ops_client, project_id, active_sale)
    _clear_all(
        legal_client,
        collections_client,
        finance_client,
        delivery_client,
        project_id,
        active_sale,
        handover_id,
    )
    completed = sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete",
        json={
            "handover_date": "2026-06-01",
            "acceptance_document_reference": "ACC-2026-0001",
            "keys_reference": "KEY-101",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["handover"]["status"] == "handed_over"

    receipts = collections_client.get(f"{collections_url(project_id)}/sales/{active_sale}/receipts")
    assert receipts.status_code == 200, receipts.text
    receipt_id = receipts.json()[0]["id"]
    reversed_receipt = finance_client.post(
        f"{collections_url(project_id)}/receipts/{receipt_id}/reverse",
        json={"reason": "Bank returned the transfer"},
    )
    assert reversed_receipt.status_code == 200, reversed_receipt.text

    body = _handover(sales_ops_client, project_id, active_sale)
    assert body["handover"]["status"] == "handed_over"
    assert body["handover"]["handover_date"] == "2026-06-01"

    collection = [c for c in body["clearances"] if c["clearance_type"] == "collection"]
    assert len(collection) == 1, "no second pending gate on a completed handover"
    assert collection[0]["status"] == "revoked"
    assert collection[0]["revoked_at"] is not None
    assert collection[0]["revoked_by_user_id"] is not None
    assert "reopened" in collection[0]["revocation_reason"]
    # The original sign-off is preserved on the same row, not erased by it.
    assert collection[0]["cleared_by_user_id"] is not None
    assert collection[0]["evidence_reference"]

    account = collection_account(collections_client, project_id, active_sale)
    assert account["collection_clearance_status"] != "cleared"
    assert account["derived_collection_status"] != "cleared"

    db.expire_all()
    unit = db.scalars(select(Unit).where(Unit.id == unit_id)).one()
    assert unit.collection_status != "cleared"
    # Delivery is untouched: the buyer has the keys and keeps them.
    assert unit.delivery_status == "handed_over"
