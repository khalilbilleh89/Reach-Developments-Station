"""Constrained configurable fields.

A custom field adds a fact the product did not anticipate. It can never redefine
one it did, and it can never execute anything. Both limits are what separate a
metadata system from a dynamic-schema engine, and both are tested here.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import CustomFieldDefinition, UnitCustomFieldValue
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, inventory_url, unit_payload


@pytest.fixture(autouse=True)
def _finalised_basis(operational_project: str) -> None:
    """Every test here configures a real project's fields, so its basis is set.

    Field definitions scoped to a project are that project's configuration and
    wait for the same finalisation inventory does. Declaring it once here keeps
    each test about the field rule it is actually testing.
    """


def _definitions(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/field-definitions"


def _unit_values(project_id: str, unit_id: str) -> str:
    return f"{inventory_url(project_id)}/units/{unit_id}/custom-values"


def _field(project: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "entity_type": "unit",
        "field_key": "ceiling_height",
        "display_label": "Ceiling height",
        "data_type": "decimal",
        "unit_of_measure": "m",
        "scope_type": "project",
        "project_id": project,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Definitions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("data_type", ["text", "integer", "decimal", "boolean", "date", "option"])
def test_every_supported_data_type_can_be_defined(
    admin_client: TestClient, project_id: str, data_type: str
) -> None:
    payload = _field(project_id, field_key=f"field_{data_type}", data_type=data_type)
    if data_type == "option":
        payload["options"] = [{"code": "A", "label": "Option A"}]

    response = admin_client.post(_definitions(project_id), json=payload)

    assert response.status_code == 201, response.text
    assert response.json()["data_type"] == data_type


@pytest.mark.parametrize(
    "field_key",
    [
        "id",
        "unit_reference",
        "commercial_status",
        "legal_status",
        "pricing_approved",
        "contract_price",
        "cost",
    ],
)
def test_a_custom_field_cannot_redefine_a_core_field(
    admin_client: TestClient, project_id: str, field_key: str
) -> None:
    """Given a core name, then the definition is refused.

    A custom ``commercial_status`` would look like core truth in every export
    while obeying none of the rules that protect it.
    """
    response = admin_client.post(
        _definitions(project_id), json=_field(project_id, field_key=field_key)
    )

    assert response.status_code == 422
    assert "core field name" in response.json()["detail"]


def test_a_field_key_is_a_lowercase_machine_name(admin_client: TestClient, project_id: str) -> None:
    response = admin_client.post(
        _definitions(project_id), json=_field(project_id, field_key="Ceiling Height!")
    )

    assert response.status_code == 422


def test_a_field_key_is_immutable(admin_client: TestClient, project_id: str) -> None:
    """Given a PATCH naming the key, then 422: values are stored against it."""
    definition = admin_client.post(_definitions(project_id), json=_field(project_id)).json()["id"]

    for body in (
        {"field_key": "other_key"},
        {"data_type": "text"},
        {"entity_type": "project"},
        {"scope_type": "global"},
    ):
        response = admin_client.patch(f"{_definitions(project_id)}/{definition}", json=body)
        assert response.status_code == 422, body


def test_two_definitions_that_could_reach_one_record_are_refused(
    admin_client: TestClient, project_id: str
) -> None:
    """Given a global field, then a project one with the same key is ambiguous.

    Rather than inventing a precedence rule nobody would remember, the second
    definition is refused and says which one it collides with.
    """
    admin_client.post(
        _definitions(project_id),
        json=_field(project_id, scope_type="global", project_id=None),
    )

    response = admin_client.post(_definitions(project_id), json=_field(project_id))

    assert response.status_code == 409
    assert "already defined at global scope" in response.json()["detail"]


def test_two_projects_may_define_the_same_key(
    admin_client: TestClient,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
    inventory_reference_data: None,
) -> None:
    from tests.modules.conftest import project_payload

    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    ).json()["id"]
    admin_client.patch(f"{PROJECTS}/{other}", json={"status": "predevelopment"})
    admin_client.post(_definitions(project_id), json=_field(project_id))

    response = admin_client.post(_definitions(other), json=_field(other))

    assert response.status_code == 201, response.text


def test_a_sensitive_field_needs_an_explicit_audience(
    admin_client: TestClient, project_id: str
) -> None:
    response = admin_client.post(_definitions(project_id), json=_field(project_id, sensitive=True))

    assert response.status_code == 422
    assert "roles that may see it" in response.json()["detail"]


def test_a_visibility_rule_must_name_real_roles(admin_client: TestClient, project_id: str) -> None:
    response = admin_client.post(
        _definitions(project_id),
        json=_field(project_id, visible_role_keys=["chief_wizard"]),
    )

    assert response.status_code == 422
    assert "roles that do not exist" in response.json()["detail"]


def test_an_invalid_pattern_is_refused(admin_client: TestClient, project_id: str) -> None:
    response = admin_client.post(
        _definitions(project_id),
        json=_field(project_id, data_type="text", regex_pattern="([unclosed"),
    )

    assert response.status_code == 422
    assert "not a valid pattern" in response.json()["detail"]


def test_updating_a_definition_increments_its_version(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    definition = admin_client.post(_definitions(project_id), json=_field(project_id)).json()["id"]

    response = admin_client.patch(
        f"{_definitions(project_id)}/{definition}",
        json={"display_label": "Ceiling height (m)", "change_reason": "Clearer label"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "custom_field.updated")).one()
    assert event.reason == "Clearer label"


def test_a_definition_is_never_deleted(admin_client: TestClient, project_id: str) -> None:
    definition = admin_client.post(_definitions(project_id), json=_field(project_id)).json()["id"]

    assert admin_client.delete(f"{_definitions(project_id)}/{definition}").status_code == 404


def test_a_project_manager_defines_only_their_own_projects_fields(
    db: Session, admin_client: TestClient, project_id: str, manager: object
) -> None:
    from tests.modules.conftest import grant_access

    grant_access(admin_client, project_id, manager)
    client = client_for(manager.email)

    assert client.post(_definitions(project_id), json=_field(project_id)).status_code == 201
    refused = client.post(
        _definitions(project_id),
        json=_field(project_id, field_key="global_note", scope_type="global", project_id=None),
    )
    assert refused.status_code == 403
    assert "their own project only" in refused.json()["detail"]


# --------------------------------------------------------------------------- #
# Values
# --------------------------------------------------------------------------- #


def test_a_decimal_value_is_stored_and_returned_as_a_string(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given 2.85, then 2.85 comes back — never a binary float."""
    admin_client.post(_definitions(project_id), json=_field(project_id))

    response = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "2.8500"}}
    )

    assert response.status_code == 200, response.text
    value = next(row for row in response.json() if row["field_key"] == "ceiling_height")
    assert value["value"] == "2.8500"
    assert Decimal(value["value"]) == Decimal("2.85")


