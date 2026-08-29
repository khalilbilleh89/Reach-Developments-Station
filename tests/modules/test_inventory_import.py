"""Bulk inventory load: validate reads, apply commits, and never half of either.

Two rules carry most of these tests. **Validate writes nothing** — an operator
must be able to check a file without changing the catalogue. And **apply is one
transaction** — a 247-row file with one bad row leaves nothing behind, because a
half-loaded development is worse than a refused one: nobody can tell which half
is real.

Identity is the UUID. An update matches on ``unit_id`` and never on the unit
reference, which is editable and would otherwise let a renumbering overwrite the
wrong row.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Building, Floor, Phase, Unit, UnitAreaSchedule
from tests.modules.conftest import PROJECTS, inventory_url


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


HEADER = (
    "action,phase_code,phase_name,building_code,building_name,floor_code,floor_label,"
    "unit_number,unit_reference,asset_class,unit_type_code,bedrooms"
)


def _row(number: str, reference: str, **overrides: str) -> str:
    values = {
        "action": "create",
        "phase_code": "PHASE-1",
        "phase_name": "Phase 1",
        "building_code": "B1",
        "building_name": "Building 1",
        "floor_code": "01",
        "floor_label": "First floor",
        "unit_number": number,
        "unit_reference": reference,
        "asset_class": "apartment",
        "unit_type_code": "2BR",
        "bedrooms": "2",
    }
    values.update(overrides)
    return ",".join(values[column] for column in HEADER.split(","))


def _file(*rows: str) -> str:
    return "\n".join([HEADER, *rows]) + "\n"


def test_a_template_is_offered(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    response = admin_client.get(f"{inventory_url(project_id)}/import/template")

    assert response.status_code == 200
    body = response.json()
    assert body["filename"].endswith(".csv")
    assert "unit_reference" in body["content"]
    # No pricing columns: there is no price to import yet.
    assert "price" not in body["content"]


def test_validation_writes_nothing(
    admin_client: TestClient, project_id: str, inventory_reference_data: None, db: Session
) -> None:
    """Given a perfectly valid file, then validating it creates no rows."""
    report = _validate(
        admin_client,
        project_id,
        _file(_row("101", "B1-101")),
        create_missing_hierarchy=True,
    )

    assert report["applied"] is False
    assert report["valid_rows"] == 1
    assert report["error_count"] == 0
    assert db.scalars(select(Unit)).all() == []
    assert db.scalars(select(Phase)).all() == []


def test_apply_creates_the_hierarchy_and_the_units(
    admin_client: TestClient, project_id: str, inventory_reference_data: None, db: Session
) -> None:
    report = _apply(
        admin_client,
        project_id,
        _file(_row("101", "B1-101"), _row("102", "B1-102"), _row("201", "B1-201", floor_code="02")),
        create_missing_hierarchy=True,
    )

    assert report["applied"] is True
    assert report["create_count"] == 3
    assert len(db.scalars(select(Unit)).all()) == 3
    assert len(db.scalars(select(Phase)).all()) == 1
    assert len(db.scalars(select(Building)).all()) == 1
    assert len(db.scalars(select(Floor)).all()) == 2


def test_an_existing_hierarchy_is_reused_not_duplicated(
    admin_client: TestClient, project_id: str, floor_id: str, db: Session
) -> None:
    """Given the phase already exists, then the import loads into it."""
    _apply(
        admin_client,
        project_id,
        _file(_row("102", "B1-102")),
        create_missing_hierarchy=True,
    )

    assert len(db.scalars(select(Phase)).all()) == 1
    assert len(db.scalars(select(Floor)).all()) == 1


def test_an_import_never_renames_existing_hierarchy(
    admin_client: TestClient, project_id: str, floor_id: str
) -> None:
    """Given a different phase name, then the row is refused, not applied.

    An import of units has no business renaming the phase they sit in.
    """
    report = _validate(
        admin_client,
        project_id,
        _file(_row("102", "B1-102", phase_name="Renamed phase")),
        create_missing_hierarchy=True,
    )

    assert report["error_count"] >= 1
    assert any(issue["column"] == "phase_name" for issue in report["issues"])


def test_missing_hierarchy_is_refused_unless_asked_for(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    report = _validate(admin_client, project_id, _file(_row("101", "B1-101")))

    assert report["error_count"] == 1
    assert "does not exist" in report["issues"][0]["message"]


def test_a_duplicate_reference_within_the_file_is_caught(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    report = _validate(
        admin_client,
        project_id,
        _file(_row("101", "B1-101"), _row("102", "B1-101")),
        create_missing_hierarchy=True,
    )

    assert report["invalid_rows"] == 1
    assert "Duplicate unit reference" in report["issues"][0]["message"]


def test_a_reference_that_already_exists_is_caught(
    admin_client: TestClient, project_id: str, floor_id: str, unit_id: str
) -> None:
    report = _validate(
        admin_client, project_id, _file(_row("102", "B1-101")), create_missing_hierarchy=True
    )

    assert report["error_count"] == 1
    assert "already exists" in report["issues"][0]["message"]


def test_a_duplicate_number_on_one_floor_is_caught(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    report = _validate(
        admin_client,
        project_id,
        _file(_row("101", "B1-101"), _row("101", "B1-102")),
        create_missing_hierarchy=True,
    )

    assert any("Duplicate unit number" in issue["message"] for issue in report["issues"])


def test_an_unconfigured_unit_type_is_caught(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    report = _validate(
        admin_client,
        project_id,
        _file(_row("101", "B1-101", unit_type_code="MANSION")),
        create_missing_hierarchy=True,
    )

    assert any(issue["column"] == "unit_type_code" for issue in report["issues"])


def test_an_unknown_area_column_is_caught(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    csv = f"{HEADER},area:PENTHOUSE\n{_row('101', 'B1-101')},100\n"

    report = _validate(admin_client, project_id, csv, create_missing_hierarchy=True)

    assert any("not an active area type" in issue["message"] for issue in report["issues"])


def test_an_unknown_core_column_is_an_error(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Given a misspelled column, then the file is refused.

    It is almost always a typo in a column the operator believed was being read,
    and a silent skip would lose the data without saying so.
    """
    csv = f"{HEADER},bedroms\n{_row('101', 'B1-101')},3\n"

    report = _validate(admin_client, project_id, csv, create_missing_hierarchy=True)

    assert any(
        "not a column this import understands" in issue["message"] for issue in report["issues"]
    )


