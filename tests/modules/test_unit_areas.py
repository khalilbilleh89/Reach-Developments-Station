"""Area types, measured revisions, and the weighted saleable figure.

Two numbers matter here and they must never be confused. The **raw** area is
what the drawing says and what the deed will say. The **weighted** area is a
commercial convention: a balcony at factor 0.5 contributes half of itself. A
factor change moves the second and never the first.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import UnitAreaSchedule, UnitAreaValue
from tests.modules.conftest import approve_areas, inventory_url


def _schedules(project_id: str, unit_id: str) -> str:
    return f"{inventory_url(project_id)}/units/{unit_id}/area-schedules"


def test_an_area_type_carries_an_explicit_factor(
    admin_client: TestClient, project_id: str, area_types: dict[str, str]
) -> None:
    """Given the configured types, then the factors come back exact."""
    rows = {
        row["code"]: row
        for row in admin_client.get(f"{inventory_url(project_id)}/area-types").json()
    }

    assert rows["INTERNAL"]["weight_factor"] == "1.000000"
    assert rows["BALCONY"]["weight_factor"] == "0.500000"
    assert rows["INTERNAL"]["required_for_release"] is True


def test_a_factor_outside_zero_to_one_is_refused(admin_client: TestClient, project_id: str) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/area-types",
        json={
            "code": "ODD",
            "label": "Odd",
            "area_role": "other",
            "weight_factor": "1.500000",
        },
    )

    assert response.status_code == 422


def test_a_project_has_one_primary_internal_area(
    admin_client: TestClient, project_id: str, area_types: dict[str, str]
) -> None:
    """Given an internal type exists, then a second active one is refused.

    Two would make "the legal area" ambiguous, which is the one thing this
    configuration must never be.
    """
    response = admin_client.post(
        f"{inventory_url(project_id)}/area-types",
        json={
            "code": "NET",
            "label": "Net internal",
            "area_role": "internal",
            "weight_factor": "1.000000",
        },
    )

    assert response.status_code == 409
    assert "one primary internal area" in response.json()["detail"]


def test_a_duplicate_area_type_code_is_refused(
    admin_client: TestClient, project_id: str, area_types: dict[str, str]
) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/area-types",
        json={
            "code": "BALCONY",
            "label": "Again",
            "area_role": "outdoor",
            "weight_factor": "0.500000",
        },
    )

    assert response.status_code == 409


def test_a_schedule_starts_as_a_draft(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    response = admin_client.post(
        _schedules(project_id, unit_id),
        json={
            "revision_code": "R0",
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "100.0000"}],
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "draft"


def test_raw_areas_survive_the_round_trip_exactly(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str], db: Session
) -> None:
    """Given 104.5000, then 104.5000 comes back — as a string, not a float."""
    admin_client.post(
        _schedules(project_id, unit_id),
        json={
            "revision_code": "R0",
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "104.5000"}],
        },
    )

    body = admin_client.get(_schedules(project_id, unit_id)).json()[0]
    assert body["lines"][0]["raw_area"] == "104.5000"
    assert db.scalars(select(UnitAreaValue)).one().raw_area == Decimal("104.5000")


def test_the_weighted_saleable_area_is_derived_exactly(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    """Given 100 internal and 20 balcony at 0.5, then the weighted total is 110."""
    approve_areas(admin_client, project_id, unit_id, area_types)

    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()

    lines = {line["code"]: line for line in body["area_lines"]}
    # Strings, not JSON numbers: a measured area routed through a binary float is
    # a figure nobody can reconcile against the drawing it came from.
    assert isinstance(lines["INTERNAL"]["weighted_area"], str)
    assert Decimal(lines["INTERNAL"]["weighted_area"]) == Decimal("100")
    assert Decimal(lines["BALCONY"]["weighted_area"]) == Decimal("10")
    assert Decimal(body["weighted_saleable_area"]) == Decimal("110")
    # The legal internal area is reported separately and is never the weighted one.
    assert Decimal(body["internal_area"]) == Decimal("100")
    assert body["internal_area"] != body["weighted_saleable_area"]


def test_a_weighted_figure_is_presented_at_the_scale_areas_are_measured_at(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    """Given a six-decimal factor, then the weighted figures still read as areas.

    A four-decimal area times a six-decimal factor lands on ten decimals.
    Publishing that is false precision, and worse, the lines a reader adds up
    would not equal the total printed beneath them.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)

    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()

    lines = {line["code"]: line for line in body["area_lines"]}
    assert lines["BALCONY"]["weighted_area"] == "10.0000"
    assert lines["INTERNAL"]["weighted_area"] == "100.0000"
    assert body["weighted_saleable_area"] == "110.0000"
    # The column adds up: the total is the sum of the figures shown, not a
    # separately rounded number that happens to sit near them.
    assert Decimal(body["weighted_saleable_area"]) == sum(
        Decimal(line["weighted_area"]) for line in body["area_lines"]
    )


