"""A hidden retained unit can be recovered; permanent deletion never silently hides it."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Building, Floor, Phase, Unit, UnitAreaSchedule
from app.modules.sales.models import SaleContract
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, inventory_url, project_payload, sales_url, unit_payload


@pytest.fixture
def owner(db: Session) -> TestClient:
    return client_for(
        make_user(db, email="recover-unit@example.com", roles=("master_admin",)).email
    )


def test_removed_priced_unit_is_discoverable_and_restorable_with_its_identity(
    owner: TestClient, project_id: str, unit_id: str, priced_unit: str, db: Session
) -> None:
    base = inventory_url(project_id)
    url = f"{base}/units/{unit_id}"
    before = owner.get(url).json()
    measurements = list(db.scalars(select(UnitAreaSchedule.id)))
    assert owner.delete(url, params={"reason": "Duplicate"}).status_code == 204
    assert owner.get(url).status_code == 404
    assert not owner.get(f"{base}/units", params={"is_active": False}).json()["units"]
    duplicate = owner.post(f"{base}/units", json=unit_payload(before["floor_id"]))
    assert duplicate.status_code == 409
    assert "Removed units" in duplicate.json()["detail"]
    found = owner.get(f"{base}/removed-units", params={"search": before["unit_number"]})
    assert found.status_code == 200, found.text
    assert [row["id"] for row in found.json()] == [unit_id]
    assert found.json()[0]["floor_code"]
    assert owner.get(f"{base}/removed-units", params={"search": "nonexistent"}).json() == []
    assert owner.get(f"{base}/removed-units", params={"offset": 1, "limit": 1}).json() == []
    restored = owner.post(f"{url}/restoration", json={"reason": "Recover original unit"})
    assert restored.status_code == 200, restored.text
    for key in ("id", "floor_id", "unit_reference", "unit_number", "commercial_status"):
        assert restored.json()[key] == before[key]
    assert restored.json()["is_active"] is True
    assert owner.get(f"{base}/removed-units").json() == []
    assert unit_id in [row["id"] for row in owner.get(f"{base}/units").json()["units"]]
    assert owner.post(f"{url}/restoration", json={"reason": "Retry"}).status_code == 200
    db.expire_all()
    assert db.get(Unit, uuid.UUID(unit_id)).removed_at is None
    assert list(db.scalars(select(UnitAreaSchedule.id))) == measurements
    events = list(db.scalars(select(AuditEvent).where(AuditEvent.action == "unit.restored")))
    assert len(events) == 1
    assert events[0].reason == "Recover original unit"
    assert events[0].entity_id == uuid.UUID(unit_id)
    assert events[0].before_data["removed_at"]
    assert owner.delete(url, params={"reason": "Remove again"}).status_code == 204


def test_restoration_preserves_sale_and_returns_it_to_current_sales(
    owner: TestClient, project_id: str, active_sale: str, db: Session
) -> None:
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    before = (sale.status, sale.total_contract_price, sale.unit_id)
    url = f"{inventory_url(project_id)}/units/{sale.unit_id}"
    assert owner.delete(url, params={"reason": "Accidental removal"}).status_code == 204
    assert owner.post(f"{url}/restoration", json={"reason": "Correct removal"}).status_code == 200
    db.expire_all()
    assert (sale.status, sale.total_contract_price, sale.unit_id) == before
    transactions = owner.get(f"{sales_url(project_id)}/transactions").json()["items"]
    assert active_sale in [row["id"] for row in transactions]


def test_recovery_authorization_and_project_isolation(
    owner: TestClient,
    admin_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    base = inventory_url(project_id)
    url = f"{base}/units/{unit_id}"
    assert owner.delete(url, params={"reason": "Remove"}).status_code == 204
    for client in (admin_client, advisor_client):
        assert client.get(f"{base}/removed-units").status_code == 403
        assert client.post(f"{url}/restoration", json={"reason": "Restore"}).status_code == 403
        assert client.delete(url, params={"reason": "Purge", "permanent": True}).status_code == 403
    other = admin_client.post(
        PROJECTS,
        json=project_payload(
            country_pack_id, currency_id, code="RECOVERY-OTHER", name="Other project"
        ),
    ).json()["id"]
    assert owner.get(f"{inventory_url(other)}/removed-units").json() == []
    other_url = f"{inventory_url(other)}/units/{unit_id}"
    assert owner.post(f"{other_url}/restoration", json={"reason": "Wrong scope"}).status_code == 404
    assert (
        owner.delete(other_url, params={"reason": "Wrong scope", "permanent": True}).status_code
        == 404
    )
    assert owner.post(f"{url}/restoration", json={"reason": "   "}).status_code == 422
    assert owner.get(url).status_code == 404


@pytest.mark.parametrize("kind", ["phase", "building", "floor"])
def test_restoration_requires_active_hierarchy(
    owner: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    phase_id: str,
    building_id: str,
    floor_id: str,
    db: Session,
    kind: str,
) -> None:
    url = f"{inventory_url(project_id)}/units/{unit_id}"
    assert owner.delete(url, params={"reason": "Remove"}).status_code == 204
    model, identifier = {
        "phase": (Phase, phase_id),
        "building": (Building, building_id),
        "floor": (Floor, floor_id),
    }[kind]
    db.get(model, uuid.UUID(identifier)).is_active = False
    db.commit()
    result = owner.post(f"{url}/restoration", json={"reason": "Restore"})
    assert result.status_code == 409, result.text
    assert "phase, building and floor" in result.json()["detail"]
    db.expire_all()
    assert db.get(Unit, uuid.UUID(unit_id)).removed_at is not None
    assert not list(db.scalars(select(AuditEvent).where(AuditEvent.action == "unit.restored")))


@pytest.mark.parametrize("removed", [False, True])
def test_explicit_permanent_delete_frees_number_and_keeps_audit(
    owner: TestClient,
    project_id: str,
    unit_id: str,
    floor_id: str,
    db: Session,
    removed: bool,
) -> None:
    if removed:
        unit = db.get(Unit, uuid.UUID(unit_id))
        unit.removed_at = datetime.now(UTC)
        unit.is_active = False
        db.commit()
    url = f"{inventory_url(project_id)}/units/{unit_id}"
    result = owner.delete(url, params={"reason": "Erase unused unit", "permanent": True})
    assert result.status_code == 204, result.text
    db.expire_all()
    assert db.get(Unit, uuid.UUID(unit_id)) is None
    assert owner.delete(url, params={"reason": "Retry", "permanent": True}).status_code == 404
    recreated = owner.post(f"{inventory_url(project_id)}/units", json=unit_payload(floor_id))
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["id"] != unit_id
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "unit.deleted"))
    assert event.entity_id == uuid.UUID(unit_id)
    assert event.reason == "Erase unused unit"


@pytest.mark.parametrize("removed", [False, True])
def test_permanent_delete_refuses_linked_prices_without_hiding_or_partial_deletion(
    owner: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
    removed: bool,
) -> None:
    url = f"{inventory_url(project_id)}/units/{unit_id}"
    if removed:
        assert owner.delete(url, params={"reason": "Remove"}).status_code == 204
    db.expire_all()
    before = db.get(Unit, uuid.UUID(unit_id)).removed_at
    measurements = list(db.scalars(select(UnitAreaSchedule.id)))
    result = owner.delete(url, params={"reason": "Purge", "permanent": True})
    assert result.status_code == 409, result.text
    assert "unit price" in result.json()["detail"]
    db.expire_all()
    assert db.get(Unit, uuid.UUID(unit_id)).removed_at == before
    assert list(db.scalars(select(UnitAreaSchedule.id))) == measurements
    assert not list(db.scalars(select(AuditEvent).where(AuditEvent.action == "unit.deleted")))


def test_permanent_delete_never_erases_a_committed_unit(
    owner: TestClient, project_id: str, active_sale: str, db: Session
) -> None:
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    unit_id = sale.unit_id
    response = owner.delete(
        f"{inventory_url(project_id)}/units/{unit_id}",
        params={"reason": "Purge", "permanent": True},
    )
    assert response.status_code == 409
    assert "commercial commitment" in response.json()["detail"]
    db.expire_all()
    assert db.get(Unit, unit_id).removed_at is None
    assert db.get(SaleContract, uuid.UUID(active_sale)) is not None
