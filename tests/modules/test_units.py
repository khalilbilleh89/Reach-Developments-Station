"""The unit: stable identity, editable reference, and a hierarchy it can leave.

The distinction these tests exist to protect is the one the whole platform rests
on. ``id`` is what every later price, sale, installment and handover will point
at, and it never changes. ``unit_reference`` is a label people read, and it does.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit
from tests.modules.conftest import PROJECTS, inventory_url, project_payload, unit_payload


def test_a_unit_is_created_with_its_four_status_dimensions(
    admin_client: TestClient, project_id: str, floor_id: str
) -> None:
    """Given a new unit, then all four statuses start honestly."""
    response = admin_client.post(f"{inventory_url(project_id)}/units", json=unit_payload(floor_id))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["commercial_status"] == "unreleased"
    assert body["legal_status"] == "not_started"
    assert body["collection_status"] == "not_started"
    assert body["delivery_status"] == "not_started"
    assert body["pricing_approved"] is False


def test_a_unit_reports_its_hierarchy_without_storing_it(
    admin_client: TestClient, project_id: str, phase_id: str, building_id: str, unit_id: str
) -> None:
    """Given a unit, then phase and building are derived through its floor.

    They are read back for the register's benefit; they are not columns, because
    two copies of one fact are two things to disagree.
    """
    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()

    assert body["phase_id"] == phase_id
    assert body["building_id"] == building_id


def test_a_unit_reference_is_unique_within_a_project(
    admin_client: TestClient, project_id: str, building_id: str, floor_id: str, unit_id: str
) -> None:
    second_floor = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "02", "label": "Second"},
    ).json()["id"]

    response = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(second_floor, unit_number="201", unit_reference="B1-101"),
    )

    assert response.status_code == 409
    assert "reference already exists" in response.json()["detail"]


def test_a_unit_number_is_unique_within_a_floor(
    admin_client: TestClient, project_id: str, floor_id: str, unit_id: str
) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(floor_id, unit_number="101", unit_reference="B1-101-DUP"),
    )

    assert response.status_code == 409
    assert "number already exists" in response.json()["detail"]


def test_the_same_number_may_recur_on_another_floor(
    admin_client: TestClient, project_id: str, building_id: str, floor_id: str, unit_id: str
) -> None:
    """Given "101" already exists on floor 1, then floor 2 may have one too."""
    second_floor = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "02", "label": "Second"},
    ).json()["id"]

    response = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(second_floor, unit_number="101", unit_reference="B1-201"),
    )

    assert response.status_code == 201, response.text


def test_the_same_reference_may_recur_in_another_project(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    country_pack_id: str,
    currency_id: str,
    inventory_reference_data: None,
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    ).json()["id"]
    # A second project needs its own basis finalised before it holds inventory.
    admin_client.patch(f"{PROJECTS}/{other}", json={"status": "predevelopment"})
    phase = admin_client.post(
        f"{inventory_url(other)}/phases", json={"code": "P1", "name": "One"}
    ).json()["id"]
    building = admin_client.post(
        f"{inventory_url(other)}/buildings",
        json={"phase_id": phase, "code": "B1", "name": "One"},
    ).json()["id"]
    floor = admin_client.post(
        f"{inventory_url(other)}/floors",
        json={"building_id": building, "code": "01", "label": "First"},
    ).json()["id"]

    response = admin_client.post(f"{inventory_url(other)}/units", json=unit_payload(floor))

    assert response.status_code == 201, response.text


def test_correcting_a_unit_reference_never_changes_identity(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given A-101 renumbered to A1-101, then the UUID is untouched.

    This is the point of separating the two columns: a project that renumbers
    its inventory must not lose every relationship pointing at it.
    """
    response = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"unit_reference": "A1-101"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == unit_id
    assert response.json()["unit_reference"] == "A1-101"
    assert db.scalars(select(Unit)).one().id == uuid.UUID(unit_id)


def test_a_reference_correction_is_audited(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"unit_reference": "A1-101"}
    )

    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "unit.updated")).one()
    assert event.before_data["unit_reference"] == "B1-101"
    assert event.after_data["unit_reference"] == "A1-101"


@pytest.mark.parametrize(
    "body",
    [
        {"commercial_status": "available"},
        {"legal_status": "registered"},
        {"collection_status": "cleared"},
        {"delivery_status": "handed_over"},
        {"pricing_approved": True},
        {"id": "00000000-0000-0000-0000-000000000000"},
        {"project_id": "00000000-0000-0000-0000-000000000000"},
        {"bedroms": 3},
    ],
)
def test_a_unit_update_refuses_what_it_does_not_declare(
    admin_client: TestClient, project_id: str, unit_id: str, body: dict[str, object]
) -> None:
    """Given a status, an identity field or a typo, then 422 and no write.

    Silently dropping the key and answering 200 would tell an operator a change
    happened that did not.
    """
    response = admin_client.patch(f"{inventory_url(project_id)}/units/{unit_id}", json=body)

    assert response.status_code == 422


