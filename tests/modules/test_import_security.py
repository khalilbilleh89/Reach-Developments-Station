"""What a CSV must not become: a way around the rules the API enforces.

A file is a bulk edit. Every check the ordinary write path makes has to hold
here too, or the import is simply the unauthorised route into the same data —
and the person who finds that will find it before the reviewer does.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, inventory_url, unit_payload

HEADER = (
    "action,unit_id,phase_code,phase_name,building_code,building_name,"
    "floor_code,floor_label,unit_number,unit_reference,asset_class"
)


def _import(
    client: TestClient, project_id: str, csv: str, *, route: str = "validate", **query: object
) -> dict:
    params = "&".join(f"{key}={value}" for key, value in {"mode": "upsert", **query}.items())
    response = client.post(
        f"{inventory_url(project_id)}/import/{route}?{params}",
        content=csv,
        headers={"content-type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def two_phases(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> dict[str, dict[str, str]]:
    """Two phases, each with a building, a floor and one unit."""
    built: dict[str, dict[str, str]] = {}
    for index, code in enumerate(("PHASE-A", "PHASE-B"), start=1):
        phase = admin_client.post(
            f"{inventory_url(project_id)}/phases", json={"code": code, "name": code.title()}
        ).json()["id"]
        building = admin_client.post(
            f"{inventory_url(project_id)}/buildings",
            json={"phase_id": phase, "code": f"B{index}", "name": f"Building {index}"},
        ).json()["id"]
        floor = admin_client.post(
            f"{inventory_url(project_id)}/floors",
            json={"building_id": building, "code": "01", "label": "First"},
        ).json()["id"]
        unit = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(
                floor, unit_number=f"{index}01", unit_reference=f"B{index}-{index}01"
            ),
        ).json()["id"]
        built[code] = {"phase": phase, "building": building, "floor": floor, "unit": unit}
    return built


@pytest.fixture
def restricted(
    db: Session,
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
) -> User:
    """A Design/Engineering user who may load inventory, but only into Phase A."""
    user = make_user(db, email="restricted-import@example.com", roles=("design_engineering",))
    assert admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}").status_code == 200
    assert (
        admin_client.patch(
            f"{PROJECTS}/{project_id}/access/{user.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    assert (
        admin_client.put(
            f"{PROJECTS}/{project_id}/access/{user.id}/phases/{two_phases['PHASE-A']['phase']}"
        ).status_code
        == 200
    )
    return user


# --------------------------------------------------------------------------- #
# Phase scope
# --------------------------------------------------------------------------- #


def test_a_hidden_unit_cannot_be_moved_into_a_visible_phase(
    db: Session,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
) -> None:
    """Given a hidden unit's id and a visible destination, then the row is refused.

    This is the shape of the attack. Naming a destination the caller *may* see
    made the destination check pass, and the unit's own phase was only consulted
    when no destination was given at all — so supplying both moved a unit out of
    a phase the caller was never allowed to open.
    """
    hidden = two_phases["PHASE-B"]["unit"]
    csv = f"{HEADER}\nupdate,{hidden},PHASE-A,Phase-A,B1,Building 1,01,First,101,B1-101,apartment\n"
    client = client_for(restricted.email)

    report = _import(client, project_id, csv)

    assert report["error_count"] >= 1
    assert any("not available to you" in issue["message"] for issue in report["issues"])
    # Nothing that names the hidden phase, its building or its unit reference.
    body = str(report)
    assert "PHASE-B" not in body
    assert "B2-201" not in body

    applied = _import(client, project_id, csv, route="apply")
    assert applied["applied"] is False

    db.expire_all()
    unit = db.scalars(select(Unit).where(Unit.id == uuid.UUID(hidden))).one()
    floor_id = unit.floor_id
    assert str(floor_id) == two_phases["PHASE-B"]["floor"]
    # The fixture's own creation event is expected; nothing from this import is.
    actions = {
        event.action
        for event in db.scalars(select(AuditEvent).where(AuditEvent.entity_id == unit.id))
    }
    assert actions == {"unit.created"}
    assert (
        db.scalars(select(AuditEvent).where(AuditEvent.action == "inventory.import_applied")).all()
        == []
    )


def test_a_visible_unit_still_imports_normally(
    project_id: str, two_phases: dict[str, dict[str, str]], restricted: User
) -> None:
    """The guard narrows; it does not break the caller's own phase."""
    visible = two_phases["PHASE-A"]["unit"]
    csv = (
        f"{HEADER}\nupdate,{visible},PHASE-A,Phase-A,B1,Building 1,01,First,101,B1-101,apartment\n"
    )

    report = _import(client_for(restricted.email), project_id, csv)

    assert report["error_count"] == 0, report["issues"]


