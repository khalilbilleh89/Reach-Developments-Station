"""The project record itself: identity, basis and the rules that keep them stable."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.projects.models import Project
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, SETTINGS, project_payload


def test_a_project_is_created_with_its_configured_basis(
    admin_client: TestClient, country_pack_id: str, currency_id: str, reference_data: None
) -> None:
    """Given valid configuration, then the project records it and defaults the fiscal year."""
    response = admin_client.post(
        PROJECTS,
        json=project_payload(
            country_pack_id,
            currency_id,
            project_type_code="RESIDENTIAL",
            planned_start="2026-03-01",
            planned_completion="2028-03-01",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["code"] == "GALINI-BLU"
    assert body["status"] == "setup"
    # Defaulted from the country pack, then owned by the project.
    assert body["fiscal_year_start_month"] == 4
    assert body["base_currency_code"] == "JOD"
    assert body["country_code"] == "JO"
    assert body["planned_duration_days"] == 731


def test_a_project_code_is_normalised_to_upper_case(
    admin_client: TestClient, country_pack_id: str, currency_id: str, reference_data: None
) -> None:
    """Given a lower-case code, then it is stored canonically rather than refused."""
    response = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="galini-blu")
    )

    assert response.status_code == 201
    assert response.json()["code"] == "GALINI-BLU"


def test_a_duplicate_project_code_conflicts(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    """Given an existing code, then a second project cannot take it — in any case."""
    response = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="galini-blu")
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "A project with that code already exists."}


def test_the_database_enforces_code_uniqueness_independently(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given the application check were bypassed, then the database still refuses.

    Uniqueness that lives only in a service is uniqueness two concurrent
    requests can both walk past.
    """
    from sqlalchemy.exc import IntegrityError

    original = db.scalars(select(Project)).one()
    duplicate = Project(
        code=original.code,
        name="Impostor",
        developer_entity="Someone else",
        country_pack_id=original.country_pack_id,
        base_currency_id=original.base_currency_id,
        reporting_currency_id=original.reporting_currency_id,
        created_by_user_id=original.created_by_user_id,
        status="setup",
        fiscal_year_start_month=1,
    )
    db.add(duplicate)

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


@pytest.mark.parametrize("code", ["A", "has space", "toolong" * 10, "bad/char"])
def test_malformed_project_codes_are_rejected(
    admin_client: TestClient, country_pack_id: str, currency_id: str, code: str
) -> None:
    """Given a code outside the permitted set, then creation fails validation."""
    response = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code=code)
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "latitude,longitude",
    [("91.000000", "35.000000"), ("31.000000", "181.000000"), ("-91.000000", "0.000000")],
)
def test_coordinates_outside_the_globe_are_rejected(
    admin_client: TestClient,
    country_pack_id: str,
    currency_id: str,
    latitude: str,
    longitude: str,
) -> None:
    """Given an impossible coordinate, then it is refused."""
    response = admin_client.post(
        PROJECTS,
        json=project_payload(country_pack_id, currency_id, latitude=latitude, longitude=longitude),
    )

    assert response.status_code == 422


def test_valid_coordinates_round_trip_as_exact_decimals(
    admin_client: TestClient, country_pack_id: str, currency_id: str, db: Session
) -> None:
    """Given coordinates, then they are stored as Decimal, never as a float."""
    response = admin_client.post(
        PROJECTS,
        json=project_payload(
            country_pack_id, currency_id, latitude="31.963158", longitude="35.930359"
        ),
    )

    assert response.status_code == 201
    stored = db.scalars(select(Project)).one()
    assert stored.latitude == Decimal("31.963158")
    assert isinstance(stored.latitude, Decimal)


def test_a_completion_before_the_start_is_rejected(
    admin_client: TestClient, country_pack_id: str, currency_id: str
) -> None:
    """Given a reversed window, then the project is refused."""
    response = admin_client.post(
        PROJECTS,
        json=project_payload(
            country_pack_id,
            currency_id,
            planned_start="2028-01-01",
            planned_completion="2026-01-01",
        ),
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Planned completion must not be earlier than planned start."
    }


def test_an_inactive_country_pack_cannot_carry_a_new_project(
    admin_client: TestClient, country_pack_id: str, currency_id: str
) -> None:
    """Given a retired country pack, then no project may be opened against it."""
    admin_client.patch(f"{SETTINGS}/country-packs/{country_pack_id}", json={"is_active": False})

    response = admin_client.post(PROJECTS, json=project_payload(country_pack_id, currency_id))

    assert response.status_code == 422
    assert response.json() == {"detail": "Country pack must be active."}


