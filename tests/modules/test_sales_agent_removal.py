"""Buyer-first attribution and audited owner removal, against disposable PostgreSQL."""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.modules.sales.models import SaleContract
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, inventory_url, project_payload, sales_url

AGENT = {
    "agent_country": "Jordan",
    "agent_branch": "Amman",
    "agent_branch_leader": "Test Leader",
    "agent_name": "Test Agent",
}


@pytest.fixture
def boss(db: Session) -> TestClient:
    user = make_user(db, email="sales-removal@example.com", roles=("master_admin",))
    return client_for(user.email)


def test_buyer_team_follows_unit_and_remains_frozen(
    boss: TestClient, project_id: str, released_unit: str
) -> None:
    base = sales_url(project_id)
    buyer = boss.post(
        f"{base}/clients",
        json={"display_name": "Buyer First", "sole_purchaser_name": "Buyer First", **AGENT},
    )
    assert buyer.status_code == 201, buyer.text
    client_id = buyer.json()["id"]
    result = boss.post(
        f"{base}/buyer-registrations",
        json={"unit_id": released_unit, "client_id": client_id, "reason": "Connect selected buyer"},
    )
    assert result.status_code == 201, result.text
    sale = result.json()["sale"]
    assert {key: sale[key] for key in AGENT} == AGENT
    updated = boss.patch(
        f"{base}/clients/{client_id}",
        json={"agent_name": "Replacement Agent", "agent_branch": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["agent_branch"] is None
    frozen = boss.get(f"{base}/contracts/{sale['id']}").json()["sale"]
    assert frozen["agent_name"] == AGENT["agent_name"]
    assert frozen["agent_branch"] == AGENT["agent_branch"]


def test_master_removes_unsigned_sale_and_can_resell(
    boss: TestClient, project_id: str, released_unit: str, db: Session
) -> None:
    base = sales_url(project_id)
    payload = {
        "unit_id": released_unit,
        "buyer": {"display_name": "Test Buyer", "sole_purchaser_name": "Test Buyer"},
        "reason": "Testing",
    }
    created = boss.post(f"{base}/buyer-registrations", json=payload)
    assert created.status_code == 201, created.text
    sale = created.json()["sale"]
    removed = boss.delete(
        f"{base}/contracts/{sale['id']}", params={"reason": "Remove my test sale"}
    )
    assert removed.status_code == 204, removed.text
    assert db.get(SaleContract, uuid.UUID(sale["id"])).status == "cancelled"
    assert boss.get(f"{base}/transactions").json()["total"] == 0
    unit = boss.get(f"{inventory_url(project_id)}/units/{released_unit}").json()
    assert unit["commercial_status"] == "available"
    again = boss.delete(f"{base}/contracts/{sale['id']}", params={"reason": "Retry"})
    assert again.status_code == 204
    new_sale = boss.post(
        f"{base}/buyer-registrations",
        json={
            "unit_id": released_unit,
            "client_id": sale["client_id"],
            "reason": "Retest same unit",
        },
    )
    assert new_sale.status_code == 201, new_sale.text
    assert new_sale.json()["sale"]["id"] != sale["id"]
    repeat = boss.delete(f"{base}/contracts/{sale['id']}", params={"reason": "Late retry"})
    assert repeat.status_code == 204
    assert (
        boss.get(f"{inventory_url(project_id)}/units/{released_unit}").json()["commercial_status"]
        == "contract_pending"
    )
    event = db.execute(
        text(
            "SELECT reason FROM audit_events WHERE entity_id = :id "
            "AND action = 'sale_contract.cancelled'"
        ),
        {"id": sale["id"]},
    ).scalar_one()
    assert event == "Remove my test sale"


def test_removal_rejects_non_master_and_blank_reason(
    boss: TestClient,
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    submitted_sale: str,
) -> None:
    url = f"{sales_url(project_id)}/contracts/{submitted_sale}"
    for actor in (sales_ops_client, admin_client):
        response = actor.delete(url, params={"reason": "Testing"})
        assert response.status_code == 403, response.text
    response = boss.delete(url, params={"reason": "   "})
    assert response.status_code == 422, response.text
    assert boss.get(url).json()["sale"]["status"] == "signature_pending"


def test_signed_sale_keeps_governed_cancellation(
    boss: TestClient, project_id: str, active_sale: str
) -> None:
    url = f"{sales_url(project_id)}/contracts/{active_sale}"
    response = boss.delete(url, params={"reason": "Mistaken entry"})
    assert response.status_code == 409, response.text
    assert boss.get(url).json()["sale"]["status"] == "active"


def test_draft_sale_can_be_removed(boss: TestClient, project_id: str, sale_id: str) -> None:
    url = f"{sales_url(project_id)}/contracts/{sale_id}"
    response = boss.delete(url, params={"reason": "Abandon test draft"})
    assert response.status_code == 204, response.text
    assert boss.get(url).json()["sale"]["status"] == "cancelled"


def test_preparing_reservation_can_be_removed(
    boss: TestClient,
    project_id: str,
    reservation_id: str,
    released_unit: str,
) -> None:
    base = sales_url(project_id)
    response = boss.post(
        f"{base}/reservations/{reservation_id}/cancel", json={"reason": "Discard draft"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["reservation"]["status"] == "cancelled"
    assert (
        boss.get(f"{inventory_url(project_id)}/units/{released_unit}").json()["commercial_status"]
        == "available"
    )


def test_cancelling_reservation_closes_its_draft_contract(
    boss: TestClient,
    project_id: str,
    sale_id: str,
) -> None:
    base = sales_url(project_id)
    sale = boss.get(f"{base}/contracts/{sale_id}").json()["sale"]
    closed = boss.post(
        f"{base}/reservations/{sale['reservation_id']}/cancel",
        json={"reason": "Cancel draft preparation"},
    )
    assert closed.status_code == 200, closed.text
    assert boss.get(f"{base}/contracts/{sale_id}").json()["sale"]["status"] == "cancelled"
    assert boss.get(f"{base}/transactions").json()["total"] == 0


def test_agent_migration_round_trip(postgres: None) -> None:
    config = alembic_config()
    try:
        command.downgrade(config, "0024_merge_permits_inventory")
        for table in ("clients", "reservations", "sale_contracts"):
            assert not set(AGENT) & {
                column["name"] for column in inspect(get_engine()).get_columns(table)
            }
        command.upgrade(config, "head")
        for table in ("clients", "reservations", "sale_contracts"):
            columns = {
                column["name"]: column for column in inspect(get_engine()).get_columns(table)
            }
            assert all(columns[name]["nullable"] for name in AGENT)
    finally:
        command.upgrade(config, "head")


def test_agent_correction_changes_only_selected_sale(
    boss: TestClient, project_id: str, submitted_sale: str, admin_client: TestClient
) -> None:
    base = f"{sales_url(project_id)}/contracts/{submitted_sale}"
    before = boss.get(base).json()["sale"]
    result = boss.put(f"{base}/agent", json={**AGENT, "reason": "Fill historical attribution"})
    assert result.status_code == 200, result.text
    after = boss.get(base).json()["sale"]
    assert {key: after[key] for key in AGENT} == AGENT
    for key in ("status", "client_id", "unit_id", "total_contract_price", "reservation_id"):
        assert after[key] == before[key]
    denied = admin_client.put(f"{base}/agent", json={**AGENT, "reason": "Not my authority"})
    assert denied.status_code == 403, denied.text
    invalid = boss.put(f"{base}/agent", json={**AGENT, "reason": " "})
    assert invalid.status_code == 422, invalid.text


def test_wrong_project_cannot_remove_or_correct_sale(
    boss: TestClient,
    admin_client: TestClient,
    country_pack_id: str,
    currency_id: str,
    project_id: str,
    submitted_sale: str,
) -> None:
    other = admin_client.post(
        PROJECTS,
        json=project_payload(
            country_pack_id, currency_id, code="OTHER-AGENT", name="Other sales project"
        ),
    )
    assert other.status_code == 201, other.text
    url = f"{sales_url(other.json()['id'])}/contracts/{submitted_sale}"
    assert boss.delete(url, params={"reason": "Wrong scope"}).status_code == 404
    assert boss.put(f"{url}/agent", json={**AGENT, "reason": "Wrong scope"}).status_code == 404
    assert (
        boss.get(f"{sales_url(project_id)}/contracts/{submitted_sale}").json()["sale"]["status"]
        == "signature_pending"
    )


def test_master_can_complete_signed_sale_cancellation(
    boss: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    base = sales_url(project_id)
    result = boss.post(
        f"{base}/contracts/{active_sale}/cancellation",
        json={"initiated_by_party": "seller", "reason": "Cancel signed test transaction"},
    )
    assert result.status_code == 201, result.text
    case_id = result.json()["id"]
    for status in ("termination_pending_approval", "ready_for_unit_return"):
        step = boss.post(f"{base}/cancellations/{case_id}/advance", json={"to_status": status})
        assert step.status_code == 200, step.text
    completed = boss.post(f"{base}/cancellations/{case_id}/complete", json={})
    assert completed.status_code == 200, completed.text
    assert boss.get(f"{base}/contracts/{active_sale}").json()["sale"]["status"] == "cancelled"
