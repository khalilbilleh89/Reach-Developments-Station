"""Inventory source CRUD, scope, audit and reconciled area feasibility."""

import uuid
from decimal import Decimal

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit
from app.modules.inventory.physical import COMPONENTS
from app.modules.project_analysis.feasibility import component
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access, inventory_url, unit_payload


def common_url(project: str) -> str:
    return f"{inventory_url(project)}/common-areas"


def area_payload(
    category: str = "common", amount: str = "10", apartment: str | None = None
) -> dict:
    return {
        "label": f"Measured {category}",
        "category": category,
        "area_sqm": amount,
        "apartment_id": apartment,
        "source_reference": "Synthetic drawing A-01",
    }


def approved(client: TestClient, project: str, unit: str) -> None:
    values = []
    for key, amount in zip(COMPONENTS, ("100", "20", "3", "4", "10", "5"), strict=True):
        created = client.post(
            f"{inventory_url(project)}/area-types",
            json={
                "code": key,
                "label": key,
                "area_role": "internal" if key == "internal" else "outdoor",
                "physical_component": key,
                "unit_of_measure": "sqm",
                "weight_factor": "1",
            },
        )
        assert created.status_code == 201, created.text
        values.append({"area_type_id": created.json()["id"], "raw_area": amount})
    created = client.post(
        f"{inventory_url(project)}/units/{unit}/area-schedules",
        json={"revision_code": "F1", "reconciled": True, "values": values},
    )
    assert created.status_code == 201, created.text
    response = client.post(
        f"{inventory_url(project)}/units/{unit}/area-schedules/{created.json()['id']}/approve"
    )
    assert response.status_code == 200, response.text


def test_area_totals_averages_groups_and_edit_delete_refresh(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    db: Session,
) -> None:
    approved(admin_client, project_id, unit_id)
    common_id = None
    for category, amount in (
        ("common", "15"),
        ("garage", "30"),
        ("community", "40"),
        ("roads_pavements", "50"),
    ):
        response = admin_client.post(
            common_url(project_id),
            json=area_payload(category, amount, unit_id if category == "common" else None),
        )
        assert response.status_code == 201, response.text
        if category == "common":
            common_id = response.json()["id"]
    url = f"/api/v1/projects/{project_id}/analysis/feasibility"
    before = db.scalar(select(text("count(*)")).select_from(AuditEvent))
    response = admin_client.get(url)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["apartments"] == 1
    expected = {
        "internal": "100",
        "balcony": "20",
        "covered": "120",
        "terrace": "10",
        "common": "15",
        "buildable": "115",
        "garage": "30",
        "building": "165",
        "community": "40",
        "roads_pavements": "50",
        "grand": "277",
    }
    for key, value in expected.items():
        assert Decimal(data["totals"][key]["value"]) == Decimal(value), key
    assert Decimal(data["averages"]["total"]["value"]) == 145
    assert data["groups"][0]["bedrooms"] == 2
    assert Decimal(data["groups"][0]["areas"]["covered"]["value"]) == 120
    assert Decimal(data["efficiencies"][0]["percentage"]) == Decimal("86.96")
    assert db.scalar(select(text("count(*)")).select_from(AuditEvent)) == before
    changed = admin_client.put(
        f"{common_url(project_id)}/{common_id}", json=area_payload("common", "25", unit_id)
    )
    assert changed.status_code == 200, changed.text
    assert Decimal(admin_client.get(url).json()["totals"]["buildable"]["value"]) == 125
    deleted = admin_client.delete(
        f"{common_url(project_id)}/{common_id}", params={"reason": "Duplicate survey removed"}
    )
    assert deleted.status_code == 204, deleted.text
    assert (
        admin_client.delete(
            f"{common_url(project_id)}/{common_id}", params={"reason": "Repeat"}
        ).status_code
        == 404
    )
    assert admin_client.get(url).json()["totals"]["buildable"]["value"] is None
    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_id == uuid.UUID(common_id), AuditEvent.action == "common_area.deleted"
        )
    )
    assert event is not None