@pytest.mark.parametrize(
    ("data_type", "bad_value"),
    [
        ("integer", "two"),
        ("decimal", "not-a-number"),
        ("boolean", "maybe"),
        ("date", "31/12/2026"),
    ],
)
def test_a_wrongly_typed_value_is_refused(
    admin_client: TestClient, project_id: str, unit_id: str, data_type: str, bad_value: str
) -> None:
    admin_client.post(
        _definitions(project_id), json=_field(project_id, field_key="probe", data_type=data_type)
    )

    response = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"probe": bad_value}}
    )

    assert response.status_code == 422


def test_bounds_are_enforced(admin_client: TestClient, project_id: str, unit_id: str) -> None:
    admin_client.post(
        _definitions(project_id),
        json=_field(project_id, minimum_value="2.0000", maximum_value="4.0000"),
    )

    too_low = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "1.5000"}}
    )
    too_high = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "9.0000"}}
    )

    assert too_low.status_code == 422
    assert too_high.status_code == 422
    assert "cannot be below" in too_low.json()["detail"]


def test_a_pattern_is_enforced(admin_client: TestClient, project_id: str, unit_id: str) -> None:
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id, field_key="kitchen_code", data_type="text", regex_pattern="^K-[0-9]{3}$"
        ),
    )

    bad = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"kitchen_code": "nope"}}
    )
    good = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"kitchen_code": "K-123"}}
    )

    assert bad.status_code == 422
    assert good.status_code == 200, good.text