def test_an_inactive_currency_cannot_be_assigned(
    admin_client: TestClient, country_pack_id: str, currency_id: str
) -> None:
    """Given a retired currency, then it cannot become a project's basis."""
    spare = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "US dollar"}
    ).json()
    admin_client.patch(f"{SETTINGS}/currencies/{spare['id']}", json={"is_active": False})

    response = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, base_currency_id=spare["id"])
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Base currency must be active."}


def test_an_unconfigured_project_type_is_rejected(
    admin_client: TestClient, country_pack_id: str, currency_id: str, reference_data: None
) -> None:
    """Given a code nobody configured, then it cannot be assigned."""
    response = admin_client.post(
        PROJECTS,
        json=project_payload(country_pack_id, currency_id, project_type_code="INVENTED"),
    )

    assert response.status_code == 422
    assert "project_type" in response.json()["detail"]


def test_a_manager_without_the_project_manager_role_is_rejected(
    admin_client: TestClient, engineer: User, project_id: str
) -> None:
    """Given the wrong role, then the assignment is refused rather than improvised."""
    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"project_manager_user_id": str(engineer.id)}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "The project manager must hold the Project Manager role."}


def test_an_inactive_manager_is_rejected(
    admin_client: TestClient, db: Session, project_id: str
) -> None:
    """Given a deactivated account, then it cannot be made project manager."""
    retired = make_user(db, email="gone@example.com", roles=("project_manager",), is_active=False)

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"project_manager_user_id": str(retired.id)}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Project manager must be an active user."}


def test_the_project_code_is_immutable(admin_client: TestClient, project_id: str) -> None:
    """Given an update naming a code, then the field is simply not accepted."""
    response = admin_client.patch(f"{PROJECTS}/{project_id}", json={"code": "RENAMED"})

    assert response.status_code == 200
    assert response.json()["code"] == "GALINI-BLU"


def test_the_basis_may_be_corrected_during_setup(admin_client: TestClient, project_id: str) -> None:
    """Given a project still in setup, then its currency basis can still be fixed."""
    spare = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "US dollar"}
    ).json()

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"reporting_currency_id": spare["id"]}
    )

    assert response.status_code == 200
    assert response.json()["reporting_currency_code"] == "USD"


def test_the_basis_locks_once_the_project_leaves_setup(
    admin_client: TestClient, project_id: str
) -> None:
    """Given an active project, then changing its monetary basis is refused.

    Amounts already recorded against the project are denominated in its base
    currency, and this MVP has no FX or restatement to move them with.
    """
    spare = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "US dollar"}
    ).json()
    assert (
        admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "active"}).status_code == 200
    )

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"base_currency_id": spare["id"]}
    )

    assert response.status_code == 409
    assert "still in setup" in response.json()["detail"]


def test_a_no_op_basis_field_after_setup_is_not_a_conflict(
    admin_client: TestClient, project_id: str, currency_id: str
) -> None:
    """Given the same value resent, then nothing changed and nothing is refused."""
    admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "active"})

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}",
        json={"base_currency_id": currency_id, "name": "Galini Blu Phase Zero"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Galini Blu Phase Zero"


def test_ordinary_fields_stay_editable_after_setup(
    admin_client: TestClient, project_id: str
) -> None:
    """Given an active project, then its descriptive fields are still maintainable."""
    admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "active"})

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"city": "Aqaba", "location": None}
    )

    assert response.status_code == 200
    assert response.json()["city"] == "Aqaba"
    assert response.json()["location"] is None


def test_a_reversed_window_is_rejected_against_the_resulting_state(
    admin_client: TestClient, project_id: str
) -> None:
    """Given only one end is sent, then it is validated against the stored other end."""
    admin_client.patch(f"{PROJECTS}/{project_id}", json={"planned_start": "2027-01-01"})

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"planned_completion": "2026-01-01"}
    )

    assert response.status_code == 422


def test_only_privileged_roles_may_create_a_project(
    advisor: User, country_pack_id: str, currency_id: str
) -> None:
    """Given a Sales Advisor, then project creation is refused."""
    client = client_for(advisor.email)

    response = client.post(PROJECTS, json=project_payload(country_pack_id, currency_id))

    assert response.status_code == 403


def test_project_changes_are_audited_with_before_and_after(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given a create and an update, then both are recorded with their snapshots."""
    admin_client.patch(f"{PROJECTS}/{project_id}", json={"name": "Galini Blu Residences"})

    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action.like("project.%"))
        .order_by(AuditEvent.occurred_at)
    ).all()

    assert [event.action for event in events] == ["project.created", "project.updated"]
    assert events[0].before_data is None
    assert events[0].after_data["code"] == "GALINI-BLU"
    assert events[1].before_data["name"] == "Galini Blu"
    assert events[1].after_data["name"] == "Galini Blu Residences"
    assert events[1].correlation_id is not None
