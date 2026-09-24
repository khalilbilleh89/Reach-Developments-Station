"""Confirmed erasure is explicit, scoped, atomic and based on a fresh preview."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.collections.models import CollectionReceipt
from app.modules.inventory.models import Unit
from app.modules.inventory.purge import SCOPES
from app.modules.sales.models import Client, SaleContract
from tests.factories import client_for, make_user
from tests.modules.conftest import (
    PROJECTS,
    cancellation_terms_payload,
    collections_url,
    inventory_url,
    project_payload,
    sales_url,
    unit_payload,
)


@pytest.fixture
def owner(db: Session) -> TestClient:
    return client_for(make_user(db, email="purge-owner@example.com", roles=("master_admin",)).email)


def remove(owner: TestClient, project_id: str, unit_id: str) -> str:
    url = f"{inventory_url(project_id)}/units/{unit_id}"
    response = owner.delete(url, params={"reason": "Remove test history"})
    assert response.status_code == 204, response.text
    return url


def payload(owner: TestClient, url: str) -> dict:
    response = owner.get(f"{url}/purge-preview")
    assert response.status_code == 200, response.text
    preview = response.json()
    return {
        "fingerprint": preview["fingerprint"],
        "confirm_reference": preview["unit_reference"],
        "reason": "Erase confirmed test history",
        "acknowledge_history_deletion": True,
    }


def cancel(
    owner: TestClient, project_id: str, sale_id: str, approver: TestClient | None = None
) -> None:
    """Cancel a contract outright, so a purge has closed history to work on.

    The cash basis comes from the server's own preview rather than a number
    written here: opening a cancellation states what was collected, and a test
    that asserts its own figure would pass while disagreeing with the ledger.

    ``approver`` is needed only when there is confirmed cash to give back. The
    refund then has to be sanctioned before the unit may be returned, and by
    somebody other than whoever opened the case — which is the separation the
    server enforces, so it cannot be the owner passed in here.
    """
    base = sales_url(project_id)
    opened = owner.post(
        f"{base}/contracts/{sale_id}/cancellation",
        json={
            "initiated_by_party": "seller",
            "reason": "Test cleanup",
            **cancellation_terms_payload(owner, project_id, sale_id),
        },
    )
    assert opened.status_code == 201, opened.text
    case_body = opened.json()
    case = f"{base}/cancellations/{case_body['id']}"
    advanced = owner.post(f"{case}/advance", json={"to_status": "termination_pending_approval"})
    assert advanced.status_code == 200, advanced.text
    if case_body["financial_approval_required"]:
        assert approver is not None, "This contract collected cash; its refund needs a checker."
        approved = approver.post(
            f"{case}/approve-financial-terms",
            json={
                "reason": "Refund terms reviewed",
                "expected_eligible_collected_amount": case_body["eligible_collected_amount"],
            },
        )
        assert approved.status_code == 200, approved.text
    ready = owner.post(f"{case}/advance", json={"to_status": "ready_for_unit_return"})
    assert ready.status_code == 200, ready.text
    response = owner.post(f"{case}/complete", json={})
    assert response.status_code == 200, response.text


def test_purge_closed_history_frees_reference_preserves_shared_records_and_audit(
    owner: TestClient,
    project_id: str,
    unit_id: str,
    active_sale: str,
    active_plan: tuple[str, str],
    floor_id: str,
    db: Session,
) -> None:
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    buyer = sale.client_id
    cancel(owner, project_id, active_sale)
    url = remove(owner, project_id, unit_id)
    # Legacy removed rows can retain a stale commercial summary. Closed source
    # documents, not that summary, decide whether this explicit purge is allowed.
    db.expire_all()
    db.get(Unit, uuid.UUID(unit_id)).commercial_status = "contracted"
    db.commit()
    unrelated = owner.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(floor_id, unit_number="9999", unit_reference="OTHER"),
    )
    assert unrelated.status_code == 201, unrelated.text
    before_audit = set(db.scalars(select(AuditEvent.id)))
    owned_before = {
        scope.table.name: set(db.scalars(select(scope.table.c.id)))
        for scope in SCOPES
        if scope.table.name != "units"
    }
    preview = owner.get(f"{url}/purge-preview").json()
    assert not preview["blockers"], preview
    assert any(item["label"] == "Installments" for item in preview["counts"])
    assert any(
        item["kind"] == "Sale" and item["status"] == "cancelled" for item in preview["transactions"]
    )
    response = owner.post(f"{url}/purge", json=payload(owner, url))
    assert response.status_code == 204, response.text
    db.expire_all()
    assert db.get(Unit, uuid.UUID(unit_id)) is None
    assert db.get(SaleContract, uuid.UUID(active_sale)) is None
    assert db.get(Client, buyer) is not None
    assert db.get(Unit, uuid.UUID(unrelated.json()["id"])) is not None
    for scope in SCOPES:
        if scope.table.name in owned_before:
            assert not set(db.scalars(select(scope.table.c.id))) & owned_before[scope.table.name]
    assert before_audit <= set(db.scalars(select(AuditEvent.id)))
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "unit.purged"))
    assert event.entity_id == uuid.UUID(unit_id)
    assert event.before_data["counts"] == preview["counts"]
    assert event.reason == "Erase confirmed test history"
    assert owner.post(f"{url}/purge", json={**payload_from(preview)}).status_code == 404
    recreated = owner.post(f"{inventory_url(project_id)}/units", json=unit_payload(floor_id))
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["id"] != unit_id


def payload_from(preview: dict) -> dict:
    return {
        "fingerprint": preview["fingerprint"],
        "confirm_reference": preview["unit_reference"],
        "reason": "Repeat",
        "acknowledge_history_deletion": True,
    }


def test_active_sale_is_not_erased(
    owner: TestClient, project_id: str, unit_id: str, active_sale: str, db: Session
) -> None:
    url = remove(owner, project_id, unit_id)
    preview = owner.get(f"{url}/purge-preview").json()
    assert any("Sale" in message and "active" in message for message in preview["blockers"])
    response = owner.post(f"{url}/purge", json=payload(owner, url))
    assert response.status_code == 409
    assert db.get(SaleContract, uuid.UUID(active_sale)) is not None


def test_purge_confirmation_and_authorization(
    owner: TestClient,
    admin_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
) -> None:
    url = remove(owner, project_id, unit_id)
    valid = payload(owner, url)
    for client in (admin_client, advisor_client):
        assert client.get(f"{url}/purge-preview").status_code == 403
        assert client.post(f"{url}/purge", json=valid).status_code == 403
    for change in (
        {"confirm_reference": "WRONG"},
        {"reason": "   "},
        {"acknowledge_history_deletion": False},
        {"fingerprint": "invalid"},
    ):
        assert owner.post(f"{url}/purge", json={**valid, **change}).status_code == 422
    assert owner.get(f"{url}/purge-preview").status_code == 200


def test_changed_preview_and_unremoved_unit_are_blocked(
    owner: TestClient, project_id: str, unit_id: str, priced_unit: str, db: Session
) -> None:
    url = f"{inventory_url(project_id)}/units/{unit_id}"
    assert owner.get(f"{url}/purge-preview").json()["blockers"]
    assert owner.post(f"{url}/purge", json=payload(owner, url)).status_code == 409
    remove(owner, project_id, unit_id)
    old = payload(owner, url)
    db.get(Unit, uuid.UUID(unit_id)).unit_number = "CHANGED"
    db.commit()
    response = owner.post(f"{url}/purge", json=old)
    assert response.status_code == 409
    assert "changed" in response.json()["detail"]
    assert owner.get(f"{url}/purge-preview").status_code == 200


@pytest.mark.parametrize("on_delete", ["CASCADE", "SET NULL", "RESTRICT"])
def test_unknown_shared_dependency_never_cascades(
    owner: TestClient, project_id: str, unit_id: str, priced_unit: str, db: Session, on_delete: str
) -> None:
    url = remove(owner, project_id, unit_id)
    original = payload(owner, url)
    # Real PostgreSQL FK, intentionally outside the reviewed ownership map.
    db.execute(
        text(
            "CREATE TABLE purge_shared_test (id uuid PRIMARY KEY, "
            f"unit_id uuid REFERENCES units(id) ON DELETE {on_delete})"
        )
    )
    db.execute(
        text("INSERT INTO purge_shared_test VALUES (:id, :unit)"),
        {"id": uuid.uuid4(), "unit": uuid.UUID(unit_id)},
    )
    db.commit()
    try:
        preview = owner.get(f"{url}/purge-preview").json()
        assert any("outside this purge" in message for message in preview["blockers"])
        response = owner.post(f"{url}/purge", json=original)
        assert response.status_code == 409, response.text
        assert db.scalar(text("SELECT unit_id FROM purge_shared_test")) == uuid.UUID(unit_id)
        assert db.get(Unit, uuid.UUID(unit_id)) is not None
        assert not db.scalar(select(AuditEvent).where(AuditEvent.action == "unit.purged"))
    finally:
        db.execute(text("DROP TABLE purge_shared_test"))
        db.commit()


def test_reviewed_delete_order_respects_foreign_keys() -> None:
    order = {scope.table.name: index for index, scope in enumerate(SCOPES)}
    for scope in SCOPES:
        for fk in scope.table.foreign_keys:
            if fk.column.table.name in order:
                assert order[fk.column.table.name] <= order[scope.table.name]


def test_confirmed_cash_requires_reversal_before_purge(
    owner: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    active_sale: str,
    confirmed_receipt: str,
    db: Session,
) -> None:
    cancel(owner, project_id, active_sale, approver=cfo_client)
    url = remove(owner, project_id, unit_id)
    preview = owner.get(f"{url}/purge-preview").json()
    assert any("Confirmed receipt" in message for message in preview["blockers"])
    assert owner.post(f"{url}/purge", json=payload(owner, url)).status_code == 409
    assert db.get(CollectionReceipt, uuid.UUID(confirmed_receipt)) is not None
    reversed_receipt = finance_client.post(
        f"{collections_url(project_id)}/receipts/{confirmed_receipt}/reverse",
        json={"reason": "Reverse test receipt"},
    )
    assert reversed_receipt.status_code == 200, reversed_receipt.text
    response = owner.post(f"{url}/purge", json=payload(owner, url))
    assert response.status_code == 204, response.text
    db.expire_all()
    assert db.get(CollectionReceipt, uuid.UUID(confirmed_receipt)) is None


def test_other_project_cannot_preview_or_purge(
    owner: TestClient,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    url = remove(owner, project_id, unit_id)
    valid = payload(owner, url)
    created = admin_client.post(
        PROJECTS,
        json=project_payload(
            country_pack_id, currency_id, code="PURGE-OTHER", name="Other project"
        ),
    )
    assert created.status_code == 201, created.text
    other_url = f"{inventory_url(created.json()['id'])}/units/{unit_id}"
    assert owner.get(f"{other_url}/purge-preview").status_code == 404
    assert owner.post(f"{other_url}/purge", json=valid).status_code == 404
    assert owner.get(f"{url}/purge-preview").status_code == 200


def test_audit_failure_rolls_back_every_deleted_row(
    owner: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.inventory import purge

    url = remove(owner, project_id, unit_id)
    valid = payload(owner, url)
    before = {scope.table.name: set(db.scalars(select(scope.table.c.id))) for scope in SCOPES}

    def fail_audit(session: Session, **kwargs: object) -> None:
        # Real database integrity error after all DELETE statements have run.
        session.execute(text("INSERT INTO audit_events (id) VALUES (NULL)"))

    monkeypatch.setattr(purge, "record_event", fail_audit)
    response = owner.post(f"{url}/purge", json=valid)
    assert response.status_code == 409, response.text
    db.expire_all()
    for scope in SCOPES:
        assert set(db.scalars(select(scope.table.c.id))) == before[scope.table.name]