def test_only_an_active_option_may_be_assigned(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    definition = admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="kitchen_package",
            data_type="option",
            options=[
                {"code": "STD", "label": "Standard"},
                {"code": "LUX", "label": "Luxury"},
            ],
        ),
    ).json()["id"]
    admin_client.patch(
        f"{_definitions(project_id)}/{definition}",
        json={"options": [{"code": "STD", "label": "Standard"}]},
    )

    unknown = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"kitchen_package": "PREMIUM"}}
    )
    retired = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"kitchen_package": "LUX"}}
    )

    assert unknown.status_code == 422
    assert "is not an option" in unknown.json()["detail"]
    assert retired.status_code == 422
    assert "no longer an active option" in retired.json()["detail"]


def test_a_required_value_cannot_be_cleared(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    admin_client.post(_definitions(project_id), json=_field(project_id, required=True))
    admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "2.8500"}}
    )

    response = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": None}}
    )

    assert response.status_code == 422
    assert "is required" in response.json()["detail"]


def test_clearing_an_optional_value_keeps_the_row(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given a cleared value, then the row survives with a null.

    A physically deleted row loses the audit trail's other side.
    """
    admin_client.post(_definitions(project_id), json=_field(project_id))
    admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "2.8500"}}
    )

    admin_client.put(_unit_values(project_id, unit_id), json={"values": {"ceiling_height": None}})

    row = db.scalars(select(UnitCustomFieldValue)).one()
    assert row.value_json is None
    assert row.unique_value is None


def test_a_value_change_records_both_sides(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    admin_client.post(_definitions(project_id), json=_field(project_id))
    admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "2.8500"}}
    )
    admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "3.0000"}}
    )

    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == "custom_field_value.updated")
        .order_by(AuditEvent.occurred_at)
    ).all()
    assert events[-1].before_data["value"] == "2.8500"
    assert events[-1].after_data["value"] == "3.0000"


def test_an_unknown_field_key_is_refused(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    response = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"invented": "x"}}
    )

    assert response.status_code == 422
    assert "not a field of this record" in response.json()["detail"]


def test_a_values_request_refuses_what_it_does_not_declare(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    response = admin_client.put(
        _unit_values(project_id, unit_id), json={"value": {"ceiling_height": "2.85"}}
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("scope", "extra", "fragment"),
    [
        ("unit_type", {}, "needs project_id and unit_type_code"),
        ("unit_type", {"project": True}, "needs unit_type_code"),
        ("country", {}, "needs country_pack_id"),
        ("project", {"project": True, "unit_type_code": "2BR"}, "does not take unit_type_code"),
        ("global", {"project": True}, "does not take project_id"),
    ],
)
def test_a_scope_must_name_exactly_what_it_is_scoped_to(
    admin_client: TestClient, project_id: str, scope: str, extra: dict, fragment: str
) -> None:
    """Given a scope missing or overreaching its columns, then it is refused.

    A unit-type field with no unit type would sit in the table looking
    configured and apply to nothing. The database refuses it too; this is the
    difference between a 422 that names the column and a 500 that names nothing.
    """
    payload = _field(project_id, field_key="scoped_note", scope_type=scope, project_id=None)
    if extra.get("project"):
        payload["project_id"] = project_id
    if "unit_type_code" in extra:
        payload["unit_type_code"] = extra["unit_type_code"]

    response = admin_client.post(_definitions(project_id), json=payload)

    assert response.status_code == 422, response.text
    assert fragment in response.json()["detail"]


def test_a_unit_type_scoped_field_reaches_only_that_unit_type(
    admin_client: TestClient, project_id: str, floor_id: str, unit_id: str
) -> None:
    """Given a field scoped to 2BR, then a 3BR unit never sees it."""
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="balcony_glazing",
            display_label="Balcony glazing",
            data_type="text",
            scope_type="unit_type",
            project_id=project_id,
            unit_type_code="2BR",
        ),
    )
    other = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(
            floor_id, unit_number="102", unit_reference="B1-102", unit_type_code="3BR"
        ),
    ).json()["id"]

    two_bed = admin_client.get(_unit_values(project_id, unit_id)).json()
    three_bed = admin_client.get(_unit_values(project_id, other)).json()

    assert "balcony_glazing" in {row["field_key"] for row in two_bed}
    assert "balcony_glazing" not in {row["field_key"] for row in three_bed}


def test_a_restricted_field_never_reaches_an_unauthorised_reader(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given a sensitive field, then its value is absent from the raw body.

    Asserted against the response text, not a flag: a value hidden by the
    interface has still left the server.
    """
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="acquisition_note",
            data_type="text",
            sensitive=True,
            visible_role_keys=["system_admin", "finance"],
        ),
    )
    admin_client.put(
        _unit_values(project_id, unit_id),
        json={"values": {"acquisition_note": "Vendor accepted 12% below asking"}},
    )

    advisor = make_user(db, email="advisor9@example.com", roles=("sales_advisor",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{advisor.id}")
    response = client_for(advisor.email).get(_unit_values(project_id, unit_id))

    assert response.status_code == 200
    assert "12% below asking" not in response.text
    assert "acquisition_note" not in response.text


def test_a_restricted_fields_name_never_reaches_the_completeness_list(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given a sensitive release requirement, then only its name is withheld.

    An outstanding item still has to be counted, or two people looking at the
    same unit disagree about whether it is ready. What a reader without the role
    must not learn is that the development tracks something called "Litigation
    exposure" at all — a label is as revealing as a value here.
    """
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="litigation_exposure",
            display_label="Litigation exposure",
            data_type="text",
            sensitive=True,
            required_for_release=True,
            visible_role_keys=["system_admin", "legal"],
        ),
    )

    advisor = make_user(db, email="advisor10@example.com", roles=("sales_advisor",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{advisor.id}")
    response = client_for(advisor.email).get(f"{inventory_url(project_id)}/units/{unit_id}")

    assert response.status_code == 200
    assert "Litigation exposure" not in response.text
    assert "A field restricted to other roles" in response.text
    # Withheld, not dropped: the requirement still counts against completeness.
    assert response.json()["is_complete"] is False


def test_a_reader_with_the_role_sees_the_restricted_requirement_by_name(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="litigation_exposure",
            display_label="Litigation exposure",
            data_type="text",
            sensitive=True,
            required_for_release=True,
            visible_role_keys=["system_admin", "legal"],
        ),
    )

    counsel = make_user(db, email="counsel@example.com", roles=("legal",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{counsel.id}")
    response = client_for(counsel.email).get(f"{inventory_url(project_id)}/units/{unit_id}")

    assert response.status_code == 200
    assert "Litigation exposure" in response.json()["missing_requirements"]


def test_an_unauthorised_writer_is_refused(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    admin_client.post(
        _definitions(project_id),
        json=_field(project_id, editable_role_keys=["system_admin"]),
    )
    engineer = make_user(db, email="eng9@example.com", roles=("design_engineering",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{engineer.id}")

    response = client_for(engineer.email).put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "2.8500"}}
    )

    assert response.status_code == 403


def test_an_approval_required_field_needs_a_reason(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    admin_client.post(_definitions(project_id), json=_field(project_id, approval_required=True))

    without = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "2.8500"}}
    )
    with_reason = admin_client.put(
        _unit_values(project_id, unit_id),
        json={"values": {"ceiling_height": "2.8500"}, "change_reason": "Surveyed"},
    )

    assert without.status_code == 422
    assert with_reason.status_code == 200, with_reason.text


def test_a_release_required_custom_field_blocks_completeness(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> None:
    """Given a field required for release, then the unit is incomplete without it.

    The one transition-specific rule the field system implements — a concrete
    requirement, not a dependency expression language.
    """
    from tests.modules.conftest import approve_areas

    approve_areas(admin_client, project_id, unit_id, area_types)
    admin_client.post(_definitions(project_id), json=_field(project_id, required_for_release=True))

    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    assert body["is_complete"] is False
    assert "Ceiling height" in body["missing_requirements"]

    admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "2.8500"}}
    )
    after = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    assert after["is_complete"] is True


def test_project_and_parcel_values_are_separate_tables(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given a project and a parcel field, then each lands in its own table."""
    from tests.modules.conftest import parcel_payload

    parcel = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id, entity_type="project", field_key="master_plan_ref", data_type="text"
        ),
    )
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id, entity_type="land_parcel", field_key="survey_ref", data_type="text"
        ),
    )

    assert (
        admin_client.put(
            f"{PROJECTS}/{project_id}/custom-values",
            json={"values": {"master_plan_ref": "MP-1"}},
        ).status_code
        == 200
    )
    assert (
        admin_client.put(
            f"{PROJECTS}/{project_id}/parcels/{parcel}/custom-values",
            json={"values": {"survey_ref": "SV-1"}},
        ).status_code
        == 200
    )

    from app.modules.inventory.models import (
        LandParcelCustomFieldValue,
        ProjectCustomFieldValue,
    )

    assert db.scalars(select(ProjectCustomFieldValue)).one().value_json == "MP-1"
    assert db.scalars(select(LandParcelCustomFieldValue)).one().value_json == "SV-1"