def test_a_header_the_import_cannot_read_leaves_no_row_called_valid(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Given a bad column, then no row is reported as valid.

    Nothing was checked against a header the import could not read, so calling
    a row valid would be a claim nobody made. "12 valid rows" beside "a column
    we do not understand" is exactly the report an operator applies by mistake.
    """
    rows = "\n".join(_row(f"1{index:02d}", f"B1-1{index:02d}") for index in range(1, 13))
    csv = f"{HEADER},bedroms\n" + "\n".join(f"{row},3" for row in rows.split("\n")) + "\n"

    report = _validate(admin_client, project_id, csv, create_missing_hierarchy=True)

    assert report["total_rows"] == 12
    assert report["valid_rows"] == 0
    assert report["invalid_rows"] == 12


def test_one_bad_row_rolls_the_whole_batch_back(
    admin_client: TestClient, project_id: str, inventory_reference_data: None, db: Session
) -> None:
    """Given 199 good rows and one bad, then nothing at all is written."""
    rows = [_row(f"1{index:02d}", f"B1-1{index:02d}") for index in range(1, 200)]
    rows.append(_row("999", "B1-999", unit_type_code="MANSION"))

    report = _apply(admin_client, project_id, _file(*rows), create_missing_hierarchy=True)

    assert report["applied"] is False
    assert report["error_count"] >= 1
    assert db.scalars(select(Unit)).all() == []
    assert db.scalars(select(Phase)).all() == []


def test_an_update_needs_the_unit_id(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given only a reference, then the update is refused.

    The reference is editable, so matching on it would update whichever row
    currently happens to carry the text.
    """
    header = "action,unit_reference,bedrooms"
    csv = f"{header}\nupdate,B1-101,4\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    assert report["error_count"] == 1
    assert "not identity" in report["issues"][0]["message"]


def test_an_upsert_matches_on_the_unit_id_and_keeps_it(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    header = "action,unit_id,unit_reference,bedrooms"
    csv = f"{header}\nupdate,{unit_id},A1-101,4\n"

    report = _apply(admin_client, project_id, csv, mode="upsert")

    assert report["applied"] is True
    assert report["update_count"] == 1
    unit = db.scalars(select(Unit)).one()
    assert str(unit.id) == unit_id
    assert unit.unit_reference == "A1-101"
    assert unit.bedrooms == 4


def test_create_mode_refuses_an_update_row(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    csv = f"action,unit_id,bedrooms\nupdate,{unit_id},4\n"

    report = _validate(admin_client, project_id, csv, mode="create")

    assert report["error_count"] == 1
    assert "create mode" in report["issues"][0]["message"]


def test_an_empty_cell_leaves_a_value_alone_and_clear_removes_it(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given an empty cell and a ``<CLEAR>`` token, then they mean different things.

    Without an explicit token an update could never clear anything, and a blank
    column would wipe every row it touched.
    """
    header = "action,unit_id,bedrooms,unit_type_code"
    _apply(admin_client, project_id, f"{header}\nupdate,{unit_id},,\n", mode="upsert")
    assert db.scalars(select(Unit)).one().bedrooms == 2

    _apply(admin_client, project_id, f"{header}\nupdate,{unit_id},<CLEAR>,\n", mode="upsert")

    db.expire_all()
    unit = db.scalars(select(Unit)).one()
    assert unit.bedrooms is None
    assert unit.unit_type_code == "2BR"


def test_imported_areas_create_a_draft_revision(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    header = "action,unit_id,area_revision,area:INTERNAL,area:BALCONY"
    csv = f"{header}\nupdate,{unit_id},R1,104.5000,12.0000\n"

    _apply(admin_client, project_id, csv, mode="upsert")

    schedule = db.scalars(select(UnitAreaSchedule)).one()
    assert schedule.status == "draft"
    assert schedule.revision_code == "R1"


def test_imported_areas_never_overwrite_an_approved_revision(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Given an approved measurement, then the import adds a revision beside it."""
    from tests.modules.conftest import approve_areas

    approved = approve_areas(admin_client, project_id, unit_id, area_types)
    header = "action,unit_id,area_revision,area:INTERNAL,area:BALCONY"
    _apply(
        admin_client,
        project_id,
        f"{header}\nupdate,{unit_id},R1,999.0000,12.0000\n",
        mode="upsert",
    )

    statuses = {str(row.id): row.status for row in db.scalars(select(UnitAreaSchedule))}
    assert statuses[approved] == "approved"
    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    assert body["area_revision_code"] == "R0"


def test_an_import_cannot_approve_an_unreconciled_revision(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Given approve_area_schedules, then the same rules still apply.

    The import is not a way around approval. An unreconciled revision refuses
    the whole batch, and the message names the row.
    """
    header = "action,unit_id,area_revision,area_reconciled,area:INTERNAL"
    response = admin_client.post(
        f"{inventory_url(project_id)}/import/apply?mode=upsert&approve_area_schedules=true",
        content=f"{header}\nupdate,{unit_id},R1,false,100.0000\n".encode(),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 422
    assert "Row 2" in response.json()["detail"]
    assert "reconciled" in response.json()["detail"]
    assert db.scalars(select(UnitAreaSchedule)).all() == []


def test_approving_through_an_import_needs_the_approving_role(
    db: Session,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    engineer_member: object,
) -> None:
    """Given Design / Engineering, then they may import but not approve areas."""
    from tests.factories import client_for

    header = "action,unit_id,area_revision,area_reconciled,area:INTERNAL,area:BALCONY"
    body = f"{header}\nupdate,{unit_id},R1,true,100.0000,20.0000\n".encode()
    client = client_for("design2@example.com")

    assert (
        client.post(
            f"{inventory_url(project_id)}/import/apply?mode=upsert",
            content=body,
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{inventory_url(project_id)}/import/apply?mode=upsert&approve_area_schedules=true",
            content=body,
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 403
    )


def test_an_import_that_approves_a_reconciled_revision_makes_it_current(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    header = "action,unit_id,area_revision,area_reconciled,area:INTERNAL,area:BALCONY"
    _apply(
        admin_client,
        project_id,
        f"{header}\nupdate,{unit_id},R1,true,100.0000,20.0000\n",
        mode="upsert",
        approve_area_schedules=True,
    )

    assert db.scalars(select(UnitAreaSchedule)).one().status == "approved"


def test_a_spreadsheet_formula_is_stored_as_text(
    admin_client: TestClient, project_id: str, inventory_reference_data: None, db: Session
) -> None:
    """Given ``=1+1`` in a cell, then it is text that starts with an equals sign.

    CSV content is data. Nothing here evaluates a cell.
    """
    _apply(
        admin_client,
        project_id,
        _file(_row("101", "=SUM(A1:A9)")),
        create_missing_hierarchy=True,
    )

    assert db.scalars(select(Unit)).one().unit_reference == "=SUM(A1:A9)"


def test_a_row_limit_is_enforced(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    from app.modules.inventory.import_service import MAX_ROWS

    rows = [_row(str(index), f"B1-{index}") for index in range(MAX_ROWS + 5)]

    report = _validate(admin_client, project_id, _file(*rows), create_missing_hierarchy=True)

    assert report["total_rows"] == MAX_ROWS
    assert any("at most" in issue["message"] for issue in report["issues"])


def test_an_oversized_payload_is_refused(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    from app.modules.inventory.import_service import MAX_BYTES

    response = admin_client.post(
        f"{inventory_url(project_id)}/import/validate",
        content=b"x" * (MAX_BYTES + 1),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 422
    assert "larger than" in response.json()["detail"]


def test_a_restricted_member_cannot_import_into_a_hidden_phase(
    db: Session, admin_client: TestClient, project_id: str, floor_id: str, phase_id: str
) -> None:
    """Given ``selected`` scope with no grant, then the rows are refused."""
    from tests.factories import client_for, make_user

    engineer = make_user(db, email="imp@example.com", roles=("design_engineering",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{engineer.id}")
    admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{engineer.id}/phase-scope",
        json={"phase_scope": "selected"},
    )

    report = _validate(client_for(engineer.email), project_id, _file(_row("102", "B1-102")))

    assert report["error_count"] == 1
    assert "not available to you" in report["issues"][0]["message"]


def test_a_successful_apply_is_audited(
    admin_client: TestClient, project_id: str, inventory_reference_data: None, db: Session
) -> None:
    _apply(admin_client, project_id, _file(_row("101", "B1-101")), create_missing_hierarchy=True)

    batch = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "inventory.import_applied")
    ).one()
    assert batch.after_data["rows"] == 1
    assert db.scalars(select(AuditEvent).where(AuditEvent.action == "unit.created")).one()


def test_only_structure_writers_may_import(
    db: Session, admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    from tests.factories import client_for, make_user

    advisor = make_user(db, email="advisor7@example.com", roles=("sales_advisor",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{advisor.id}")

    response = client_for(advisor.email).post(
        f"{inventory_url(project_id)}/import/validate",
        content=_file(_row("101", "B1-101")).encode(),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 403


def test_an_empty_file_is_refused(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/import/validate",
        content=b"",
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 422
    assert "empty" in response.json()["detail"]


@pytest.mark.parametrize("mode", ["destroy", "merge"])
def test_an_unknown_mode_is_refused(
    admin_client: TestClient, project_id: str, inventory_reference_data: None, mode: str
) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/import/validate?mode={mode}",
        content=_file(_row("101", "B1-101")).encode(),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 422