def test_a_unit_may_move_floors_while_unreleased(
    admin_client: TestClient, project_id: str, building_id: str, unit_id: str
) -> None:
    second_floor = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "02", "label": "Second"},
    ).json()["id"]

    response = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"floor_id": second_floor}
    )

    assert response.status_code == 200, response.text
    assert response.json()["floor_id"] == second_floor


def test_a_held_unit_cannot_be_moved(
    admin_client: TestClient,
    project_id: str,
    building_id: str,
    unit_id: str,
) -> None:
    """Given a unit that has left unreleased, then a move is refused.

    Changing the floor changes the building and phase with it, which would move
    a unit somebody is holding out of one person's access and into another's.
    """
    admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={"to_status": "held", "effective_date": "2026-02-01", "reason": "Broker hold"},
    )
    second_floor = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "02", "label": "Second"},
    ).json()["id"]

    response = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"floor_id": second_floor}
    )

    assert response.status_code == 409
    assert "only be moved while it is unreleased" in response.json()["detail"]


def test_a_unit_cannot_be_moved_onto_another_projects_floor(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    country_pack_id: str,
    currency_id: str,
    inventory_reference_data: None,
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    ).json()["id"]
    # A second project needs its own basis finalised before it holds inventory.
    admin_client.patch(f"{PROJECTS}/{other}", json={"status": "predevelopment"})
    phase = admin_client.post(
        f"{inventory_url(other)}/phases", json={"code": "P1", "name": "One"}
    ).json()["id"]
    building = admin_client.post(
        f"{inventory_url(other)}/buildings",
        json={"phase_id": phase, "code": "B1", "name": "One"},
    ).json()["id"]
    foreign_floor = admin_client.post(
        f"{inventory_url(other)}/floors",
        json={"building_id": building, "code": "01", "label": "First"},
    ).json()["id"]

    response = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"floor_id": foreign_floor}
    )

    assert response.status_code == 404


def test_an_unconfigured_unit_type_is_refused(
    admin_client: TestClient, project_id: str, floor_id: str
) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(floor_id, unit_type_code="PENTHOUSE_XL"),
    )

    assert response.status_code == 422
    assert "unit_type" in response.json()["detail"]


def test_a_retired_code_stays_on_the_record_that_carries_it(
    admin_client: TestClient, project_id: str, unit_id: str, country_pack_id: str
) -> None:
    """Given the configured code is retired, then the unit keeps it.

    Configuration moving on is not a reason to invalidate a record that was
    correct when it was made. Only newly assigned codes are checked.
    """
    from tests.modules.conftest import SETTINGS

    values = admin_client.get(f"{SETTINGS}/reference-values").json()
    two_br = next(value for value in values if value["code"] == "2BR")
    admin_client.patch(f"{SETTINGS}/reference-values/{two_br['id']}", json={"is_active": False})

    response = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"bedrooms": 3}
    )

    assert response.status_code == 200, response.text
    assert response.json()["unit_type_code"] == "2BR"


def test_units_have_no_delete_endpoint(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    response = admin_client.delete(f"{inventory_url(project_id)}/units/{unit_id}")

    assert response.status_code == 404


def test_the_register_counts_the_whole_set_not_the_page(
    admin_client: TestClient, project_id: str, floor_id: str
) -> None:
    """Given a page smaller than the register, then the counts still describe it all.

    Reporting the size of one page under the name ``total`` tells a manager
    there are two units when there are five.
    """
    for number in range(1, 6):
        admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number=f"10{number}", unit_reference=f"B1-10{number}"),
        )

    register = admin_client.get(f"{inventory_url(project_id)}/units?limit=2").json()

    assert len(register["units"]) == 2
    assert register["total"] == 5
    assert register["unreleased_count"] == 5


def test_a_filter_narrows_the_counts_as_well_as_the_rows(
    admin_client: TestClient, project_id: str, floor_id: str, unit_id: str
) -> None:
    admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(floor_id, unit_number="102", unit_reference="B1-102", bedrooms=3),
    )

    register = admin_client.get(f"{inventory_url(project_id)}/units?search=B1-102").json()

    assert register["total"] == 1
    assert [row["unit_reference"] for row in register["units"]] == ["B1-102"]


def test_a_sales_advisor_may_read_but_not_write(
    db: Session, admin_client: TestClient, project_id: str, floor_id: str, unit_id: str
) -> None:
    from tests.factories import client_for, make_user

    advisor = make_user(db, email="advisor2@example.com", roles=("sales_advisor",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{advisor.id}")
    client = client_for(advisor.email)

    assert client.get(f"{inventory_url(project_id)}/units").status_code == 200
    assert (
        client.patch(
            f"{inventory_url(project_id)}/units/{unit_id}", json={"bedrooms": 4}
        ).status_code
        == 403
    )