def test_a_factor_change_moves_the_weighted_area_and_not_the_raw_one(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)

    admin_client.patch(
        f"{inventory_url(project_id)}/area-types/{area_types['BALCONY']}",
        json={"weight_factor": "0.250000"},
    )

    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    lines = {line["code"]: line for line in body["area_lines"]}
    assert lines["BALCONY"]["raw_area"] == "20.0000"
    assert Decimal(lines["BALCONY"]["weighted_area"]) == Decimal("5")
    assert Decimal(body["weighted_saleable_area"]) == Decimal("105")


def test_approval_requires_reconciliation(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    """Given a revision nobody checked against the drawing, then approval waits."""
    schedule = admin_client.post(
        _schedules(project_id, unit_id),
        json={
            "revision_code": "R0",
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "100.0000"}],
        },
    ).json()["id"]

    response = admin_client.post(f"{_schedules(project_id, unit_id)}/{schedule}/approve")

    assert response.status_code == 409
    assert "not been reconciled" in response.json()["detail"]


def test_approval_requires_every_required_area(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    schedule = admin_client.post(
        _schedules(project_id, unit_id),
        json={
            "revision_code": "R0",
            "reconciled": True,
            "values": [{"area_type_id": area_types["BALCONY"], "raw_area": "20.0000"}],
        },
    ).json()["id"]

    response = admin_client.post(f"{_schedules(project_id, unit_id)}/{schedule}/approve")

    assert response.status_code == 409
    assert "INTERNAL" in response.json()["detail"]


def test_an_approved_revision_is_immutable(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    """Given an approved revision, then editing it is refused.

    The measurement a unit was sold against does not get quietly rewritten. A
    correction is a new revision.
    """
    schedule = approve_areas(admin_client, project_id, unit_id, area_types)

    response = admin_client.patch(
        f"{_schedules(project_id, unit_id)}/{schedule}",
        json={"values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "999.0000"}]},
    )

    assert response.status_code == 409
    assert "cannot be edited" in response.json()["detail"]


def test_approving_a_second_revision_supersedes_the_first(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str], db: Session
) -> None:
    """Given a corrected measurement, then the old one is kept and superseded."""
    first = approve_areas(admin_client, project_id, unit_id, area_types)
    second = approve_areas(
        admin_client, project_id, unit_id, area_types, internal="105.0000", revision="R1"
    )

    statuses = {
        str(schedule.id): schedule.status for schedule in db.scalars(select(UnitAreaSchedule))
    }
    assert statuses[first] == "superseded"
    assert statuses[second] == "approved"
    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    assert body["area_revision_code"] == "R1"


def test_a_superseded_revision_cannot_be_approved_again(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    first = approve_areas(admin_client, project_id, unit_id, area_types)
    approve_areas(admin_client, project_id, unit_id, area_types, revision="R1")

    response = admin_client.post(f"{_schedules(project_id, unit_id)}/{first}/approve")

    assert response.status_code == 409


def test_a_duplicate_revision_code_is_refused(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)

    response = admin_client.post(
        _schedules(project_id, unit_id),
        json={
            "revision_code": "R0",
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "1.0000"}],
        },
    )

    assert response.status_code == 409


def test_one_area_type_appears_once_per_schedule(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    response = admin_client.post(
        _schedules(project_id, unit_id),
        json={
            "revision_code": "R0",
            "values": [
                {"area_type_id": area_types["INTERNAL"], "raw_area": "100.0000"},
                {"area_type_id": area_types["INTERNAL"], "raw_area": "200.0000"},
            ],
        },
    )

    assert response.status_code == 422
    assert "only once" in response.json()["detail"]


def test_a_negative_area_is_refused(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    response = admin_client.post(
        _schedules(project_id, unit_id),
        json={
            "revision_code": "R0",
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "-1.0000"}],
        },
    )

    assert response.status_code == 422


def test_design_engineering_drafts_but_does_not_approve(
    db: Session,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    engineer_member: object,
) -> None:
    """Given the measurer, then they may record and not approve their own work."""
    from tests.factories import client_for

    client = client_for("design2@example.com")
    created = client.post(
        _schedules(project_id, unit_id),
        json={
            "revision_code": "R0",
            "reconciled": True,
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "100.0000"}],
        },
    )
    assert created.status_code == 201, created.text

    response = client.post(f"{_schedules(project_id, unit_id)}/{created.json()['id']}/approve")

    assert response.status_code == 403


@pytest.mark.parametrize("body", [{"status": "approved"}, {"approved_at": "2026-01-01T00:00:00Z"}])
def test_a_schedule_update_refuses_what_it_does_not_declare(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    body: dict[str, object],
) -> None:
    """Given a status on a PATCH, then 422: approval is its own endpoint."""
    schedule = admin_client.post(
        _schedules(project_id, unit_id),
        json={
            "revision_code": "R0",
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "100.0000"}],
        },
    ).json()["id"]

    response = admin_client.patch(f"{_schedules(project_id, unit_id)}/{schedule}", json=body)

    assert response.status_code == 422
