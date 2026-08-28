"""The permit register: identity, links, filters and the derived governance figures."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.projects.models import Permit
from tests.factories import client_for
from tests.modules.conftest import (
    PROJECTS,
    grant_access,
    parcel_payload,
    permit_payload,
    project_payload,
)


@pytest.fixture
def permits_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/permits"


def test_a_permit_starts_not_started(admin_client: TestClient, permits_url: str) -> None:
    """Given a new permit, then it opens in the state before any work."""
    response = admin_client.post(permits_url, json=permit_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "not_started"
    assert body["status_effective_date"] == "2026-01-01"


def test_a_permit_code_is_unique_within_a_project(
    admin_client: TestClient, permits_url: str
) -> None:
    """Given the code is taken, then a second permit is refused."""
    admin_client.post(permits_url, json=permit_payload())

    response = admin_client.post(permits_url, json=permit_payload())

    assert response.status_code == 409
    assert "permit with that code" in response.json()["detail"]


def test_the_same_permit_code_is_free_in_another_project(
    admin_client: TestClient, permits_url: str, country_pack_id: str, currency_id: str
) -> None:
    admin_client.post(permits_url, json=permit_payload())
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]

    response = admin_client.post(f"{PROJECTS}/{other}/permits", json=permit_payload())

    assert response.status_code == 201


def test_an_unconfigured_permit_type_is_rejected(
    admin_client: TestClient, permits_url: str
) -> None:
    """Given a permit type nobody configured, then it cannot be assigned.

    Local permit vocabularies belong to country configuration; the code stays
    country-neutral.
    """
    response = admin_client.post(
        permits_url, json=permit_payload(permit_type_code="NOT_CONFIGURED")
    )

    assert response.status_code == 422
    assert "permit_type" in response.json()["detail"]


def test_a_permit_may_only_reference_a_parcel_in_its_own_project(
    admin_client: TestClient,
    permits_url: str,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    foreign_parcel = admin_client.post(f"{PROJECTS}/{other}/parcels", json=parcel_payload()).json()[
        "id"
    ]

    response = admin_client.post(permits_url, json=permit_payload(parcel_id=foreign_parcel))

    assert response.status_code == 404
    assert response.json() == {"detail": "Land parcel not found."}


def test_an_inactive_owner_cannot_be_assigned(
    admin_client: TestClient, permits_url: str, db: Session
) -> None:
    from tests.factories import make_user

    retired = make_user(db, email="left@example.com", roles=("legal",), is_active=False)

    response = admin_client.post(permits_url, json=permit_payload(owner_user_id=str(retired.id)))

    assert response.status_code == 422
    assert response.json() == {"detail": "Permit owner must be an active user."}


def test_a_permit_cannot_be_its_own_prerequisite(
    admin_client: TestClient, permits_url: str
) -> None:
    created = admin_client.post(permits_url, json=permit_payload()).json()

    response = admin_client.patch(
        f"{permits_url}/{created['id']}", json={"prerequisite_permit_id": created["id"]}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "A permit cannot be its own prerequisite."}


def test_a_circular_prerequisite_is_rejected(admin_client: TestClient, permits_url: str) -> None:
    """Given A depends on B, then B may not be made to depend on A."""
    first = admin_client.post(permits_url, json=permit_payload(permit_code="PLN-001")).json()
    second = admin_client.post(
        permits_url, json=permit_payload(prerequisite_permit_id=first["id"])
    ).json()

    response = admin_client.patch(
        f"{permits_url}/{first['id']}", json={"prerequisite_permit_id": second["id"]}
    )

    assert response.status_code == 422
    assert "circular dependency" in response.json()["detail"]


def test_a_prerequisite_from_another_project_is_rejected(
    admin_client: TestClient, permits_url: str, country_pack_id: str, currency_id: str
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    foreign = admin_client.post(f"{PROJECTS}/{other}/permits", json=permit_payload()).json()["id"]

    response = admin_client.post(
        permits_url, json=permit_payload(permit_code="PLN-001", prerequisite_permit_id=foreign)
    )

    assert response.status_code == 422
    assert "must belong to this project" in response.json()["detail"]


def test_a_prerequisite_is_satisfied_only_once_the_permit_is_in_force(
    admin_client: TestClient, permits_url: str
) -> None:
    """Given a prerequisite still in progress, then the dependant is not satisfied.

    ``approved_with_conditions`` deliberately does not count: the conditions are
    exactly what is not yet met.
    """
    first = admin_client.post(permits_url, json=permit_payload(permit_code="PLN-001")).json()
    second = admin_client.post(
        permits_url, json=permit_payload(prerequisite_permit_id=first["id"])
    ).json()

    assert (
        admin_client.get(f"{permits_url}/{second['id']}").json()["prerequisite_satisfied"] is False
    )

    for to_status in ("preparing", "submitted", "accepted_for_review"):
        admin_client.post(
            f"{permits_url}/{first['id']}/transitions",
            json={"to_status": to_status, "effective_date": "2026-02-01"},
        )
    admin_client.post(
        f"{permits_url}/{first['id']}/transitions",
        json={"to_status": "approved_with_conditions", "effective_date": "2026-03-01"},
    )
    assert (
        admin_client.get(f"{permits_url}/{second['id']}").json()["prerequisite_satisfied"] is False
    )

    admin_client.post(
        f"{permits_url}/{first['id']}/transitions",
        json={"to_status": "issued", "effective_date": "2026-04-01"},
    )
    assert (
        admin_client.get(f"{permits_url}/{second['id']}").json()["prerequisite_satisfied"] is True
    )


def test_a_permit_with_no_prerequisite_is_satisfied(
    admin_client: TestClient, permits_url: str
) -> None:
    created = admin_client.post(permits_url, json=permit_payload()).json()

    assert created["prerequisite_satisfied"] is True


def test_the_permit_fee_keeps_exact_decimal_precision(
    admin_client: TestClient, permits_url: str, db: Session
) -> None:
    response = admin_client.post(permits_url, json=permit_payload(fee_amount="7654.32"))

    assert response.status_code == 201
    assert response.json()["fee_amount"] == "7654.32"
    stored = db.scalars(select(Permit)).one()
    assert stored.fee_amount == Decimal("7654.32")
    assert isinstance(stored.fee_amount, Decimal)


def test_a_negative_fee_is_rejected(admin_client: TestClient, permits_url: str) -> None:
    response = admin_client.post(permits_url, json=permit_payload(fee_amount="-1.00"))

    assert response.status_code == 422


def test_days_in_stage_and_sla_are_derived_from_today(
    admin_client: TestClient, permits_url: str
) -> None:
    """Given a permit sitting in a stage, then the aging figures follow the date.

    Derived at read time rather than stored: a stored age is true for one day.
    """
    effective = date.today() - timedelta(days=10)
    created = admin_client.post(
        permits_url,
        json=permit_payload(status_effective_date=effective.isoformat(), statutory_sla_days=30),
    ).json()

    assert created["days_in_stage"] == 10
    assert created["sla_days_remaining"] == 20
    assert created["sla_overdue"] is False


def test_an_sla_past_its_deadline_reads_as_overdue(
    admin_client: TestClient, permits_url: str
) -> None:
    effective = date.today() - timedelta(days=40)
    created = admin_client.post(
        permits_url,
        json=permit_payload(status_effective_date=effective.isoformat(), statutory_sla_days=30),
    ).json()

    assert created["sla_days_remaining"] == -10
    assert created["sla_overdue"] is True


def test_a_permit_without_an_sla_has_no_deadline(
    admin_client: TestClient, permits_url: str
) -> None:
    created = admin_client.post(permits_url, json=permit_payload()).json()

    assert created["sla_days_remaining"] is None
    assert created["sla_overdue"] is False


def test_schedule_variance_prefers_the_actual_over_the_forecast(
    admin_client: TestClient, permits_url: str
) -> None:
    """Given a submission has actually happened, then the estimate stops mattering."""
    created = admin_client.post(
        permits_url,
        json=permit_payload(
            planned_submission_date="2026-01-10",
            forecast_submission_date="2026-01-20",
            planned_issue_date="2026-06-01",
            forecast_issue_date="2026-06-20",
        ),
    ).json()

    assert created["submission_variance_days"] == 10
    assert created["issue_variance_days"] == 19

    updated = admin_client.patch(
        f"{permits_url}/{created['id']}", json={"actual_submission_date": "2026-01-12"}
    ).json()

    assert updated["submission_variance_days"] == 2


def test_variance_is_absent_without_a_plan_to_compare_against(
    admin_client: TestClient, permits_url: str
) -> None:
    created = admin_client.post(
        permits_url, json=permit_payload(forecast_submission_date="2026-01-20")
    ).json()

    assert created["submission_variance_days"] is None


def test_the_register_summarises_what_needs_attention(
    admin_client: TestClient, permits_url: str
) -> None:
    """Given a mixed register, then the counts a manager acts on come back with it."""
    admin_client.post(permits_url, json=permit_payload(is_blocking=True, is_critical_path=True))
    admin_client.post(permits_url, json=permit_payload(permit_code="PLN-001"))
    effective = (date.today() - timedelta(days=40)).isoformat()
    admin_client.post(
        permits_url,
        json=permit_payload(
            permit_code="NOC-001",
            is_blocking=True,
            statutory_sla_days=30,
            status_effective_date=effective,
        ),
    )

    register = admin_client.get(permits_url).json()

    assert register["total"] == 3
    assert register["blocking_count"] == 2
    assert register["critical_path_count"] == 1
    assert register["sla_overdue_count"] == 1


@pytest.mark.parametrize(
    "query,expected",
    [
        ("is_blocking=true", ["BLD-001"]),
        ("is_critical_path=true", ["BLD-001"]),
        ("status=not_started", ["BLD-001", "PLN-001"]),
        ("permit_type_code=PLANNING", ["PLN-001"]),
    ],
)
def test_the_register_can_be_filtered(
    admin_client: TestClient, permits_url: str, query: str, expected: list[str]
) -> None:
    admin_client.post(permits_url, json=permit_payload(is_blocking=True, is_critical_path=True))
    admin_client.post(
        permits_url, json=permit_payload(permit_code="PLN-001", permit_type_code="PLANNING")
    )

    register = admin_client.get(f"{permits_url}?{query}").json()

    assert sorted(permit["permit_code"] for permit in register["permits"]) == expected


def test_a_permit_from_another_project_cannot_be_read_through_this_one(
    admin_client: TestClient, permits_url: str, country_pack_id: str, currency_id: str
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    foreign = admin_client.post(f"{PROJECTS}/{other}/permits", json=permit_payload()).json()["id"]

    response = admin_client.get(f"{permits_url}/{foreign}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Permit not found."}


def test_an_unknown_permit_is_not_found(admin_client: TestClient, permits_url: str) -> None:
    assert admin_client.get(f"{permits_url}/{uuid.uuid4()}").status_code == 404


def test_permits_have_no_delete_endpoint(admin_client: TestClient, permits_url: str) -> None:
    """Given a permit, then it is withdrawn through a transition, never removed."""
    created = admin_client.post(permits_url, json=permit_payload()).json()

    assert admin_client.delete(f"{permits_url}/{created['id']}").status_code == 404


def test_design_engineering_maintains_permits(
    admin_client: TestClient, engineer: User, project_id: str, permits_url: str
) -> None:
    grant_access(admin_client, project_id, engineer)
    client = client_for(engineer.email)

    assert client.post(permits_url, json=permit_payload()).status_code == 201


def test_a_member_without_a_writing_role_cannot_register_a_permit(
    admin_client: TestClient, advisor: User, project_id: str, permits_url: str
) -> None:
    grant_access(admin_client, project_id, advisor)
    client = client_for(advisor.email)

    assert client.get(permits_url).status_code == 200
    assert client.post(permits_url, json=permit_payload()).status_code == 403


def test_permit_changes_are_audited(
    admin_client: TestClient, permits_url: str, db: Session
) -> None:
    created = admin_client.post(
        permits_url, json=permit_payload(next_action="Draft drawings")
    ).json()
    admin_client.patch(f"{permits_url}/{created['id']}", json={"next_action": "Submit drawings"})

    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action.like("permit.%"))
        .order_by(AuditEvent.occurred_at)
    ).all()

    assert [event.action for event in events] == ["permit.created", "permit.updated"]
    assert events[1].before_data["next_action"] == "Draft drawings"
    assert events[1].after_data["next_action"] == "Submit drawings"