def test_missing_zero_allocation_and_scope(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    building_id: str,
    db: Session,
) -> None:
    approved(admin_client, project_id, unit_id)
    url = f"/api/v1/projects/{project_id}/analysis/feasibility"
    data = admin_client.get(url).json()
    assert data["totals"]["covered"]["value"] == "120.0000"
    assert data["totals"]["common"]["value"] is None
    created = admin_client.post(common_url(project_id), json=area_payload("common", "10"))
    assert created.status_code == 201
    data = admin_client.get(url).json()
    assert data["totals"]["common"]["value"] == "10.0000"
    assert data["groups"][0]["areas"]["common"]["value"] is None
    changed = admin_client.put(
        f"{common_url(project_id)}/{created.json()['id']}", json=area_payload("common", "0")
    )
    assert changed.status_code == 200
    assert admin_client.get(url).json()["groups"][0]["areas"]["common"]["value"] == "0.0000"
    scoped = admin_client.get(url, params={"building_id": building_id}).json()
    assert scoped["totals"]["common"]["value"] is None
    assert admin_client.get(url, params={"building_id": str(uuid.uuid4())}).status_code == 404
    unit = db.get(Unit, uuid.UUID(unit_id))
    unit.is_active = False
    db.commit()
    assert admin_client.get(url).json()["apartments"] == 0