# --------------------------------------------------------------------------- #
# Release-control authorization
# --------------------------------------------------------------------------- #


@pytest.fixture
def engineer_member(db: Session, admin_client: TestClient, project_id: str) -> User:
    user = make_user(db, email="csv-engineer@example.com", roles=("design_engineering",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")
    return user


def _release_csv(column: str, value: str) -> str:
    return (
        f"action,phase_code,phase_name,building_code,building_name,floor_code,"
        f"floor_label,unit_number,unit_reference,asset_class,{column}\n"
        f"create,PHASE-1,One,B1,Tower,01,First,101,B1-101,apartment,{value}\n"
    )


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("legal_sale_eligible", "true"),
        ("release_date", "2026-09-01"),
        ("release_batch", "BATCH-1"),
        ("block_reason", "Held for review"),
    ],
)
def test_design_cannot_reach_another_roles_release_control_through_a_file(
    admin_client: TestClient,
    project_id: str,
    inventory_reference_data: None,
    engineer_member: User,
    db: Session,
    column: str,
    value: str,
) -> None:
    """Given a column Design does not own, then the row is refused.

    Uploading a file needs only the structure-writer right, so without this
    check Design/Engineering could set a unit legally saleable — a decision that
    belongs to Legal — through a column they were never allowed to PATCH.
    """
    client = client_for(engineer_member.email)

    report = _import(
        client,
        project_id,
        _release_csv(column, value),
        mode="create",
        create_missing_hierarchy="true",
    )

    assert report["error_count"] >= 1
    assert any(issue["column"] == column for issue in report["issues"])
    assert any("permission" in issue["message"].lower() for issue in report["issues"])

    applied = _import(
        client,
        project_id,
        _release_csv(column, value),
        route="apply",
        mode="create",
        create_missing_hierarchy="true",
    )
    assert applied["applied"] is False
    assert db.scalars(select(Unit)).all() == []


def test_design_may_still_approve_drawings_through_a_file(
    admin_client: TestClient,
    project_id: str,
    inventory_reference_data: None,
    engineer_member: User,
    db: Session,
) -> None:
    """Design owns drawings, and the CSV grants exactly that much and no more."""
    report = _import(
        client_for(engineer_member.email),
        project_id,
        _release_csv("drawings_approved", "true"),
        route="apply",
        mode="create",
        create_missing_hierarchy="true",
    )

    assert report["applied"] is True, report["issues"]
    assert db.scalars(select(Unit)).one().drawings_approved is True


def test_clearing_a_protected_control_is_still_changing_it(
    admin_client: TestClient,
    project_id: str,
    inventory_reference_data: None,
    engineer_member: User,
    unit_id: str,
) -> None:
    """Given ``<CLEAR>``, then the same right is required.

    Emptying a release batch is a change to a release control. Reading only the
    supplied values would have let the clear token through the gate the value
    itself could not pass.
    """
    csv = f"action,unit_id,release_batch\nupdate,{unit_id},<CLEAR>\n"

    report = _import(client_for(engineer_member.email), project_id, csv)

    assert report["error_count"] >= 1
    assert any(issue["column"] == "release_batch" for issue in report["issues"])


