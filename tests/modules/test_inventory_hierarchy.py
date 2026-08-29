"""Buildings and floors: the structure a unit hangs from.

The interesting assertions here are the ones the database makes. A building
whose phase belongs to another project is not refused by a Python check that
somebody might forget to write — it is a foreign-key violation.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.inventory.models import Building, Floor
from tests.modules.conftest import PROJECTS, inventory_url, project_payload


def test_a_building_belongs_to_a_phase(
    admin_client: TestClient, project_id: str, phase_id: str
) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/buildings",
        json={"phase_id": phase_id, "code": "b1", "name": "Building 1", "zone": "North"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["code"] == "B1"
    assert body["phase_id"] == phase_id
    assert body["zone"] == "North"


def test_a_duplicate_building_code_in_one_phase_is_refused(
    admin_client: TestClient, project_id: str, phase_id: str, building_id: str
) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/buildings",
        json={"phase_id": phase_id, "code": "B1", "name": "Again"},
    )

    assert response.status_code == 409


def test_two_phases_may_use_the_same_building_code(
    admin_client: TestClient, project_id: str, phase_id: str, building_id: str
) -> None:
    """Given a second phase, then B1 there is a different building."""
    second = admin_client.post(
        f"{inventory_url(project_id)}/phases", json={"code": "PHASE-2", "name": "Two"}
    ).json()["id"]

    response = admin_client.post(
        f"{inventory_url(project_id)}/buildings",
        json={"phase_id": second, "code": "B1", "name": "Building 1"},
    )

    assert response.status_code == 201, response.text


def test_a_building_cannot_be_created_under_another_projects_phase(
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    """Given a phase of project A named in project B's path, then 404."""
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    ).json()["id"]
    # A second project needs its own basis finalised before it holds inventory.
    admin_client.patch(f"{PROJECTS}/{other}", json={"status": "predevelopment"})

    response = admin_client.post(
        f"{inventory_url(other)}/buildings",
        json={"phase_id": phase_id, "code": "B1", "name": "Smuggled"},
    )

    assert response.status_code == 404


def test_the_database_refuses_a_cross_project_building(
    db: Session,
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    """Given a direct INSERT, then the composite foreign key still refuses it.

    The API check above could be removed by a careless refactor. This one could
    not: the pair (phase_id, project_id) has to exist in ``phases``.
    """
    from sqlalchemy.exc import IntegrityError

    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    ).json()["id"]
    # A second project needs its own basis finalised before it holds inventory.
    admin_client.patch(f"{PROJECTS}/{other}", json={"status": "predevelopment"})
    admin_id = db.scalars(text("SELECT id FROM users LIMIT 1")).one()

    db.add(
        Building(
            project_id=uuid.UUID(other),
            phase_id=uuid.UUID(phase_id),
            code="X1",
            name="Impossible",
            created_by_user_id=admin_id,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_floor_uses_a_string_code(
    admin_client: TestClient, project_id: str, building_id: str
) -> None:
    """Given a basement, then its code survives.

    Real buildings have B2, GF, M and RF. An integer-only floor identity loses
    the mezzanine and the roof.
    """
    for code, label in (("b2", "Basement 2"), ("GF", "Ground floor"), ("RF", "Roof")):
        response = admin_client.post(
            f"{inventory_url(project_id)}/floors",
            json={"building_id": building_id, "code": code, "label": label},
        )
        assert response.status_code == 201, response.text
        assert response.json()["code"] == code.upper()


def test_a_duplicate_floor_code_in_one_building_is_refused(
    admin_client: TestClient, project_id: str, building_id: str, floor_id: str
) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "01", "label": "Again"},
    )

    assert response.status_code == 409


def test_a_floor_cannot_be_created_under_an_inactive_building(
    admin_client: TestClient, project_id: str, building_id: str
) -> None:
    admin_client.patch(
        f"{inventory_url(project_id)}/buildings/{building_id}", json={"is_active": False}
    )

    response = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "02", "label": "Second"},
    )

    assert response.status_code == 409
    assert "not active" in response.json()["detail"]


def test_a_building_with_active_floors_cannot_be_deactivated(
    admin_client: TestClient, project_id: str, building_id: str, floor_id: str
) -> None:
    response = admin_client.patch(
        f"{inventory_url(project_id)}/buildings/{building_id}", json={"is_active": False}
    )

    assert response.status_code == 409
    assert "still has active floors" in response.json()["detail"]


def test_a_floor_with_active_units_cannot_be_deactivated(
    admin_client: TestClient, project_id: str, floor_id: str, unit_id: str
) -> None:
    response = admin_client.patch(
        f"{inventory_url(project_id)}/floors/{floor_id}", json={"is_active": False}
    )

    assert response.status_code == 409
    assert "still has active units" in response.json()["detail"]


def test_buildings_can_be_filtered_by_phase(
    admin_client: TestClient, project_id: str, phase_id: str, building_id: str
) -> None:
    second = admin_client.post(
        f"{inventory_url(project_id)}/phases", json={"code": "PHASE-2", "name": "Two"}
    ).json()["id"]
    admin_client.post(
        f"{inventory_url(project_id)}/buildings",
        json={"phase_id": second, "code": "B9", "name": "Other"},
    )

    response = admin_client.get(f"{inventory_url(project_id)}/buildings?phase_id={phase_id}")

    assert response.status_code == 200
    assert [row["code"] for row in response.json()] == ["B1"]


def test_floors_can_be_filtered_by_building(
    admin_client: TestClient, project_id: str, phase_id: str, building_id: str, floor_id: str
) -> None:
    other_building = admin_client.post(
        f"{inventory_url(project_id)}/buildings",
        json={"phase_id": phase_id, "code": "B2", "name": "Building 2"},
    ).json()["id"]
    admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": other_building, "code": "01", "label": "First"},
    )

    response = admin_client.get(f"{inventory_url(project_id)}/floors?building_id={building_id}")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_hierarchy_creation_is_audited(
    admin_client: TestClient, project_id: str, building_id: str, floor_id: str, db: Session
) -> None:
    from app.modules.audit.models import AuditEvent

    actions = set(
        db.scalars(
            select(AuditEvent.action).where(
                AuditEvent.action.in_(["building.created", "floor.created"])
            )
        )
    )
    assert actions == {"building.created", "floor.created"}


def test_a_floor_keeps_its_building(
    admin_client: TestClient, project_id: str, floor_id: str, db: Session
) -> None:
    """Given a PATCH naming a building, then the request is refused.

    Moving a floor between buildings would move every unit on it, which is a
    larger change than a floor edit and is not on offer.
    """
    response = admin_client.patch(
        f"{inventory_url(project_id)}/floors/{floor_id}",
        json={"building_id": str(uuid.uuid4())},
    )

    assert response.status_code == 422
    assert db.scalars(select(Floor)).one().id == uuid.UUID(floor_id)
