"""Validation has to be able to promise what apply will do.

The contract the interface advertises is validate, fix, apply. It is only worth
anything if a row reported valid is a row that will be written — otherwise the
operator fixes the file until the report is clean and then meets a second, worse
list of errors halfway through a 247-row load.

Every case here is a value that used to reach apply, or PostgreSQL, before
anybody said no.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Unit
from tests.modules.conftest import PROJECTS, inventory_url

HEADER = (
    "action,phase_code,phase_name,building_code,building_name,floor_code,"
    "floor_label,unit_number,unit_reference,asset_class"
)


def _row(number: str, reference: str, extra: str = "") -> str:
    return f"create,PHASE-1,One,B1,Tower,01,First,{number},{reference},apartment{extra}"


def _validate(
    client: TestClient, project_id: str, csv: str, *, mode: str = "create", **query: object
) -> dict:
    params = f"mode={mode}&create_missing_hierarchy=true"
    for key, value in query.items():
        params += f"&{key}={value}"
    response = client.post(
        f"{inventory_url(project_id)}/import/validate?{params}",
        content=csv,
        headers={"content-type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _issue(report: dict, column: str) -> dict | None:
    return next((issue for issue in report["issues"] if issue["column"] == column), None)


# --------------------------------------------------------------------------- #
# Area columns
# --------------------------------------------------------------------------- #


def test_a_malformed_measured_date_is_caught_before_apply(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """``31/12/2026`` is a date somewhere; it is not one here.

    Apply parsed this with ``date.fromisoformat`` long after validation had
    called the row good.
    """
    csv = f"{HEADER},area_revision,area_measured_date\n{_row('101', 'B1-101', ',R1,31/12/2026')}\n"

    report = _validate(admin_client, project_id, csv)

    assert report["error_count"] >= 1
    assert _issue(report, "area_measured_date") is not None


def test_a_reconciliation_flag_that_is_neither_true_nor_false_is_refused(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """ "maybe" means the operator does not know, and false is not that answer.

    Coercing it silently would record that somebody checked the drawing against
    the measurement when nobody did.
    """
    csv = f"{HEADER},area_revision,area_reconciled\n{_row('101', 'B1-101', ',R1,maybe')}\n"

    report = _validate(admin_client, project_id, csv)

    assert _issue(report, "area_reconciled") is not None


# --------------------------------------------------------------------------- #
# Numeric bounds
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("bedrooms", "-3"),
        ("bathrooms", "-1"),
        ("sequence", "-5"),
        ("plot_coverage_fraction", "1.5"),
    ],
)
def test_a_value_outside_the_domain_fails_validation_not_a_check_constraint(
    admin_client: TestClient,
    project_id: str,
    inventory_reference_data: None,
    column: str,
    value: str,
) -> None:
    """The same bounds the request schema applies, applied to the file.

    Otherwise a typo becomes a 500 from a database CHECK, discovered after the
    batch has already begun.
    """
    csv = f"{HEADER},{column}\n{_row('101', 'B1-101', f',{value}')}\n"

    report = _validate(admin_client, project_id, csv)

    assert _issue(report, column) is not None, report["issues"]


def test_a_value_inside_the_domain_still_loads(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    csv = f"{HEADER},bedrooms\n{_row('101', 'B1-101', ',3')}\n"

    report = _validate(admin_client, project_id, csv)

    assert report["error_count"] == 0, report["issues"]


# --------------------------------------------------------------------------- #
# <CLEAR>
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("column", ["unit_number", "unit_reference", "asset_class"])
def test_a_column_a_unit_cannot_exist_without_may_not_be_cleared(
    admin_client: TestClient,
    project_id: str,
    inventory_reference_data: None,
    unit_id: str,
    column: str,
) -> None:
    """Given ``<CLEAR>`` on identity, then the row is refused with a reason.

    A NOT NULL violation discovered during apply says "null value in column"
    and rolls back the whole batch. This says which column and why.
    """
    csv = f"action,unit_id,{column}\nupdate,{unit_id},<CLEAR>\n"

    report = _validate(admin_client, project_id, csv, mode="upsert")

    assert _issue(report, column) is not None, report["issues"]
    assert "cannot be cleared" in _issue(report, column)["message"]


# --------------------------------------------------------------------------- #
# Hierarchy declared inside the file
# --------------------------------------------------------------------------- #


def test_one_file_cannot_name_the_same_new_phase_two_ways(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Neither name exists yet, so the database cannot arbitrate. The file must.

    "First row wins" would silently load two hundred units under a name the
    operator did not choose and would not see.
    """
    csv = (
        f"{HEADER}\n"
        "create,PHASE-1,North Phase,B1,Tower,01,First,101,B1-101,apartment\n"
        "create,PHASE-1,South Phase,B1,Tower,01,First,102,B1-102,apartment\n"
    )

    report = _validate(admin_client, project_id, csv)

    assert _issue(report, "phase_name") is not None, report["issues"]
    assert "two ways" in _issue(report, "phase_name")["message"]


