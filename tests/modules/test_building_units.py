"""Villas have a real building parent without an invented floor."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.modules.conftest import inventory_url


def test_building_unit_is_visible_and_requires_a_real_parent(
    admin_client: TestClient, project_id: str, building_id: str, phase_id: str, db: Session
) -> None:
    import uuid

    from app.modules.inventory.models import Unit
    from app.modules.pricing.service import hierarchy_of

    url = inventory_url(project_id)
    payload = {
        "building_id": building_id,
        "unit_number": "V1",
        "unit_reference": "VILLA-1",
        "asset_class": "villa",
        "bedrooms": 3,
    }
    response = admin_client.post(f"{url}/units", json=payload)
    assert response.status_code == 201, response.text
    unit = response.json()
    assert unit["floor_id"] is None
    assert unit["building_id"] == building_id
    assert unit["phase_id"] == phase_id
    for query in (f"building_id={building_id}", f"phase_id={phase_id}", ""):
        result = admin_client.get(f"{url}/units?{query}")
        assert result.status_code == 200, result.text
        assert "VILLA-1" in result.text
    phase, building, floor = hierarchy_of(db, db.get(Unit, uuid.UUID(unit["id"])))
    assert str(phase.id) == phase_id and str(building.id) == building_id and floor is None
    db.rollback()
    duplicate = admin_client.post(f"{url}/units", json={**payload, "unit_reference": "VILLA-2"})
    assert duplicate.status_code == 409
    assert (
        admin_client.patch(f"{url}/units/{unit['id']}", json={"building_id": None}).status_code
        == 422
    )
    assert (
        admin_client.post(
            f"{url}/floors", json={"building_id": building_id, "code": "G", "label": "Ground"}
        ).status_code
        == 409
    )


def test_building_with_floors_requires_floor(
    admin_client: TestClient, project_id: str, building_id: str, floor_id: str
) -> None:
    url = inventory_url(project_id)
    payload = {"unit_number": "101", "unit_reference": "A101", "asset_class": "apartment"}
    assert admin_client.post(f"{url}/units", json=payload).status_code == 422
    assert (
        admin_client.post(f"{url}/units", json={**payload, "building_id": building_id}).status_code
        == 422
    )
    assert (
        admin_client.post(
            f"{url}/units", json={**payload, "building_id": building_id, "floor_id": floor_id}
        ).status_code
        == 422
    )
    response = admin_client.post(f"{url}/units", json={**payload, "floor_id": floor_id})
    assert response.status_code == 201, response.text


def test_building_unit_migration_preserves_units_and_refuses_loss(
    admin_client: TestClient, project_id: str, building_id: str, db: Session
) -> None:
    import pytest
    from alembic import command

    from tests.conftest import alembic_config

    config = alembic_config()
    db.rollback()
    command.downgrade(config, "0030_unit_removal")
    command.upgrade(config, "head")
    command.check(config)
    response = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json={
            "building_id": building_id,
            "unit_number": "V1",
            "unit_reference": "V1",
            "asset_class": "villa",
        },
    )
    assert response.status_code == 201, response.text
    with pytest.raises(RuntimeError, match="Assign building-level units"):
        command.downgrade(config, "0030_unit_removal")
    assert (
        admin_client.get(f"{inventory_url(project_id)}/units/{response.json()['id']}").status_code
        == 200
    )


def test_building_units_obey_phase_scope(
    admin_client: TestClient, project_id: str, building_id: str, phase_id: str, db: Session
) -> None:
    from tests.factories import client_for, make_user
    from tests.modules.conftest import PROJECTS

    user = make_user(db, email="villa-reader@example.com", roles=("sales_advisor",))
    user_id = user.id
    db.rollback()
    admin_client.put(f"{PROJECTS}/{project_id}/access/{user_id}")
    admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{user_id}/phase-scope", json={"phase_scope": "selected"}
    )
    unit = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json={
            "building_id": building_id,
            "unit_number": "V1",
            "unit_reference": "PRIVATE-VILLA",
            "asset_class": "villa",
        },
    ).json()
    client = client_for("villa-reader@example.com")
    url = f"{inventory_url(project_id)}/units/{unit['id']}"
    assert client.get(url).status_code == 404
    assert "PRIVATE-VILLA" not in client.get(f"{inventory_url(project_id)}/units").text
    admin_client.put(f"{PROJECTS}/{project_id}/access/{user_id}/phases/{phase_id}")
    assert client.get(url).status_code == 200
    assert "PRIVATE-VILLA" in client.get(f"{inventory_url(project_id)}/units").text


def test_building_unit_can_be_repriced_after_a_governed_move(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    phase_id: str,
    unit_id: str,
    priced_unit: str,
) -> None:
    from tests.modules.conftest import pricing_url

    url = inventory_url(project_id)
    building = admin_client.post(
        f"{url}/buildings", json={"phase_id": phase_id, "code": "VILLAS", "name": "Villas"}
    ).json()
    moved = admin_client.patch(
        f"{url}/units/{unit_id}", json={"floor_id": None, "building_id": building["id"]}
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["floor_id"] is None
    assert moved.json()["pricing_approved"] is False
    draft = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    )
    assert draft.status_code == 201, draft.text
