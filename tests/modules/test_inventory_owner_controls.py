"""Owner corrections and deletion preserve authorization, identifiers and history."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import UnitAreaSchedule
from tests.factories import client_for, make_user
from tests.modules.conftest import inventory_url, sales_url


def test_administrator_can_correct_codes_and_move_empty_hierarchy(
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
    building_id: str,
    floor_id: str,
) -> None:
    base = inventory_url(project_id)
    for kind, identifier, code in (
        ("phases", phase_id, "PHASE2"),
        ("buildings", building_id, "B2"),
        ("floors", floor_id, "-1"),
    ):
        response = admin_client.patch(f"{base}/{kind}/{identifier}", json={"code": code})
        assert response.status_code == 200, response.text
        assert response.json()["id"] == identifier
        assert response.json()["code"] == code
    destination = admin_client.post(
        f"{base}/buildings", json={"phase_id": phase_id, "code": "B3", "name": "Three"}
    ).json()["id"]
    moved = admin_client.patch(f"{base}/floors/{floor_id}", json={"building_id": destination})
    assert moved.status_code == 200, moved.text
    assert moved.json()["building_id"] == destination


def test_delete_empty_unit_floor_building_keeps_audit(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    floor_id: str,
    building_id: str,
    db: Session,
) -> None:
    base = inventory_url(project_id)
    blocked = admin_client.delete(f"{base}/floors/{floor_id}", params={"reason": "Mistake"})
    assert blocked.status_code == 409, blocked.text
    for kind, identifier in (("units", unit_id), ("floors", floor_id), ("buildings", building_id)):
        response = admin_client.delete(
            f"{base}/{kind}/{identifier}", params={"reason": "Duplicate entry"}
        )
        assert response.status_code == 204, response.text
        assert db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.entity_id == uuid.UUID(identifier),
                AuditEvent.action == f"{kind[:-1]}.deleted",
            )
        )
    assert admin_client.get(f"{base}/units/{unit_id}").status_code == 404


def test_delete_priced_unit_rolls_back_measurements(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    before = list(db.scalars(select(UnitAreaSchedule.id)))
    response = admin_client.delete(
        f"{inventory_url(project_id)}/units/{unit_id}", params={"reason": "Remove"}
    )
    assert response.status_code == 409, response.text
    assert list(db.scalars(select(UnitAreaSchedule.id))) == before
    assert admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").status_code == 200


def test_master_can_delete_unused_buyer_with_parties(
    project_id: str,
    buyer_id: str,
    db: Session,
) -> None:
    master = make_user(db, email="owner-delete@example.com", roles=("master_admin",))
    client = client_for(master.email)
    url = f"{sales_url(project_id)}/clients/{buyer_id}"
    response = client.delete(url, params={"reason": "Duplicate buyer"})
    assert response.status_code == 204, response.text
    assert client.get(url).status_code == 404


def test_other_users_cannot_delete_and_blank_reason_is_refused(
    admin_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    unit_id: str,
) -> None:
    url = f"{inventory_url(project_id)}/units/{unit_id}"
    assert sales_ops_client.delete(url, params={"reason": "Remove"}).status_code == 403
    assert admin_client.delete(url, params={"reason": "   "}).status_code == 422


def test_buyer_with_sales_history_cannot_be_deleted(
    admin_client: TestClient,
    project_id: str,
    buyer_id: str,
    reservation_id: str,
) -> None:
    url = f"{sales_url(project_id)}/clients/{buyer_id}"
    response = admin_client.delete(url, params={"reason": "Remove"})
    assert response.status_code == 409, response.text
    assert admin_client.get(url).status_code == 200