def test_a_definition_is_scoped_to_its_entity(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given a project field, then a unit cannot carry it."""
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id, entity_type="project", field_key="master_plan_ref", data_type="text"
        ),
    )

    response = admin_client.put(
        _unit_values(project_id, unit_id), json={"values": {"master_plan_ref": "MP-1"}}
    )

    assert response.status_code == 422


def test_no_definition_carries_an_expression(db: Session) -> None:
    """Given the definition table, then it has nowhere to put executable text.

    The absence is the feature: a configuration screen that can run something is
    a programming environment with no code review.
    """
    columns = set(CustomFieldDefinition.__table__.columns.keys())

    for forbidden in ("formula", "expression", "script", "dependency_rule", "computed_sql"):
        assert forbidden not in columns


def test_a_nullable_json_column_stores_sql_null_not_json_null(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given no visibility rule, then the column is SQL NULL in the database.

    SQLAlchemy's default is to store Python ``None`` in a JSONB column as the
    JSON scalar ``null``, which is not SQL NULL: ``'null'::jsonb IS NOT NULL``
    is true. Every ``IS NULL`` check — the sensitive-field constraint here, and
    the partial index behind unique custom values — would quietly stop meaning
    what it says.
    """
    from sqlalchemy import text

    admin_client.post(_definitions(project_id), json=_field(project_id))
    admin_client.put(_unit_values(project_id, unit_id), json={"values": {"ceiling_height": None}})

    assert (
        db.execute(
            text("SELECT count(*) FROM custom_field_definitions WHERE visible_role_keys IS NULL")
        ).scalar()
        == 1
    )
    assert (
        db.execute(
            text("SELECT count(*) FROM unit_custom_field_values WHERE value_json IS NULL")
        ).scalar()
        == 1
    )


def test_the_database_also_refuses_a_sensitive_field_without_an_audience(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given the service check is bypassed, then the constraint still refuses it.

    The service gives the operator a readable message; this is the backstop that
    holds even if a future path forgets to ask.
    """
    from sqlalchemy.exc import IntegrityError

    from app.modules.access.models import User

    admin = db.scalars(select(User)).first()
    db.add(
        CustomFieldDefinition(
            entity_type="unit",
            field_key="leaky",
            display_label="Leaky",
            data_type="text",
            scope_type="project",
            project_id=project_id,
            sensitive=True,
            created_by_user_id=admin.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