def test_a_project_manager_may_use_every_release_control(
    admin_client: TestClient,
    project_id: str,
    inventory_reference_data: None,
    manager: User,
    db: Session,
) -> None:
    admin_client.put(f"{PROJECTS}/{project_id}/access/{manager.id}")
    csv = (
        "action,phase_code,phase_name,building_code,building_name,floor_code,floor_label,"
        "unit_number,unit_reference,asset_class,drawings_approved,legal_sale_eligible,"
        "release_date,release_batch\n"
        "create,PHASE-1,One,B1,Tower,01,First,101,B1-101,apartment,true,true,2026-09-01,BATCH-1\n"
    )

    report = _import(
        client_for(manager.email),
        project_id,
        csv,
        route="apply",
        mode="create",
        create_missing_hierarchy="true",
    )

    assert report["applied"] is True, report["issues"]
    unit = db.scalars(select(Unit)).one()
    assert unit.legal_sale_eligible is True
    assert unit.release_batch == "BATCH-1"


def test_validate_and_apply_agree_about_authorization(
    admin_client: TestClient,
    project_id: str,
    inventory_reference_data: None,
    engineer_member: User,
) -> None:
    """Apply revalidates rather than trusting the earlier call.

    A validate that said no and an apply that said yes would make the validation
    step decorative, and the apply is the one that writes.
    """
    csv = _release_csv("legal_sale_eligible", "true")
    client = client_for(engineer_member.email)

    checked = _import(client, project_id, csv, mode="create", create_missing_hierarchy="true")
    applied = _import(
        client, project_id, csv, route="apply", mode="create", create_missing_hierarchy="true"
    )

    assert checked["error_count"] == applied["error_count"]
    assert applied["applied"] is False


# --------------------------------------------------------------------------- #
# Hidden custom definitions
# --------------------------------------------------------------------------- #


def test_a_hidden_custom_field_is_not_discoverable_through_the_header(
    admin_client: TestClient,
    project_id: str,
    inventory_reference_data: None,
    engineer_member: User,
) -> None:
    """Given a sensitive field, then the header validator gives nothing away.

    A caller who may not see a field must get the same answer for it as for a
    field that does not exist — otherwise the validator answers "does this
    project track something called `owner_litigation_note`?" for anyone who can
    upload a file.
    """
    admin_client.post(
        f"{PROJECTS}/{project_id}/field-definitions",
        json={
            "entity_type": "unit",
            "field_key": "owner_litigation_note",
            "display_label": "Owner litigation note",
            "data_type": "text",
            "scope_type": "project",
            "project_id": project_id,
            "sensitive": True,
            "visible_role_keys": ["system_admin", "legal"],
        },
    )
    client = client_for(engineer_member.email)
    real = f"{HEADER},custom:owner_litigation_note\ncreate,,P,One,B,T,01,F,1,X-1,apartment,x\n"
    invented = f"{HEADER},custom:no_such_field_at_all\ncreate,,P,One,B,T,01,F,1,X-1,apartment,x\n"

    hidden = _import(client, project_id, real, mode="create", create_missing_hierarchy="true")
    unknown = _import(client, project_id, invented, mode="create", create_missing_hierarchy="true")

    hidden_messages = [
        issue["message"] for issue in hidden["issues"] if "owner_litigation_note" in str(issue)
    ]
    unknown_messages = [
        issue["message"] for issue in unknown["issues"] if "no_such_field_at_all" in str(issue)
    ]
    assert hidden_messages, "the hidden field produced no issue at all"
    assert [message.replace("owner_litigation_note", "X") for message in hidden_messages] == [
        message.replace("no_such_field_at_all", "X") for message in unknown_messages
    ]
    assert "Owner litigation note" not in str(hidden)
    assert "sensitive" not in str(hidden).lower()
