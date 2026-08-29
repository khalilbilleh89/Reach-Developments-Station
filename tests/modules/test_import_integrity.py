"""What a clean import report has to be worth.

The interface promises validate, fix, apply. That is only a promise if a row
called valid is a row apply will write — and if "create" cannot quietly turn out
to have meant "edit that one". Every case here reached apply, PostgreSQL or the
wrong unit before anybody said no during validation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit, UnitAreaSchedule
from tests.modules.conftest import PROJECTS, inventory_url, unit_payload

CREATE_HEADER = "action,phase_code,building_code,floor_code,unit_number,unit_reference,asset_class"
MOVE_HEADER = "action,unit_id,phase_code,building_code,floor_code,unit_number"


def _validate(client: TestClient, project_id: str, csv: str, **params: object) -> dict:
    query = "&".join(f"{key}={str(value).lower()}" for key, value in params.items())
    response = client.post(
        f"{inventory_url(project_id)}/import/validate?{query}",
        content=csv.encode(),
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _apply(client: TestClient, project_id: str, csv: str, **params: object) -> dict:
    query = "&".join(f"{key}={str(value).lower()}" for key, value in params.items())
    response = client.post(
        f"{inventory_url(project_id)}/import/apply?{query}",
        content=csv.encode(),
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _issue(report: dict, column: str) -> dict | None:
    return next((issue for issue in report["issues"] if issue["column"] == column), None)


@pytest.fixture
def second_floor(admin_client: TestClient, project_id: str, building_id: str) -> str:
    response = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "02", "label": "Second floor"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _hold(client: TestClient, project_id: str, unit_id: str) -> None:
    response = client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={
            "to_status": "held",
            "effective_date": "2026-02-01",
            "reason": "Broker hold pending decision",
        },
    )
    assert response.status_code == 201, response.text


# --------------------------------------------------------------------------- #
# Create rows and unit identity
# --------------------------------------------------------------------------- #


def test_a_create_row_carrying_a_unit_id_is_refused(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given create and an existing identifier, then the row is refused.

    The apply path decides what to do from the identifier alone, so a file in
    create mode could edit a unit it never claimed to be touching — which is
    precisely what create mode exists to rule out.
    """
    csv = f"action,unit_id,bedrooms\ncreate,{unit_id},4\n"

    report = _validate(admin_client, project_id, csv, mode="create")

    assert report["error_count"] == 1
    issue = _issue(report, "unit_id")
    assert issue is not None
    assert issue["message"] == (
        "A create row must not contain unit_id. Existing units are updated "
        "only with action=update in upsert mode."
    )


