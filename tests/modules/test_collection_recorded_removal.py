"""Unconfirmed claims can be removed without authority to reverse actual cash."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from tests.modules.conftest import (
    PROJECTS,
    allocate,
    collection_account,
    collections_url,
    governing_installments,
    grant_access,
    project_payload,
    record_receipt,
)
from tests.modules.test_collection_refunds import cancelled_sale as cancelled_sale


def record(client: TestClient, project_id: str, sale: tuple[str, str], kind: str) -> dict:
    sale_id, cancellation_id = sale
    response = (
        record_receipt(client, project_id, sale_id, "100.00")
        if kind == "receipt"
        else client.post(
            f"{collections_url(project_id)}/sales/{sale_id}/refunds",
            json={
                "cancellation_id": cancellation_id,
                "amount": "100.00",
                "refund_date": "2026-06-01",
            },
        )
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("kind", ["receipt", "refund"])
def test_void_enforces_roles_scope_reason_and_retains_audit_without_cash(
    kind: str,
    collections_client: TestClient,
    finance_client: TestClient,
    admin_client: TestClient,
    auditor_client: TestClient,
    collections_officer: User,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
    cancelled_sale: tuple[str, str],
    db: Session,
) -> None:
    row = record(collections_client, project_id, cancelled_sale, kind)
    base = f"{collections_url(project_id)}/{kind}s/{row['id']}"
    body = {"reason": "Duplicate unconfirmed entry"}
    before = collection_account(collections_client, project_id, cancelled_sale[0])
    historical = collection_account(
        collections_client, project_id, cancelled_sale[0], as_of="2026-07-01"
    )
    for denied in (finance_client, admin_client, auditor_client):
        assert denied.post(base + "/void", json=body).status_code == 403
    for blank in ("", " \t\n"):
        assert collections_client.post(base + "/void", json={"reason": blank}).status_code == 422
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER-VOID")
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]
    grant_access(admin_client, other_id, collections_officer)
    assert (
        collections_client.post(
            f"{collections_url(other_id)}/{kind}s/{row['id']}/void",
            json=body,
        ).status_code
        == 404
    )
    assert (
        collections_client.post(
            f"{collections_url(project_id)}/{kind}s/{uuid.uuid4()}/void",
            json=body,
        ).status_code
        == 404
    )
    scope = f"{PROJECTS}/{project_id}/access/{collections_officer.id}/phase-scope"
    assert admin_client.patch(scope, json={"phase_scope": "selected"}).status_code == 200
    assert collections_client.post(base + "/void", json=body).status_code == 404
    assert admin_client.patch(scope, json={"phase_scope": "all"}).status_code == 200

    removed = collections_client.post(base + "/void", json=body)
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "reversed"
    assert removed.json()["confirmed_at"] is None
    assert removed.json()["reversal_reason"] == body["reason"]
    assert collections_client.post(base + "/void", json=body).status_code == 409
    assert finance_client.post(base + "/confirm", json={}).status_code == 409
    listing = collections_client.get(
        f"{collections_url(project_id)}/sales/{cancelled_sale[0]}/{kind}s"
    )
    assert listing.status_code == 200
    assert any(item["id"] == row["id"] and item["status"] == "reversed" for item in listing.json())
    after = collection_account(collections_client, project_id, cancelled_sale[0])
    for key in (
        "confirmed_receipts_total",
        "allocated_total",
        "unapplied_cash",
        "outstanding_total",
        "refund_due_total",
        "refund_confirmed_total",
        "refund_outstanding",
    ):
        assert after[key] == before[key], key
    assert (
        collection_account(collections_client, project_id, cancelled_sale[0], as_of="2026-07-01")
        == historical
    )
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity_id == uuid.UUID(row["id"]),
            AuditEvent.action == f"collections.{kind}_voided",
        )
    ).all()
    assert len(events) == 1
    assert events[0].actor_user_id == collections_officer.id
    assert events[0].reason == body["reason"]
    assert events[0].before_data["status"] == "recorded"
    assert events[0].after_data["status"] == "reversed"


@pytest.mark.parametrize("kind", ["receipt", "refund"])
def test_confirmed_cash_cannot_be_voided_or_reversed_by_collections(
    kind: str,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    cancelled_sale: tuple[str, str],
) -> None:
    row = record(collections_client, project_id, cancelled_sale, kind)
    base = f"{collections_url(project_id)}/{kind}s/{row['id']}"
    body = {"reason": "Wrong entry"}
    assert finance_client.post(base + "/reverse", json=body).status_code == 409
    assert finance_client.post(base + "/confirm", json={}).status_code == 200
    refused = collections_client.post(base + "/void", json=body)
    assert refused.status_code == 409
    assert "Finance" in refused.json()["detail"]
    assert collections_client.post(base + "/reverse", json=body).status_code == 403
    assert finance_client.post(base + "/reverse", json=body).status_code == 200


def test_active_allocations_block_removal_until_explicitly_reversed(
    collections_client: TestClient,
    project_id: str,
    cancelled_sale: tuple[str, str],
) -> None:
    row = record(collections_client, project_id, cancelled_sale, "receipt")
    installment = governing_installments(collections_client, project_id, cancelled_sale[0])[0]
    created = allocate(
        collections_client, project_id, row["id"], installment["installment_id"], "10.00"
    )
    assert created.status_code == 201, created.text
    base = f"{collections_url(project_id)}/receipts/{row['id']}"
    body = {"reason": "Duplicate entry"}
    refused = collections_client.post(base + "/void", json=body)
    assert refused.status_code == 409
    assert "active allocations" in refused.json()["detail"]
    receipt = collections_client.get(base).json()
    assert receipt["status"] == "recorded"
    assert receipt["allocations"][0]["status"] == "active"
    reversed_allocation = collections_client.post(
        f"{collections_url(project_id)}/allocations/{created.json()['id']}/reverse",
        json=body,
    )
    assert reversed_allocation.status_code == 200, reversed_allocation.text
    removed = collections_client.post(base + "/void", json=body)
    assert removed.status_code == 200, removed.text
    assert removed.json()["allocations"][0]["status"] == "reversed"
    assert removed.json()["counts_as_cash"] is False


@pytest.mark.parametrize("kind", ["receipt", "refund"])
def test_confirmation_racing_void_has_one_winner(
    kind: str,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    cancelled_sale: tuple[str, str],
    db: Session,
) -> None:
    row = record(collections_client, project_id, cancelled_sale, kind)
    base = f"{collections_url(project_id)}/{kind}s/{row['id']}"
    barrier = Barrier(2)
    db.rollback()

    def remove() -> int:
        barrier.wait(timeout=10)
        return collections_client.post(base + "/void", json={"reason": "Duplicate"}).status_code

    def confirm() -> int:
        barrier.wait(timeout=10)
        return finance_client.post(base + "/confirm", json={}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        removal = pool.submit(remove)
        confirmation = pool.submit(confirm)
        outcomes = [removal.result(timeout=30), confirmation.result(timeout=30)]
    assert sorted(outcomes) == [200, 409]
    rows = collections_client.get(
        f"{collections_url(project_id)}/sales/{cancelled_sale[0]}/{kind}s"
    ).json()
    final = next(item for item in rows if item["id"] == row["id"])
    assert final["status"] == ("reversed" if outcomes[0] == 200 else "confirmed")
    assert (final["confirmed_at"] is None) == (outcomes[0] == 200)


def test_refund_can_be_removed_after_cancellation_is_withdrawn(
    collections_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    cancelled_sale: tuple[str, str],
) -> None:
    row = record(collections_client, project_id, cancelled_sale, "refund")
    withdrawn = sales_ops_client.post(
        f"{PROJECTS}/{project_id}/sales/cancellations/{cancelled_sale[1]}/advance",
        json={"to_status": "withdrawn", "reason": "The parties settled"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    account = collection_account(collections_client, project_id, cancelled_sale[0])
    assert account["refund_due_total"] == "0.00"
    removed = collections_client.post(
        f"{collections_url(project_id)}/refunds/{row['id']}/void",
        json={"reason": "Repayment no longer needed"},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["confirmed_at"] is None
    assert removed.json()["status"] == "reversed"
