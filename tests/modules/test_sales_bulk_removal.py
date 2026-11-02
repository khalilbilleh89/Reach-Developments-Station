"""Bulk removal on the Buyers, Agents and Sales registers, against disposable PostgreSQL.

Each ticked record must get exactly its single-record removal: unused buyers and
Agents go, ones with history are kept and explained, an unsigned sale closes as
cancelled with its history retained, and a refused record never blocks the rest.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access, sales_url


@pytest.fixture
def boss(db: Session) -> TestClient:
    user = make_user(db, email="sales-bulk@example.com", roles=("master_admin",))
    return client_for(user.email)


def _buyer(client: TestClient, base: str, name: str, **extra: object) -> str:
    created = client.post(f"{base}/clients", json={"display_name": name, **extra})
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _draft_sale(client: TestClient, base: str, unit_id: str, client_id: str) -> dict:
    result = client.post(
        f"{base}/buyer-registrations",
        json={"unit_id": unit_id, "client_id": client_id, "reason": "Connect selected buyer"},
    )
    assert result.status_code == 201, result.text
    return result.json()["sale"]


def _audit(db: Session, action: str, reason: str) -> int:
    return db.execute(
        text("select count(*) from audit_events where action = :a and reason = :r"),
        {"a": action, "r": reason},
    ).scalar_one()


def test_unused_buyers_go_and_a_buyer_with_a_sale_is_kept(
    boss: TestClient, db: Session, project_id: str, released_unit: str
) -> None:
    base = sales_url(project_id)
    first, second = _buyer(boss, base, "Unused One"), _buyer(boss, base, "Unused Two")
    engaged = _buyer(boss, base, "Engaged", sole_purchaser_name="Engaged")
    _draft_sale(boss, base, released_unit, engaged)
    missing = str(uuid.uuid4())

    result = boss.post(
        f"{base}/clients/bulk-delete",
        json={"ids": [first, engaged, second, missing], "reason": "Clear test buyers"},
    )

    assert result.status_code == 200, result.text
    body = result.json()
    assert body["removed"] == [first, second]
    kept = {row["id"]: row["message"] for row in body["skipped"]}
    assert set(kept) == {engaged, missing}
    assert "transaction history" in kept[engaged]
    remaining = {row["id"] for row in boss.get(f"{base}/clients").json()}
    assert engaged in remaining and not {first, second} & remaining
    assert _audit(db, "client.deleted", "Clear test buyers") == 2


def test_unused_agents_go_and_an_assigned_agent_is_kept(
    boss: TestClient, db: Session, project_id: str, operational_project: str
) -> None:
    base = sales_url(project_id)
    unused = boss.post(f"{base}/agents", json={"display_name": "Unused Agent"}).json()["id"]
    assigned = boss.post(f"{base}/agents", json={"display_name": "Assigned Agent"}).json()["id"]
    _buyer(boss, base, "Has Agent", agent_id=assigned)

    result = boss.post(
        f"{base}/agents/bulk-delete", json={"ids": [unused, assigned], "reason": "Clear roster"}
    )

    assert result.status_code == 200, result.text
    assert result.json()["removed"] == [unused]
    assert [row["id"] for row in result.json()["skipped"]] == [assigned]
    assert {row["id"] for row in boss.get(f"{base}/agents").json()} >= {assigned}
    assert boss.get(f"{base}/agents/{unused}").status_code == 404
    assert _audit(db, "sales_agent.deleted", "Clear roster") == 1


def test_an_unsigned_sale_closes_as_cancelled_and_repeats_are_reported(
    boss: TestClient, db: Session, project_id: str, released_unit: str
) -> None:
    base = sales_url(project_id)
    sale = _draft_sale(
        boss, base, released_unit, _buyer(boss, base, "Draft", sole_purchaser_name="Draft")
    )
    items = [{"kind": "sale", "id": sale["id"]}]

    first = boss.post(
        f"{base}/transactions/bulk-remove", json={"items": items, "reason": "Test sale"}
    )
    assert first.status_code == 200, first.text
    assert first.json() == {"removed": [sale["id"]], "skipped": []}
    # History is retained: the sale and its reservation remain, cancelled.
    assert boss.get(f"{base}/contracts/{sale['id']}").json()["sale"]["status"] == "cancelled"
    reservation = boss.get(f"{base}/reservations/{sale['reservation_id']}").json()
    assert reservation["reservation"]["status"] == "cancelled"
    assert _audit(db, "sale_contract.cancelled", "Test sale") == 1

    again = boss.post(
        f"{base}/transactions/bulk-remove",
        json={
            "items": [
                *items,
                {"kind": "reservation", "id": sale["reservation_id"]},
                {"kind": "sale", "id": str(uuid.uuid4())},
            ],
            "reason": "Test sale",
        },
    )
    assert again.status_code == 200, again.text
    assert again.json()["removed"] == []
    messages = [row["message"] for row in again.json()["skipped"]]
    assert messages[0] == "This sale was already removed."
    assert "live reservation" in messages[1]
    assert messages[2] == "Sale not found."
    assert _audit(db, "sale_contract.cancelled", "Test sale") == 1


def test_bulk_removal_is_role_bound_and_validated(
    boss: TestClient,
    admin_client: TestClient,
    db: Session,
    project_id: str,
    operational_project: str,
) -> None:
    base = sales_url(project_id)
    operator = make_user(db, email="sales-bulk-ops@example.com", roles=("sales_operations",))
    grant_access(admin_client, project_id, operator)
    ops = client_for(operator.email)
    buyer = _buyer(boss, base, "Protected")
    sale_item = {"kind": "sale", "id": str(uuid.uuid4())}

    assert (
        ops.post(f"{base}/clients/bulk-delete", json={"ids": [buyer], "reason": "No"}).status_code
        == 403
    )
    assert (
        ops.post(
            f"{base}/transactions/bulk-remove", json={"items": [sale_item], "reason": "No"}
        ).status_code
        == 403
    )
    assert buyer in {row["id"] for row in boss.get(f"{base}/clients").json()}

    for payload in (
        {"ids": [], "reason": "Empty"},
        {"ids": [buyer, buyer], "reason": "Twice"},
        {"ids": [str(uuid.uuid4()) for _ in range(501)], "reason": "Too many"},
        {"ids": [buyer], "reason": ""},
    ):
        assert boss.post(f"{base}/clients/bulk-delete", json=payload).status_code == 422
    assert (
        boss.post(f"{base}/clients/bulk-delete", json={"ids": [buyer], "reason": "   "}).status_code
        == 422
    )
    assert (
        boss.post(
            f"{base}/transactions/bulk-remove",
            json={"items": [sale_item, sale_item], "reason": "Twice"},
        ).status_code
        == 422
    )