def test_a_create_row_with_a_unit_id_writes_nothing(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given the same file applied, then nothing about the unit changes.

    Every column a create needs is present, so the row is otherwise perfectly
    valid — which is the point. Counted as a create and applied as an update, it
    was a way to edit a unit through an import that said it created one.
    """
    header = "action,unit_id,unit_number,unit_reference,asset_class,bedrooms"
    csv = f"{header}\ncreate,{unit_id},101,B1-101,apartment,4\n"

    report = _apply(admin_client, project_id, csv, mode="create")

    assert report["applied"] is False
    db.expire_all()
    unit = db.scalars(select(Unit)).one()
    assert unit.bedrooms == 2
    updates = db.scalars(select(AuditEvent).where(AuditEvent.action == "unit.updated")).all()
    assert updates == []


def test_upsert_mode_also_refuses_a_create_row_with_a_unit_id(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Upsert is where updates are allowed, and they are still spelled ``update``."""
    csv = f"action,unit_id,bedrooms\ncreate,{unit_id},4\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    assert report["error_count"] == 1
    assert _issue(report, "unit_id") is not None


def test_an_omitted_action_with_a_unit_id_is_still_an_update(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """The documented convenience stands: an identifier and no action means update."""
    csv = f"action,unit_id,bedrooms\n,{unit_id},4\n"

    report = _apply(admin_client, project_id, csv, mode="upsert")

    assert (report["applied"], report["update_count"], report["create_count"]) == (True, 1, 0)
    db.expire_all()
    assert db.scalars(select(Unit)).one().bedrooms == 4


# --------------------------------------------------------------------------- #
# The floor and number a row actually produces
# --------------------------------------------------------------------------- #


def test_a_create_row_into_an_occupied_number_is_refused(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given a number already standing on that floor, then validation refuses it.

    A different reference does not make it a different position: floor and
    number are what ``uq_units_floor_id_unit_number`` compares.
    """
    csv = f"{CREATE_HEADER}\ncreate,PHASE-1,B1,01,101,B1-999,apartment\n"

    report = _validate(admin_client, project_id, csv, mode="create")

    issue = _issue(report, "unit_number")
    assert issue is not None
    assert issue["message"] == "Unit number '101' already exists on the destination floor."


def test_the_same_number_on_another_floor_is_accepted(
    admin_client: TestClient, project_id: str, unit_id: str, second_floor: str
) -> None:
    """Uniqueness is per floor, and the check must not become per building."""
    csv = f"{CREATE_HEADER}\ncreate,PHASE-1,B1,02,101,B1-201,apartment\n"

    report = _validate(admin_client, project_id, csv, mode="create")

    assert report["error_count"] == 0, report["issues"]
    assert report["valid_rows"] == 1


def test_moving_a_unit_onto_an_occupied_number_is_refused(
    admin_client: TestClient, project_id: str, unit_id: str, second_floor: str, db: Session
) -> None:
    """Given a blank number, then the number it keeps is the one that is judged.

    This is the case the batch-level duplicate check could never see: nothing in
    the row says 101, and the destination floor already has a 101.
    """
    other = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(second_floor, unit_number="101", unit_reference="B1-201"),
    )
    assert other.status_code == 201, other.text
    csv = f"{MOVE_HEADER}\nupdate,{unit_id},PHASE-1,B1,02,\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    issue = _issue(report, "unit_number")
    assert issue is not None
    assert issue["message"] == "Unit number '101' already exists on the destination floor."


def test_a_refused_move_never_reaches_the_database_constraint(
    admin_client: TestClient, project_id: str, unit_id: str, second_floor: str, db: Session
) -> None:
    """Given apply rather than validate, then it is still a report, not a 500."""
    admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(second_floor, unit_number="101", unit_reference="B1-201"),
    )
    csv = f"{MOVE_HEADER}\nupdate,{unit_id},PHASE-1,B1,02,\n"

    report = _apply(admin_client, project_id, csv, mode="upsert")

    assert report["applied"] is False
    db.expire_all()
    moved = db.scalars(select(Unit).where(Unit.id == unit_id)).one()
    assert str(moved.floor_id) != second_floor


def test_a_unit_keeping_its_own_floor_and_number_is_valid(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """A unit is never a collision with itself."""
    csv = f"{MOVE_HEADER}\nupdate,{unit_id},PHASE-1,B1,01,101\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    assert report["error_count"] == 0, report["issues"]


def test_a_move_to_a_free_number_is_valid(
    admin_client: TestClient, project_id: str, unit_id: str, second_floor: str, db: Session
) -> None:
    """The check refuses collisions, not moves."""
    csv = f"{MOVE_HEADER}\nupdate,{unit_id},PHASE-1,B1,02,\n"

    report = _apply(admin_client, project_id, csv, mode="upsert")

    assert report["applied"] is True, report["issues"]
    db.expire_all()
    assert str(db.scalars(select(Unit)).one().floor_id) == second_floor


# --------------------------------------------------------------------------- #
# The hierarchy freeze, said during validation
# --------------------------------------------------------------------------- #


def test_moving_a_held_unit_is_refused_during_validation(
    admin_client: TestClient, project_id: str, unit_id: str, second_floor: str
) -> None:
    """Given a held unit, then the move is refused before anything is written.

    Apply always refused this. Reporting the file clean and then abandoning the
    load on row 180 is the failure mode validation exists to remove.
    """
    _hold(admin_client, project_id, unit_id)
    csv = f"{MOVE_HEADER}\nupdate,{unit_id},PHASE-1,B1,02,\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    issue = _issue(report, "floor_code")
    assert issue is not None
    assert issue["message"] == "A unit can only be moved while it is unreleased."


def test_moving_an_available_unit_is_refused_during_validation(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    second_floor: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Released is further along than held, and the freeze applies the same."""
    from tests.modules.conftest import make_releasable

    make_releasable(admin_client, project_id, unit_id, area_types, db)
    released = admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={"to_status": "available", "effective_date": "2026-02-01"},
    )
    assert released.status_code == 201, released.text
    csv = f"{MOVE_HEADER}\nupdate,{unit_id},PHASE-1,B1,02,\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    assert _issue(report, "floor_code") is not None


def test_moving_an_unreleased_unit_stays_valid(
    admin_client: TestClient, project_id: str, unit_id: str, second_floor: str
) -> None:
    csv = f"{MOVE_HEADER}\nupdate,{unit_id},PHASE-1,B1,02,\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    assert report["error_count"] == 0, report["issues"]


# --------------------------------------------------------------------------- #
# Area revisions
# --------------------------------------------------------------------------- #


def test_a_revision_the_unit_already_has_is_refused_during_validation(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Given R0 already recorded, then a second R0 is caught before apply."""
    from tests.modules.conftest import approve_areas

    approve_areas(admin_client, project_id, unit_id, area_types)
    header = "action,unit_id,area_revision,area:INTERNAL"
    csv = f"{header}\nupdate,{unit_id},R0,105.0000\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    issue = _issue(report, "area_revision")
    assert issue is not None
    assert issue["message"] == "Revision 'R0' already exists for this unit."
    assert len(db.scalars(select(UnitAreaSchedule)).all()) == 1


def test_two_rows_cannot_record_one_revision_for_one_unit(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    """The file has to say one thing, and the database cannot settle it in advance."""
    header = "action,unit_id,area_revision,area:INTERNAL"
    csv = f"{header}\nupdate,{unit_id},R1,105.0000\nupdate,{unit_id},R1,106.0000\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    issue = _issue(report, "area_revision")
    assert issue is not None
    assert issue["message"] == "Row 2 already records revision 'R1' for this unit."


def test_a_new_revision_stays_valid(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    from tests.modules.conftest import approve_areas

    approve_areas(admin_client, project_id, unit_id, area_types)
    header = "action,unit_id,area_revision,area:INTERNAL"
    csv = f"{header}\nupdate,{unit_id},R1,105.0000\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    assert report["error_count"] == 0, report["issues"]


# --------------------------------------------------------------------------- #
# Unique custom values
# --------------------------------------------------------------------------- #


@pytest.fixture
def serial_field(admin_client: TestClient, project_id: str, operational_project: str) -> str:
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/field-definitions",
        json={
            "entity_type": "unit",
            "field_key": "meter_serial",
            "display_label": "Meter serial",
            "data_type": "text",
            "scope_type": "project",
            "project_id": project_id,
            "is_unique": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_a_unique_value_another_unit_holds_is_refused_during_validation(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    second_floor: str,
    serial_field: str,
) -> None:
    """Given SN-0001 already claimed, then the report says so.

    The UNIQUE index still decides between two simultaneous writers. It just
    cannot tell an operator which of 247 rows to fix.
    """
    other = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(second_floor, unit_number="201", unit_reference="B1-201"),
    ).json()["id"]
    admin_client.put(
        f"{inventory_url(project_id)}/units/{other}/custom-values",
        json={"values": {"meter_serial": "SN-0001"}},
    )
    csv = f"action,unit_id,custom:meter_serial\nupdate,{unit_id},SN-0001\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    issue = _issue(report, "custom:meter_serial")
    assert issue is not None
    assert "another unit already uses this value" in issue["message"]


def test_two_rows_cannot_claim_one_unique_value(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    second_floor: str,
    serial_field: str,
) -> None:
    """Neither row has been written, so only the file can settle this."""
    other = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(second_floor, unit_number="201", unit_reference="B1-201"),
    ).json()["id"]
    header = "action,unit_id,custom:meter_serial"
    csv = f"{header}\nupdate,{unit_id},SN-0001\nupdate,{other},sn-0001\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    issue = _issue(report, "custom:meter_serial")
    assert issue is not None
    assert "row 2 already claims this value" in issue["message"]


def test_a_unit_keeping_its_own_unique_value_is_valid(
    admin_client: TestClient, project_id: str, unit_id: str, serial_field: str
) -> None:
    """Re-stating a value a unit already holds is not a clash with itself."""
    admin_client.put(
        f"{inventory_url(project_id)}/units/{unit_id}/custom-values",
        json={"values": {"meter_serial": "SN-0001"}},
    )
    csv = f"action,unit_id,custom:meter_serial\nupdate,{unit_id},SN-0001\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    assert report["error_count"] == 0, report["issues"]


def test_a_free_unique_value_is_valid(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    second_floor: str,
    serial_field: str,
    db: Session,
) -> None:
    other = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(second_floor, unit_number="201", unit_reference="B1-201"),
    ).json()["id"]
    admin_client.put(
        f"{inventory_url(project_id)}/units/{other}/custom-values",
        json={"values": {"meter_serial": "SN-0001"}},
    )
    csv = f"action,unit_id,custom:meter_serial\nupdate,{unit_id},SN-0002\n"

    report = _apply(admin_client, project_id, csv, mode="upsert")

    assert report["applied"] is True, report["issues"]
