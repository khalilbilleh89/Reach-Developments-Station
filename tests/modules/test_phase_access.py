"""Phase-scoped access: the security model PR-MVP-02 deferred until Phase existed.

A member with ``selected`` scope may open the project and sees only the phases
they were granted. Everything beneath an ungranted phase — units, areas,
sub-assets, custom values — answers 404, and never a 403: a 403 would confirm
the identifier names something real, which is what someone enumerating wants.

Two projects' worth of inventory is arranged once here and then attacked from
every route that could leak it.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.inventory.models import UserPhaseAccess
from app.modules.projects.models import UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, inventory_url, unit_payload


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
    db: Session, admin_client: TestClient, project_id: str, two_phases: dict[str, dict[str, str]]
) -> User:
    """A member who may open the project but only sees Phase A."""
    user = make_user(db, email="restricted@example.com", roles=("sales_advisor",))
    assert admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}").status_code == 200
    assert (
        admin_client.patch(
            f"{PROJECTS}/{project_id}/access/{user.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    granted = admin_client.put(
        f"{PROJECTS}/{project_id}/access/{user.id}/phases/{two_phases['PHASE-A']['phase']}"
    )
    assert granted.status_code == 200, granted.text
    return user


def test_existing_memberships_default_to_seeing_every_phase(
    db: Session, admin_client: TestClient, project_id: str, manager: User
) -> None:
    """Given a membership created before phases existed, then it means ``all``.

    Every row that existed before this PR meant "the whole project", and the
    migration default has to keep meaning that.
    """
    admin_client.put(f"{PROJECTS}/{project_id}/access/{manager.id}")

    membership = db.scalars(
        select(UserProjectAccess).where(UserProjectAccess.user_id == manager.id)
    ).one()
    assert membership.phase_scope == "all"


def test_a_restricted_member_lists_only_their_phases(
    project_id: str, two_phases: dict[str, dict[str, str]], restricted: User
) -> None:
    client = client_for(restricted.email)

    phases = client.get(f"{inventory_url(project_id)}/phases").json()

    assert [phase["code"] for phase in phases] == ["PHASE-A"]


def test_an_all_scope_member_lists_every_phase(
    db: Session, admin_client: TestClient, project_id: str, two_phases: dict[str, dict[str, str]]
) -> None:
    user = make_user(db, email="wide@example.com", roles=("sales_advisor",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")

    phases = client_for(user.email).get(f"{inventory_url(project_id)}/phases").json()

    assert {phase["code"] for phase in phases} == {"PHASE-A", "PHASE-B"}


def test_a_system_administrator_sees_every_phase_without_a_grant(
    admin_client: TestClient, project_id: str, two_phases: dict[str, dict[str, str]]
) -> None:
    phases = admin_client.get(f"{inventory_url(project_id)}/phases").json()

    assert len(phases) == 2


@pytest.mark.parametrize(
    "path",
    [
        "/phases/{phase}",
        "/units/{unit}",
        "/units/{unit}/area-schedules",
        "/units/{unit}/status-history",
        "/units/{unit}/custom-values",
    ],
)
def test_every_route_beneath_an_ungranted_phase_answers_404(
    project_id: str, two_phases: dict[str, dict[str, str]], restricted: User, path: str
) -> None:
    """Given Phase B, then nothing under it is reachable and nothing leaks."""
    hidden = two_phases["PHASE-B"]
    url = inventory_url(project_id) + path.format(phase=hidden["phase"], unit=hidden["unit"])

    response = client_for(restricted.email).get(url)

    assert response.status_code == 404
    assert "B2-201" not in response.text


def test_a_hidden_unit_cannot_be_written_either(
    project_id: str, two_phases: dict[str, dict[str, str]], restricted: User
) -> None:
    hidden = two_phases["PHASE-B"]["unit"]

    response = client_for(restricted.email).patch(
        f"{inventory_url(project_id)}/units/{hidden}", json={"bedrooms": 4}
    )

    assert response.status_code in {403, 404}


def test_the_register_never_returns_a_hidden_unit(
    project_id: str, two_phases: dict[str, dict[str, str]], restricted: User
) -> None:
    register = client_for(restricted.email).get(f"{inventory_url(project_id)}/units").json()

    assert register["total"] == 1
    assert [row["unit_reference"] for row in register["units"]] == ["B1-101"]


def test_a_filter_cannot_widen_what_a_restricted_member_sees(
    project_id: str, two_phases: dict[str, dict[str, str]], restricted: User
) -> None:
    """Given a filter naming the hidden phase, then the answer is empty, not 403.

    The narrowing is applied in SQL, so a caller-supplied filter intersects with
    it rather than replacing it.
    """
    hidden = two_phases["PHASE-B"]["phase"]

    register = (
        client_for(restricted.email)
        .get(f"{inventory_url(project_id)}/units?phase_id={hidden}")
        .json()
    )

    assert register["total"] == 0
    assert register["units"] == []


def test_a_guessed_identifier_and_a_real_hidden_one_look_the_same(
    project_id: str, two_phases: dict[str, dict[str, str]], restricted: User
) -> None:
    """Given both, then the responses are byte-identical."""
    client = client_for(restricted.email)
    hidden = client.get(f"{inventory_url(project_id)}/units/{two_phases['PHASE-B']['unit']}")
    guessed = client.get(f"{inventory_url(project_id)}/units/{uuid.uuid4()}")

    assert hidden.status_code == guessed.status_code == 404
    assert hidden.json() == guessed.json()


def test_a_hidden_phases_buildings_and_floors_are_absent(
    project_id: str, two_phases: dict[str, dict[str, str]], restricted: User
) -> None:
    client = client_for(restricted.email)

    buildings = client.get(f"{inventory_url(project_id)}/buildings").json()
    floors = client.get(f"{inventory_url(project_id)}/floors").json()

    assert [row["code"] for row in buildings] == ["B1"]
    assert len(floors) == 1


def test_a_sub_asset_linked_to_a_hidden_unit_is_absent(
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
) -> None:
    for code, key in (("P-A", "PHASE-A"), ("P-B", "PHASE-B")):
        admin_client.post(
            f"{inventory_url(project_id)}/sub-assets",
            json={
                "asset_reference": code,
                "asset_type": "parking",
                "linked_unit_id": two_phases[key]["unit"],
            },
        )

    assets = client_for(restricted.email).get(f"{inventory_url(project_id)}/sub-assets").json()

    assert [asset["asset_reference"] for asset in assets] == ["P-A"]


def test_revoking_a_phase_hides_it_immediately(
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
) -> None:
    response = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{restricted.id}/phases/{two_phases['PHASE-A']['phase']}",
        json={"is_active": False},
    )

    assert response.status_code == 200, response.text
    assert client_for(restricted.email).get(f"{inventory_url(project_id)}/phases").json() == []


def test_regranting_reuses_the_existing_row(
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
    db: Session,
) -> None:
    """Given a revoke and a re-grant, then the pairing keeps one history line."""
    url = f"{PROJECTS}/{project_id}/access/{restricted.id}/phases/{two_phases['PHASE-A']['phase']}"
    admin_client.patch(url, json={"is_active": False})
    admin_client.patch(url, json={"is_active": True})

    rows = db.scalars(select(UserPhaseAccess).where(UserPhaseAccess.user_id == restricted.id)).all()
    assert len(rows) == 1
    assert rows[0].is_active is True


def test_a_phase_grant_needs_a_project_membership(
    db: Session, admin_client: TestClient, project_id: str, two_phases: dict[str, dict[str, str]]
) -> None:
    """Given a user who is not a member, then a phase grant is refused."""
    outsider = make_user(db, email="outsider@example.com", roles=("sales_advisor",))

    response = admin_client.put(
        f"{PROJECTS}/{project_id}/access/{outsider.id}/phases/{two_phases['PHASE-A']['phase']}"
    )

    assert response.status_code == 404
    assert "no access record" in response.json()["detail"]


def test_the_assigned_project_manager_cannot_be_narrowed(
    admin_client: TestClient, project_id: str, manager: User, two_phases: dict[str, dict[str, str]]
) -> None:
    """Given the assigned manager, then narrowing their scope is refused.

    A project manager who can only see half the inventory is not managing the
    project.
    """
    admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"project_manager_user_id": str(manager.id)}
    )

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{manager.id}/phase-scope",
        json={"phase_scope": "selected"},
    )

    assert response.status_code == 409
    assert "sees every phase" in response.json()["detail"]


def test_only_a_system_administrator_administers_phase_access(
    admin_client: TestClient, project_id: str, manager: User, two_phases: dict[str, dict[str, str]]
) -> None:
    """Given a project manager, then phase access is not theirs to grant.

    Membership is security administration, not project editing.
    """
    from tests.modules.conftest import grant_access

    grant_access(admin_client, project_id, manager)
    client = client_for(manager.email)
    phase = two_phases["PHASE-A"]["phase"]

    assert (
        client.patch(
            f"{PROJECTS}/{project_id}/access/{manager.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 403
    )
    assert (
        client.put(f"{PROJECTS}/{project_id}/access/{manager.id}/phases/{phase}").status_code == 403
    )


def test_a_phase_scope_change_is_audited(
    admin_client: TestClient, project_id: str, restricted: User, db: Session
) -> None:
    from app.modules.audit.models import AuditEvent

    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "project_access.phase_scope_changed")
    ).one()
    assert event.before_data["phase_scope"] == "all"
    assert event.after_data["phase_scope"] == "selected"


def test_granting_and_revoking_a_phase_are_both_audited(
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
    db: Session,
) -> None:
    from app.modules.audit.models import AuditEvent

    admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{restricted.id}/phases/{two_phases['PHASE-A']['phase']}",
        json={"is_active": False},
    )

    actions = set(
        db.scalars(
            select(AuditEvent.action).where(
                AuditEvent.action.in_(["phase_access.granted", "phase_access.revoked"])
            )
        )
    )
    assert actions == {"phase_access.granted", "phase_access.revoked"}


def test_a_phase_scope_request_refuses_an_unknown_value(
    admin_client: TestClient, project_id: str, manager: User
) -> None:
    admin_client.put(f"{PROJECTS}/{project_id}/access/{manager.id}")

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{manager.id}/phase-scope",
        json={"phase_scope": "everything"},
    )

    assert response.status_code == 422


def test_the_membership_listing_reports_each_members_phase_scope(
    admin_client: TestClient, project_id: str, manager: User
) -> None:
    """An administrator cannot manage a narrowing they cannot see.

    The access listing is the only screen that administers membership, so the
    scope has to be readable there rather than inferable from a separate call.
    """
    admin_client.put(f"{PROJECTS}/{project_id}/access/{manager.id}")
    admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{manager.id}/phase-scope",
        json={"phase_scope": "selected"},
    )

    rows = admin_client.get(f"{PROJECTS}/{project_id}/access").json()

    assert [row["phase_scope"] for row in rows if row["user_id"] == str(manager.id)] == ["selected"]
