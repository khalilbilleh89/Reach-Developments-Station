"""Inventory may not begin until a project's basis is settled.

The companion to ``test_project_basis``, which covers the other half of the
same rule: that module proves the basis stops being editable once the project
leaves setup, and this one proves inventory cannot exist before it does.

A unit's type, orientation, view class and furnishing are all validated against
the project's country pack, and PR-MVP-02 deliberately lets that pack change
freely while the project is still in ``setup``. Building inventory first would
leave every one of those codes describing a jurisdiction the project has since
left, and the projects module cannot notice: it does not import inventory, and
giving it that import to close one hole is a circular dependency bought cheap.

So the rule runs the other way. Leaving setup is what finalises the basis, and
inventory starts after it. A project can never return to setup, so the sequence
cannot be walked backwards.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import CustomFieldDefinition, Phase, Unit
from app.modules.projects.models import Project
from tests.modules.conftest import PROJECTS, inventory_url

SETUP_DETAIL = "Finalize the project setup before creating inventory."


def _leave_setup(client: TestClient, project_id: str) -> None:
    response = client.patch(f"{PROJECTS}/{project_id}", json={"status": "predevelopment"})
    assert response.status_code == 200, response.text


def test_a_project_in_setup_cannot_create_a_phase(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given a project still in setup, then inventory is refused with a reason."""
    response = admin_client.post(
        f"{inventory_url(project_id)}/phases", json={"code": "PHASE-1", "name": "Phase One"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == SETUP_DETAIL
    assert db.scalars(select(Phase)).all() == []


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/buildings",
            {"phase_id": "00000000-0000-0000-0000-000000000000", "code": "B1", "name": "B"},
        ),
        (
            "/floors",
            {"building_id": "00000000-0000-0000-0000-000000000000", "code": "01", "label": "F"},
        ),
        (
            "/units",
            {
                "floor_id": "00000000-0000-0000-0000-000000000000",
                "unit_number": "101",
                "unit_reference": "B1-101",
                "asset_class": "apartment",
            },
        ),
        (
            "/area-types",
            {
                "code": "INT",
                "label": "Internal",
                "area_role": "internal",
                "weight_factor": "1.000000",
            },
        ),
        ("/sub-assets", {"asset_reference": "P-1", "asset_type": "parking"}),
    ],
)
def test_every_inventory_creation_waits_for_the_basis(
    admin_client: TestClient, project_id: str, path: str, payload: dict
) -> None:
    """The refusal is uniform: no route is the one that forgot.

    Each payload names an identifier that does not exist. The point is that the
    basis is checked before any of that matters — a 404 here would mean the
    route reached lookup with the project still unsettled.
    """
    response = admin_client.post(f"{inventory_url(project_id)}{path}", json=payload)

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == SETUP_DETAIL


def test_a_project_in_setup_cannot_be_loaded_from_a_file(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given a CSV, then it is refused before a line of it is read.

    Validating first would be worse than refusing: a report calling two hundred
    rows valid, followed by an apply that refuses them, is the report telling
    the lie.
    """
    csv = (
        "action,phase_code,phase_name,building_code,building_name,floor_code,"
        "floor_label,unit_number,unit_reference,asset_class\n"
        "create,PHASE-1,One,B1,Tower,01,First,101,B1-101,apartment\n"
    )
    for route in ("validate", "apply"):
        response = admin_client.post(
            f"{inventory_url(project_id)}/import/{route}?mode=create&create_missing_hierarchy=true",
            content=csv,
            headers={"content-type": "text/csv"},
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == SETUP_DETAIL

    assert db.scalars(select(Unit)).all() == []
    assert db.scalars(select(Phase)).all() == []


def test_a_project_scoped_field_waits_for_the_basis(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """A project's own configurable fields are its configuration, so they wait."""
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/field-definitions",
        json={
            "entity_type": "unit",
            "field_key": "ceiling_height",
            "display_label": "Ceiling height",
            "data_type": "decimal",
            "scope_type": "project",
            "project_id": project_id,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == SETUP_DETAIL
    assert db.scalars(select(CustomFieldDefinition)).all() == []


def test_a_unit_type_scoped_field_waits_for_the_basis(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Given a unit-type scope, then it waits too: the type is configured.

    ``inventory_reference_data`` has already moved this project out of setup, so
    the test creates its own project to be sure the refusal is about the basis
    and not about a missing unit type.
    """
    from tests.modules.conftest import project_payload

    project = admin_client.get(f"{PROJECTS}/{project_id}").json()
    fresh = admin_client.post(
        PROJECTS,
        json=project_payload(
            project["country_pack_id"], project["base_currency_id"], code="SECOND"
        ),
    ).json()["id"]

    response = admin_client.post(
        f"{PROJECTS}/{fresh}/field-definitions",
        json={
            "entity_type": "unit",
            "field_key": "balcony_glazing",
            "display_label": "Balcony glazing",
            "data_type": "text",
            "scope_type": "unit_type",
            "project_id": fresh,
            "unit_type_code": "2BR",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == SETUP_DETAIL


def test_global_configuration_is_never_blocked_by_a_projects_setup(
    admin_client: TestClient, project_id: str
) -> None:
    """Given a project in setup, then a global field can still be defined.

    The rule is about a project's operational inventory, not about system
    configuration. An administrator maintaining a global field is not doing
    anything to this project, and must not be stopped because of the screen they
    happened to navigate from.
    """
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/field-definitions",
        json={
            "entity_type": "unit",
            "field_key": "heritage_listed",
            "display_label": "Heritage listed",
            "data_type": "boolean",
            "scope_type": "global",
        },
    )

    assert response.status_code == 201, response.text


def test_leaving_setup_opens_inventory(admin_client: TestClient, project_id: str) -> None:
    """Given the project moves to pre-development, then inventory may start."""
    _leave_setup(admin_client, project_id)

    response = admin_client.post(
        f"{inventory_url(project_id)}/phases", json={"code": "PHASE-1", "name": "Phase One"}
    )

    assert response.status_code == 201, response.text


def test_the_basis_is_locked_once_the_project_leaves_setup(
    admin_client: TestClient, project_id: str, country_pack_id: str, db: Session
) -> None:
    """The two rules meet: inventory starts where the basis stops moving.

    This is the whole point of the sequence. Before the transition the pack can
    change and there is no inventory to invalidate; after it there is inventory
    and the pack is fixed. There is no window where both are true.
    """
    _leave_setup(admin_client, project_id)
    project = db.scalars(select(Project)).one()
    original = project.country_pack_id

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"country_pack_id": str(country_pack_id)}
    )

    assert response.status_code in (200, 409)
    db.expire_all()
    assert db.scalars(select(Project)).one().country_pack_id == original


def test_a_project_still_cannot_return_to_setup(admin_client: TestClient, project_id: str) -> None:
    """Otherwise the whole sequence is reversible and guarantees nothing."""
    _leave_setup(admin_client, project_id)

    response = admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "setup"})

    assert response.status_code == 409


def test_a_refused_creation_writes_no_audit_event(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """A refusal is not an event. Nothing happened, so nothing is recorded."""
    from app.modules.audit.models import AuditEvent

    admin_client.post(
        f"{inventory_url(project_id)}/phases", json={"code": "PHASE-1", "name": "Phase One"}
    )

    assert db.scalars(select(AuditEvent).where(AuditEvent.action.like("phase.%"))).all() == []
