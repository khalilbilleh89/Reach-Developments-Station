"""Phases: the delivery stages of a project, and the unit of inventory access.

A phase is what a restricted member is granted or denied, so these tests treat
it as a security boundary as much as a piece of hierarchy.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Phase
from tests.modules.conftest import PROJECTS, inventory_url


def test_a_phase_is_created_with_a_normalized_code(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Given a lower-case code, then it is stored upper-cased."""
    response = admin_client.post(
        f"{inventory_url(project_id)}/phases",
        json={"code": "phase-1", "name": "Phase 1", "sequence": 1},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["code"] == "PHASE-1"
    assert body["status"] == "planning"
    assert body["is_active"] is True


def test_a_duplicate_phase_code_is_refused(
    admin_client: TestClient, project_id: str, phase_id: str
) -> None:
    """Given the code already exists in this project, then the second is refused."""
    response = admin_client.post(
        f"{inventory_url(project_id)}/phases", json={"code": "PHASE-1", "name": "Again"}
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_two_projects_may_use_the_same_phase_code(
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    """Given another project, then PHASE-1 means something different there."""
    from tests.modules.conftest import project_payload

    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    ).json()["id"]
    admin_client.patch(f"{PROJECTS}/{other}", json={"status": "predevelopment"})

    response = admin_client.post(
        f"{inventory_url(other)}/phases", json={"code": "PHASE-1", "name": "Phase 1"}
    )

    assert response.status_code == 201, response.text


def test_a_phase_code_cannot_be_changed(
    admin_client: TestClient, project_id: str, phase_id: str
) -> None:
    """Given a code on a PATCH body, then the whole request is refused.

    Rows point at the identifier, so the code is a label — but a label people
    quote in correspondence, and silently accepting a change to it would leave
    two documents naming different things.
    """
    response = admin_client.patch(
        f"{inventory_url(project_id)}/phases/{phase_id}", json={"code": "PHASE-2"}
    )

    assert response.status_code == 422


def test_planned_dates_must_be_in_order(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    response = admin_client.post(
        f"{inventory_url(project_id)}/phases",
        json={
            "code": "PHASE-9",
            "name": "Backwards",
            "planned_start": "2027-01-01",
            "planned_completion": "2026-01-01",
        },
    )

    assert response.status_code == 422
    assert "before planned start" in response.json()["detail"]


def test_updating_a_phase_is_audited(
    admin_client: TestClient, project_id: str, phase_id: str, db: Session
) -> None:
    """Given a status change, then the before and after are both recorded."""
    response = admin_client.patch(
        f"{inventory_url(project_id)}/phases/{phase_id}", json={"status": "active"}
    )

    assert response.status_code == 200, response.text
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "phase.updated")).one()
    assert event.before_data["status"] == "planning"
    assert event.after_data["status"] == "active"


def test_a_phase_with_active_buildings_cannot_be_deactivated(
    admin_client: TestClient, project_id: str, phase_id: str, building_id: str
) -> None:
    """Given live inventory beneath it, then retiring the phase is refused.

    There is deliberately no cascade: quietly deactivating every building and
    unit under a phase is a larger change than the request said it was.
    """
    response = admin_client.patch(
        f"{inventory_url(project_id)}/phases/{phase_id}", json={"is_active": False}
    )

    assert response.status_code == 409
    assert "still has active buildings" in response.json()["detail"]


def test_a_phase_is_never_deleted(admin_client: TestClient, project_id: str, phase_id: str) -> None:
    response = admin_client.delete(f"{inventory_url(project_id)}/phases/{phase_id}")

    assert response.status_code == 404


def test_an_unknown_phase_is_not_found(admin_client: TestClient, project_id: str) -> None:
    import uuid

    response = admin_client.get(f"{inventory_url(project_id)}/phases/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Phase not found."}


def test_a_phase_of_another_project_is_not_found(
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    """Given a real phase identifier under the wrong project, then 404.

    The substitution attack: a phase the caller may see, reached through a path
    it does not belong to.
    """
    from tests.modules.conftest import project_payload

    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    ).json()["id"]

    response = admin_client.get(f"{inventory_url(other)}/phases/{phase_id}")

    assert response.status_code == 404


@pytest.mark.parametrize("role", ["design_engineering", "sales_operations", "sales_advisor"])
def test_only_project_configurers_create_phases(
    db: Session,
    admin_client: TestClient,
    project_id: str,
    inventory_reference_data: None,
    role: str,
) -> None:
    """Given a member without the role, then creating a phase is a 403."""
    from tests.factories import client_for, make_user

    user = make_user(db, email=f"{role}@example.com", roles=(role,))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")

    response = client_for(user.email).post(
        f"{inventory_url(project_id)}/phases", json={"code": "PHASE-2", "name": "Two"}
    )

    assert response.status_code == 403


def test_a_manager_may_create_a_phase(
    db: Session,
    admin_client: TestClient,
    manager: User,
    project_id: str,
    inventory_reference_data: None,
) -> None:
    from tests.factories import client_for
    from tests.modules.conftest import grant_access

    grant_access(admin_client, project_id, manager)

    response = client_for(manager.email).post(
        f"{inventory_url(project_id)}/phases", json={"code": "PHASE-2", "name": "Two"}
    )

    assert response.status_code == 201, response.text


def test_creating_a_phase_records_the_creator(
    admin_client: TestClient, admin: User, project_id: str, phase_id: str, db: Session
) -> None:
    phase = db.scalars(select(Phase)).one()
    assert phase.created_by_user_id == admin.id
