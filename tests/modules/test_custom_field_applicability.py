"""When a configurable field applies, where it applies, and who may write it.

Three separate things the metadata claimed and the code did not do: effective
dates that decided nothing, a project listing that showed another country's
configuration, and an ``editable_role_keys`` list the write path never consulted
because a blanket role gate had already answered.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.inventory.models import CustomFieldDefinition, UnitCustomFieldValue
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, inventory_url


@pytest.fixture(autouse=True)
def _finalised_basis(operational_project: str) -> None:
    """These are a project's own fields, so its basis is settled first."""


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
        "scope_type": "project",
        "project_id": project,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Effective dates
# --------------------------------------------------------------------------- #


def test_a_field_that_starts_next_quarter_does_not_apply_yet(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given valid_from in the future, then the field is not there today.

    ``valid_from`` and ``valid_to`` were stored and then consulted by nothing.
    A field scheduled for next quarter appeared in the API, could be written and
    blocked a release, which is precisely what dating it was meant to prevent.
    """
    later = (date.today() + timedelta(days=30)).isoformat()
    admin_client.post(_definitions(project_id), json=_field(project_id, valid_from=later))

    values = admin_client.get(_unit_values(project_id, unit_id)).json()

    assert "ceiling_height" not in {row["field_key"] for row in values}


def test_a_field_that_expired_last_month_no_longer_applies(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    earlier = (date.today() - timedelta(days=30)).isoformat()
    admin_client.post(_definitions(project_id), json=_field(project_id, valid_to=earlier))

    values = admin_client.get(_unit_values(project_id, unit_id)).json()

    assert "ceiling_height" not in {row["field_key"] for row in values}


def test_a_field_in_force_today_applies(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """The window includes its own edges: a field valid today is valid today."""
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            valid_from=date.today().isoformat(),
            valid_to=date.today().isoformat(),
        ),
    )

    values = admin_client.get(_unit_values(project_id, unit_id)).json()

    assert "ceiling_height" in {row["field_key"] for row in values}


def test_a_future_required_field_does_not_block_a_release_today(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """A requirement that has not started is not a requirement.

    Otherwise scheduling a field for next year silently stops every release from
    the moment somebody configures it.
    """
    later = (date.today() + timedelta(days=90)).isoformat()
    admin_client.post(
        _definitions(project_id),
        json=_field(project_id, required_for_release=True, valid_from=later),
    )

    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()

    assert "Ceiling height" not in body["missing_requirements"]


def test_a_future_field_is_not_a_column_the_importer_accepts(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """The CSV reads applicability the same way every other caller does."""
    later = (date.today() + timedelta(days=30)).isoformat()
    admin_client.post(_definitions(project_id), json=_field(project_id, valid_from=later))
    csv = (
        "action,phase_code,phase_name,building_code,building_name,floor_code,floor_label,"
        "unit_number,unit_reference,asset_class,custom:ceiling_height\n"
        "create,PHASE-1,One,B1,Tower,01,First,101,B1-101,apartment,3.2\n"
    )

    report = admin_client.post(
        f"{inventory_url(project_id)}/import/validate?mode=create&create_missing_hierarchy=true",
        content=csv,
        headers={"content-type": "text/csv"},
    ).json()

    assert report["error_count"] >= 1


# --------------------------------------------------------------------------- #
# Country applicability
# --------------------------------------------------------------------------- #


def test_a_projects_field_listing_does_not_show_another_countrys_configuration(
    admin_client: TestClient,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
    db: Session,
) -> None:
    """Given a UAE-only field, then a Jordan project does not list it.

    Country-scoped definitions carry no project id, and the listing asked for
    "this project's, or nobody's" — so every other country's configuration came
    back looking like this project's own.
    """
    other_currency = admin_client.post(
        "/api/v1/settings/currencies", json={"code": "AED", "name": "UAE dirham"}
    ).json()["id"]
    other_pack = admin_client.post(
        "/api/v1/settings/country-packs",
        json={
            "country_code": "AE",
            "name": "United Arab Emirates",
            "locale": "en-AE",
            "timezone": "Asia/Dubai",
            "default_currency_id": other_currency,
            "area_unit": "sqm",
            "fiscal_year_start_month": 1,
        },
    ).json()["id"]

    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="jordan_only",
            display_label="Jordan only",
            scope_type="country",
            project_id=None,
            country_pack_id=country_pack_id,
        ),
    )
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="emirates_only",
            display_label="Emirates only",
            scope_type="country",
            project_id=None,
            country_pack_id=other_pack,
        ),
    )
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="everywhere",
            display_label="Everywhere",
            scope_type="global",
            project_id=None,
        ),
    )

    listing = admin_client.get(_definitions(project_id)).json()

    keys = {definition["field_key"] for definition in listing}
    assert "jordan_only" in keys
    assert "everywhere" in keys
    assert "emirates_only" not in keys


# --------------------------------------------------------------------------- #
# Definition coherence
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload",
    [
        {"minimum_value": "10.0000", "maximum_value": "2.0000"},
        {"valid_from": "2026-12-01", "valid_to": "2026-01-01"},
    ],
)
def test_an_incoherent_definition_is_refused_with_a_sentence(
    admin_client: TestClient, project_id: str, db: Session, payload: dict
) -> None:
    """PostgreSQL refuses these too — as a 500 naming a constraint.

    A person who typed a range backwards deserves to be told which way round it
    goes, not handed an internal server error.
    """
    response = admin_client.post(_definitions(project_id), json=_field(project_id, **payload))

    assert response.status_code == 422, response.text
    assert db.scalars(select(CustomFieldDefinition)).all() == []


@pytest.mark.parametrize(
    ("initial", "patch"),
    [
        ({"minimum_value": "1.0000"}, {"maximum_value": "0.5000"}),
        ({"valid_from": "2026-06-01"}, {"valid_to": "2026-01-01"}),
    ],
)
def test_a_patch_that_would_make_a_definition_incoherent_is_refused(
    admin_client: TestClient, project_id: str, db: Session, initial: dict, patch: dict
) -> None:
    """The row it would leave behind is what is checked, not the half in the body."""
    definition = admin_client.post(
        _definitions(project_id), json=_field(project_id, **initial)
    ).json()

    response = admin_client.patch(f"{_definitions(project_id)}/{definition['id']}", json=patch)

    assert response.status_code == 422, response.text
    db.expire_all()
    stored = db.scalars(select(CustomFieldDefinition)).one()
    assert stored.version == 1


# --------------------------------------------------------------------------- #
# Who may edit
# --------------------------------------------------------------------------- #


@pytest.fixture
def sales_member(db: Session, admin_client: TestClient, project_id: str) -> User:
    user = make_user(db, email="sales-fields@example.com", roles=("sales_operations",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")
    return user


@pytest.fixture
def design_member(db: Session, admin_client: TestClient, project_id: str) -> User:
    user = make_user(db, email="design-fields@example.com", roles=("design_engineering",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")
    return user


def test_a_unit_field_with_no_configured_editors_falls_back_to_the_units_own_writers(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    design_member: User,
    sales_member: User,
) -> None:
    """An unconfigured field behaves like the record it hangs off.

    Not "anyone may write it", which is what the metadata used to say before the
    route's blanket gate quietly corrected it.
    """
    admin_client.post(_definitions(project_id), json=_field(project_id))

    design = client_for(design_member.email).put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "3.2000"}}
    )
    sales = client_for(sales_member.email).put(
        _unit_values(project_id, unit_id), json={"values": {"ceiling_height": "3.4000"}}
    )

    assert design.status_code == 200, design.text
    assert sales.status_code == 403


def test_a_field_configured_for_sales_operations_is_editable_by_sales_operations(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    sales_member: User,
    design_member: User,
    db: Session,
) -> None:
    """Given editable_role_keys, then it means what it says.

    A field configured as editable by Sales Operations that Sales Operations
    could not edit was a lie in the published contract — the route refused
    before the definition was ever consulted.
    """
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="sales_release_note",
            display_label="Sales release note",
            data_type="text",
            editable_role_keys=["sales_operations"],
        ),
    )

    sales = client_for(sales_member.email).put(
        _unit_values(project_id, unit_id), json={"values": {"sales_release_note": "Launch week"}}
    )
    design = client_for(design_member.email).put(
        _unit_values(project_id, unit_id), json={"values": {"sales_release_note": "Mine"}}
    )

    assert sales.status_code == 200, sales.text
    assert design.status_code == 403
    db.expire_all()
    assert db.scalars(select(UnitCustomFieldValue)).one().value_json == "Launch week"


def test_naming_a_role_on_one_field_grants_that_role_nothing_else(
    admin_client: TestClient, project_id: str, unit_id: str, sales_member: User
) -> None:
    """The grant is this field, never the unit's physical facts.

    That separation is the whole reason this is safe to allow: Sales Operations
    writing a release note must not become Sales Operations editing bedrooms.
    """
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="sales_release_note",
            display_label="Sales release note",
            data_type="text",
            editable_role_keys=["sales_operations"],
        ),
    )
    client = client_for(sales_member.email)

    field = client.put(
        _unit_values(project_id, unit_id), json={"values": {"sales_release_note": "Launch week"}}
    )
    core = client.patch(f"{inventory_url(project_id)}/units/{unit_id}", json={"bedrooms": 9})

    assert field.status_code == 200
    assert core.status_code == 403


def test_approval_required_still_overrides_a_configured_role(
    admin_client: TestClient, project_id: str, unit_id: str, sales_member: User
) -> None:
    """A field marked as needing approval stays with the roles that would give it."""
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            field_key="valuation_note",
            display_label="Valuation note",
            data_type="text",
            approval_required=True,
            editable_role_keys=["sales_operations"],
        ),
    )

    response = client_for(sales_member.email).put(
        _unit_values(project_id, unit_id),
        json={"values": {"valuation_note": "x"}, "change_reason": "Because"},
    )

    assert response.status_code == 403


def test_a_narrowed_member_cannot_reach_a_hidden_unit_through_custom_values(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Removing the route's blanket gate must not have opened the phase boundary.

    That boundary is a different rule and still applies to every unit route.
    """
    admin_client.post(
        _definitions(project_id),
        json=_field(project_id, field_key="note", display_label="Note", data_type="text"),
    )
    outsider = make_user(db, email="outside-phase@example.com", roles=("design_engineering",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{outsider.id}")
    admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{outsider.id}/phase-scope",
        json={"phase_scope": "selected"},
    )

    response = client_for(outsider.email).put(
        _unit_values(project_id, unit_id), json={"values": {"note": "mine"}}
    )

    assert response.status_code == 404


def test_a_project_field_with_no_configured_editors_stays_with_the_projects_writers(
    admin_client: TestClient, project_id: str, sales_member: User, design_member: User
) -> None:
    """The route's blanket gate is gone, so the default has to carry the weight.

    A project's own fields belong to whoever maintains the project. Removing the
    gate made the definition the authority; if its default were permissive, that
    change would have quietly widened who may edit a project.
    """
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            entity_type="project",
            field_key="board_reference",
            display_label="Board reference",
            data_type="text",
        ),
    )

    sales = client_for(sales_member.email).put(
        f"{PROJECTS}/{project_id}/custom-values",
        json={"values": {"board_reference": "BR-1"}},
    )
    design = client_for(design_member.email).put(
        f"{PROJECTS}/{project_id}/custom-values",
        json={"values": {"board_reference": "BR-2"}},
    )
    manager = admin_client.put(
        f"{PROJECTS}/{project_id}/custom-values",
        json={"values": {"board_reference": "BR-3"}},
    )

    assert sales.status_code == 403
    # Design maintains units, not the project record itself.
    assert design.status_code == 403
    assert manager.status_code == 200, manager.text


def test_a_parcel_field_keeps_the_same_default(
    admin_client: TestClient, project_id: str, design_member: User
) -> None:
    from tests.modules.conftest import parcel_payload

    parcel = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]
    admin_client.post(
        _definitions(project_id),
        json=_field(
            project_id,
            entity_type="land_parcel",
            field_key="survey_reference",
            display_label="Survey reference",
            data_type="text",
        ),
    )

    response = client_for(design_member.email).put(
        f"{PROJECTS}/{project_id}/parcels/{parcel}/custom-values",
        json={"values": {"survey_reference": "S-1"}},
    )

    assert response.status_code == 403