@pytest.mark.parametrize(
    "role,read,write",
    [
        ("project_manager", True, True),
        ("design_engineering", True, True),
        ("finance", True, False),
        ("sales_operations", False, False),
        ("sales_advisor", False, False),
    ],
)
def test_common_area_permissions_and_phase_isolation(
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
    db: Session,
    role: str,
    read: bool,
    write: bool,
) -> None:
    user = make_user(db, email=f"common-{role}@example.com", roles=(role,))
    grant_access(admin_client, project_id, user)
    client = client_for(user.email)
    url = f"/api/v1/projects/{project_id}/analysis/feasibility"
    assert client.get(url).status_code == (200 if read else 403)
    created = admin_client.post(common_url(project_id), json=area_payload())
    assert created.status_code == 201, created.text
    record = created.json()["id"]
    assert client.post(common_url(project_id), json=area_payload("garage")).status_code == (
        201 if write else 403
    )
    assert client.put(f"{common_url(project_id)}/{record}", json=area_payload()).status_code == (
        200 if write else 403
    )
    assert client.delete(
        f"{common_url(project_id)}/{record}", params={"reason": "Test"}
    ).status_code == (204 if write else 403)
    assert client.get(common_url(str(uuid.uuid4()))).status_code == 404
    admin_client.patch(
        f"/api/v1/projects/{project_id}/access/{user.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    admin_client.put(f"/api/v1/projects/{project_id}/access/{user.id}/phases/{phase_id}")
    assert client.get(common_url(project_id)).status_code == 403
    assert client.post(common_url(project_id), json=area_payload()).status_code == 403
    assert client.get(url).status_code == 403


def test_invalid_inputs_and_linked_apartment(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
) -> None:
    for change in (
        {"area_sqm": "-1"},
        {"area_sqm": None},
        {"category": "other"},
        {"label": " "},
        {"source_reference": " "},
        {"unrecognized": 12},
        {"category": "garage", "apartment_id": unit_id},
    ):
        response = admin_client.post(common_url(project_id), json={**area_payload(), **change})
        assert response.status_code == 422, response.text
    response = admin_client.post(
        common_url(project_id), json=area_payload(apartment=str(uuid.uuid4()))
    )
    assert response.status_code == 404
    created = admin_client.post(common_url(project_id), json=area_payload(apartment=unit_id))
    assert created.status_code == 201
    # Existing unit removal catches the restrictive FK and preserves both records.
    response = admin_client.delete(
        f"{inventory_url(project_id)}/units/{unit_id}", params={"reason": "Test linked"}
    )
    assert response.status_code == 409, response.text


def test_measurement_conversion_and_invalid_components() -> None:
    line = {"physical_component": "internal", "unit_of_measure": "sqft", "raw_area": Decimal("100")}
    assert component([line], "internal") == Decimal("9.290304")
    assert component([line, line], "internal") is None
    assert component([], "internal") is None
    assert component([{**line, "unit_of_measure": "yards"}], "internal") is None


def test_common_area_migration_roundtrip(db: Session) -> None:
    db.rollback()
    command.downgrade(alembic_config(), "0025_prelaunch_master")
    command.upgrade(alembic_config(), "head")
    assert db.scalar(text("SELECT count(*) FROM inventory_common_areas")) == 0


def test_multiple_apartments_weighted_averages_missing_and_mixed_classes(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    floor_id: str,
    db: Session,
) -> None:
    approved(admin_client, project_id, unit_id)
    second = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(floor_id, unit_reference="B1-102", unit_number="102", bedrooms=0),
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]
    url = f"/api/v1/projects/{project_id}/analysis/feasibility"
    data = admin_client.get(url).json()
    assert data["apartments"] == 2
    assert data["totals"]["internal"]["value"] is None
    assert data["totals"]["internal"]["measured_count"] == 1
    assert data["averages"]["internal"]["value"] is None
    types = admin_client.get(f"{inventory_url(project_id)}/area-types").json()
    schedule = admin_client.post(
        f"{inventory_url(project_id)}/units/{second_id}/area-schedules",
        json={
            "revision_code": "SECOND",
            "reconciled": True,
            "values": [
                {
                    "area_type_id": row["id"],
                    "raw_area": "200" if row["physical_component"] == "internal" else "0",
                }
                for row in types
            ],
        },
    )
    assert schedule.status_code == 201, schedule.text
    assert (
        admin_client.post(
            f"{inventory_url(project_id)}/units/{second_id}/area-schedules/{schedule.json()['id']}/approve"
        ).status_code
        == 200
    )
    for name, unit, amount in (
        ("First allocation", unit_id, "10"),
        ("Second allocation", second_id, "30"),
    ):
        result = admin_client.post(
            common_url(project_id),
            json={**area_payload(apartment=unit, amount=amount), "label": name},
        )
        assert result.status_code == 201, result.text
    data = admin_client.get(url).json()
    assert Decimal(data["averages"]["covered"]["value"]) == 160
    assert Decimal(data["averages"]["common"]["value"]) == 20
    assert Decimal(data["averages"]["total"]["value"]) == 185
    assert [
        (row["bedrooms"], Decimal(row["areas"]["common"]["value"])) for row in data["groups"]
    ] == [(0, Decimal("30")), (2, Decimal("10"))]
    unit = db.get(Unit, uuid.UUID(second_id))
    unit.asset_class = "villa"
    db.commit()
    data = admin_client.get(url).json()
    assert data["apartments"] == 1 and data["other_units"] == 1
    assert data["totals"]["buildable"]["value"] is None
    assert data["efficiencies"][0]["percentage"] is None


def test_duplicate_source_and_wrong_project_mutations(
    admin_client: TestClient,
    project_id: str,
    operational_project: str,
) -> None:
    record = admin_client.post(common_url(project_id), json=area_payload())
    assert record.status_code == 201
    assert admin_client.post(common_url(project_id), json=area_payload()).status_code == 409
    identifier = record.json()["id"]
    assert (
        admin_client.put(
            f"{common_url(str(uuid.uuid4()))}/{identifier}", json=area_payload()
        ).status_code
        == 404
    )
    assert (
        admin_client.delete(
            f"{common_url(str(uuid.uuid4()))}/{identifier}", params={"reason": "Wrong scope"}
        ).status_code
        == 404
    )
    assert len(admin_client.get(common_url(project_id)).json()) == 1


def test_populated_migration_refuses_loss(
    admin_client: TestClient,
    project_id: str,
    operational_project: str,
    db: Session,
) -> None:
    assert admin_client.post(common_url(project_id), json=area_payload()).status_code == 201
    db.rollback()
    with pytest.raises(RuntimeError, match="Common area measurements exist"):
        command.downgrade(alembic_config(), "0025_prelaunch_master")
    assert db.scalar(text("SELECT count(*) FROM inventory_common_areas")) == 1