def test_the_same_check_covers_buildings_and_floors(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    csv = (
        f"{HEADER}\n"
        "create,PHASE-1,One,B1,North Tower,01,First,101,B1-101,apartment\n"
        "create,PHASE-1,One,B1,South Tower,01,Ground,102,B1-102,apartment\n"
    )

    report = _validate(admin_client, project_id, csv)

    assert _issue(report, "building_name") is not None
    assert _issue(report, "floor_label") is not None


def test_a_file_may_declare_one_name_on_every_row(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Repeating the same name is how a CSV works, and is not a conflict."""
    csv = (
        f"{HEADER}\n"
        "create,PHASE-1,One,B1,Tower,01,First,101,B1-101,apartment\n"
        "create,PHASE-1,One,B1,Tower,01,First,102,B1-102,apartment\n"
    )

    report = _validate(admin_client, project_id, csv)

    assert report["error_count"] == 0, report["issues"]


def test_units_cannot_be_loaded_into_a_retired_phase(
    admin_client: TestClient, project_id: str, phase_id: str, inventory_reference_data: None
) -> None:
    """A retired level was retired deliberately; a file does not reopen it."""
    admin_client.patch(f"{inventory_url(project_id)}/phases/{phase_id}", json={"is_active": False})
    csv = f"{HEADER}\n{_row('101', 'B1-101')}\n"

    report = _validate(admin_client, project_id, csv)

    assert _issue(report, "phase_code") is not None
    assert "not active" in _issue(report, "phase_code")["message"]


def test_two_different_floors_are_not_the_same_floor(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Building 'B1' + floor '01' and building 'B' + floor '101' are different.

    The duplicate check used to concatenate the two codes, so those two collided
    and a legitimate second row was rejected as a duplicate.
    """
    csv = (
        f"{HEADER}\n"
        "create,PHASE-1,One,B1,Tower One,01,First,7,U-7,apartment\n"
        "create,PHASE-1,One,B,Tower B,101,Hundred and first,7,U-8,apartment\n"
    )

    report = _validate(admin_client, project_id, csv)

    assert report["error_count"] == 0, report["issues"]


# --------------------------------------------------------------------------- #
# Custom values
# --------------------------------------------------------------------------- #


def _define(client: TestClient, project_id: str, **overrides: object) -> dict:
    payload: dict[str, object] = {
        "entity_type": "unit",
        "field_key": "ceiling_height",
        "display_label": "Ceiling height",
        "data_type": "decimal",
        "scope_type": "project",
        "project_id": project_id,
    }
    payload.update(overrides)
    response = client.post(f"{PROJECTS}/{project_id}/field-definitions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_custom_value_of_the_wrong_type_fails_validation(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """The header knew the column; nobody checked the value under it."""
    _define(admin_client, project_id)
    csv = f"{HEADER},custom:ceiling_height\n{_row('101', 'B1-101', ',not-a-number')}\n"

    report = _validate(admin_client, project_id, csv)

    assert _issue(report, "custom:ceiling_height") is not None, report["issues"]


def test_a_custom_option_outside_the_option_set_fails_validation(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    _define(
        admin_client,
        project_id,
        field_key="finish_grade",
        display_label="Finish grade",
        data_type="option",
        options=[{"code": "A", "label": "Grade A"}],
    )
    csv = f"{HEADER},custom:finish_grade\n{_row('101', 'B1-101', ',Z')}\n"

    report = _validate(admin_client, project_id, csv)

    assert _issue(report, "custom:finish_grade") is not None, report["issues"]


def test_a_custom_value_outside_its_bounds_fails_validation(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    _define(admin_client, project_id, minimum_value="2.0000", maximum_value="4.0000")
    csv = f"{HEADER},custom:ceiling_height\n{_row('101', 'B1-101', ',9.5')}\n"

    report = _validate(admin_client, project_id, csv)

    assert _issue(report, "custom:ceiling_height") is not None, report["issues"]


def test_a_unit_type_scoped_field_applies_only_to_that_unit_type(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Given a 2BR field on a 3BR row, then the row is refused.

    Which type the row produces is decided by the file when it names one, and by
    the existing unit when it does not — so applicability cannot be settled from
    the header alone.
    """
    _define(
        admin_client,
        project_id,
        field_key="balcony_glazing",
        display_label="Balcony glazing",
        data_type="text",
        scope_type="unit_type",
        unit_type_code="2BR",
    )
    csv = (
        f"{HEADER},unit_type_code,custom:balcony_glazing\n{_row('101', 'B1-101', ',3BR,double')}\n"
    )

    report = _validate(admin_client, project_id, csv)

    assert _issue(report, "custom:balcony_glazing") is not None, report["issues"]


def test_a_unit_type_scoped_field_loads_for_the_type_it_belongs_to(
    admin_client: TestClient, project_id: str, inventory_reference_data: None, db: Session
) -> None:
    _define(
        admin_client,
        project_id,
        field_key="balcony_glazing",
        display_label="Balcony glazing",
        data_type="text",
        scope_type="unit_type",
        unit_type_code="2BR",
    )
    csv = (
        f"{HEADER},unit_type_code,custom:balcony_glazing\n{_row('101', 'B1-101', ',2BR,double')}\n"
    )

    report = _validate(admin_client, project_id, csv)

    assert report["error_count"] == 0, report["issues"]


def test_an_approval_required_field_is_judged_the_same_way_twice(
    admin_client: TestClient, project_id: str, inventory_reference_data: None, db: Session
) -> None:
    """Given a field needing a reason, then validate and apply agree it has one.

    Apply supplies its own reason for a bulk load. Validation judging the same
    field without one would refuse a row apply would happily write — the same
    disagreement as the other direction, and just as misleading.
    """
    _define(
        admin_client,
        project_id,
        field_key="valuation_note",
        display_label="Valuation note",
        data_type="text",
        approval_required=True,
    )
    csv = f"{HEADER},custom:valuation_note\n{_row('101', 'B1-101', ',Reviewed')}\n"

    report = _validate(admin_client, project_id, csv)
    assert report["error_count"] == 0, report["issues"]

    applied = admin_client.post(
        f"{inventory_url(project_id)}/import/apply?mode=create&create_missing_hierarchy=true",
        content=csv,
        headers={"content-type": "text/csv"},
    )

    assert applied.status_code == 200, applied.text
    assert applied.json()["applied"] is True


def test_a_clean_report_survives_apply(
    admin_client: TestClient, project_id: str, inventory_reference_data: None, db: Session
) -> None:
    """The contract itself: a file called valid is a file that loads.

    Everything above exists so that this holds for the cases that used to slip
    through — the report and the write now consult the same rules.
    """
    _define(admin_client, project_id, minimum_value="2.0000", maximum_value="4.0000")
    csv = (
        f"{HEADER},bedrooms,plot_coverage_fraction,area_revision,area_measured_date,"
        f"area_reconciled,custom:ceiling_height\n"
        f"{_row('101', 'B1-101', ',3,0.4500,R1,2026-08-01,true,3.2000')}\n"
    )

    report = _validate(admin_client, project_id, csv)
    assert report["error_count"] == 0, report["issues"]
    assert report["valid_rows"] == 1

    applied = admin_client.post(
        f"{inventory_url(project_id)}/import/apply?mode=create&create_missing_hierarchy=true",
        content=csv,
        headers={"content-type": "text/csv"},
    )

    assert applied.status_code == 200, applied.text
    assert applied.json()["applied"] is True
    assert db.scalars(select(Unit)).one().bedrooms == 3
