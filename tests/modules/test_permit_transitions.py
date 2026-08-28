"""Permit status movement: the append-only history and the rules that guard it."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.models import Permit, PermitStatusEvent
from tests.modules.conftest import PROJECTS, parcel_payload, permit_payload


@pytest.fixture
def permits_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/permits"


@pytest.fixture
def permit_id(admin_client: TestClient, permits_url: str) -> str:
    response = admin_client.post(permits_url, json=permit_payload())
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _move(
    client: TestClient, permits_url: str, permit_id: str, to_status: str, day: str, **extra: object
) -> object:
    return client.post(
        f"{permits_url}/{permit_id}/transitions",
        json={"to_status": to_status, "effective_date": day, **extra},
    )


def _walk_to(client: TestClient, permits_url: str, permit_id: str, *steps: tuple[str, str]) -> None:
    for to_status, day in steps:
        response = _move(client, permits_url, permit_id, to_status, day, reason="Progressing")
        assert response.status_code == 201, response.text


def test_a_permit_walks_the_full_lifecycle(
    admin_client: TestClient, permits_url: str, permit_id: str, db: Session
) -> None:
    """Given each ordinary step, then the permit moves and the history accumulates."""
    _walk_to(
        admin_client,
        permits_url,
        permit_id,
        ("preparing", "2026-01-05"),
        ("submitted", "2026-01-10"),
        ("accepted_for_review", "2026-01-20"),
        ("comments_received", "2026-02-01"),
        ("resubmission", "2026-02-15"),
        ("issued", "2026-03-01"),
        ("expired", "2027-03-01"),
        ("renewed", "2027-03-15"),
    )

    permit = db.scalars(select(Permit)).one()
    assert permit.status == "renewed"
    events = db.scalars(select(PermitStatusEvent).order_by(PermitStatusEvent.effective_date)).all()
    assert [event.to_status for event in events] == [
        "preparing",
        "submitted",
        "accepted_for_review",
        "comments_received",
        "resubmission",
        "issued",
        "expired",
        "renewed",
    ]


def test_a_move_the_table_does_not_allow_is_refused(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given a jump nobody sanctioned, then it conflicts rather than happening."""
    response = _move(admin_client, permits_url, permit_id, "issued", "2026-02-01")

    assert response.status_code == 409
    assert response.json() == {"detail": "A permit cannot move from not_started to issued."}


def test_moving_to_the_current_status_is_refused(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given no actual change, then there is no event to record."""
    response = _move(admin_client, permits_url, permit_id, "not_started", "2026-02-01")

    assert response.status_code == 409
    assert response.json() == {"detail": "The permit is already in that status."}


def test_history_cannot_travel_backwards(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given an earlier effective date, then the move is refused.

    A register whose history runs backwards cannot be read as a sequence.
    """
    _walk_to(admin_client, permits_url, permit_id, ("preparing", "2026-02-01"))

    response = _move(admin_client, permits_url, permit_id, "submitted", "2026-01-01")

    assert response.status_code == 422
    assert "cannot be earlier" in response.json()["detail"]


def test_a_historical_backfill_on_the_same_day_is_allowed(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given several steps recorded on one day, then backfill still works."""
    _walk_to(admin_client, permits_url, permit_id, ("preparing", "2026-01-01"))

    response = _move(admin_client, permits_url, permit_id, "submitted", "2026-01-01")

    assert response.status_code == 201


@pytest.mark.parametrize("to_status", ["rejected", "on_hold", "withdrawn"])
def test_stopping_a_permit_requires_a_reason(
    admin_client: TestClient, permits_url: str, permit_id: str, to_status: str
) -> None:
    """Given a move that halts or refuses the application, then 'why' is required."""
    _walk_to(
        admin_client,
        permits_url,
        permit_id,
        ("preparing", "2026-01-05"),
        ("submitted", "2026-01-10"),
    )

    without = _move(admin_client, permits_url, permit_id, to_status, "2026-02-01")
    with_reason = _move(
        admin_client,
        permits_url,
        permit_id,
        to_status,
        "2026-02-01",
        reason="Authority requested further information",
    )

    assert without.status_code == 422
    assert "reason is required" in without.json()["detail"]
    assert with_reason.status_code == 201


def test_restarting_after_a_refusal_requires_a_reason(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given a rejected application, then restarting it must be explained."""
    _walk_to(
        admin_client,
        permits_url,
        permit_id,
        ("preparing", "2026-01-05"),
        ("submitted", "2026-01-10"),
    )
    _move(admin_client, permits_url, permit_id, "rejected", "2026-02-01", reason="Height exceeded")

    without = _move(admin_client, permits_url, permit_id, "preparing", "2026-03-01")

    assert without.status_code == 422


def test_starting_work_needs_no_explanation(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given the first move off not_started, then no reason is demanded.

    Beginning work is not an exception that needs justifying.
    """
    response = _move(admin_client, permits_url, permit_id, "preparing", "2026-01-05")

    assert response.status_code == 201


def test_withdrawn_is_terminal(admin_client: TestClient, permits_url: str, permit_id: str) -> None:
    """Given a withdrawn application, then nothing follows it."""
    _move(admin_client, permits_url, permit_id, "withdrawn", "2026-01-05", reason="Scheme dropped")

    response = _move(
        admin_client, permits_url, permit_id, "preparing", "2026-02-01", reason="Revived"
    )

    assert response.status_code == 409


def test_an_on_hold_permit_can_resume_where_it_paused(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    _walk_to(
        admin_client,
        permits_url,
        permit_id,
        ("preparing", "2026-01-05"),
        ("submitted", "2026-01-10"),
    )
    _move(admin_client, permits_url, permit_id, "on_hold", "2026-02-01", reason="Funding paused")

    response = _move(admin_client, permits_url, permit_id, "accepted_for_review", "2026-04-01")

    assert response.status_code == 201


def test_a_transition_establishes_its_milestone_date(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given a submission, then the actual submission date follows from the move."""
    _walk_to(admin_client, permits_url, permit_id, ("preparing", "2026-01-05"))

    response = _move(admin_client, permits_url, permit_id, "submitted", "2026-01-10")

    assert response.status_code == 201
    assert response.json()["actual_submission_date"] == "2026-01-10"


def test_an_explicit_milestone_date_is_never_silently_overwritten(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given somebody recorded the real date, then the transition leaves it alone.

    Theirs is the corrected one; the transition date is only a default.
    """
    admin_client.patch(f"{permits_url}/{permit_id}", json={"actual_submission_date": "2026-01-07"})
    _walk_to(admin_client, permits_url, permit_id, ("preparing", "2026-01-05"))

    response = _move(admin_client, permits_url, permit_id, "submitted", "2026-01-10")

    assert response.json()["actual_submission_date"] == "2026-01-07"


def test_an_ordinary_update_cannot_change_the_status(
    admin_client: TestClient, permits_url: str, permit_id: str, db: Session
) -> None:
    """Given a PATCH naming a status, then the field is simply not accepted.

    Status is history; it moves only through a transition that records the move.
    """
    response = admin_client.patch(
        f"{permits_url}/{permit_id}", json={"status": "issued", "next_action": "Chase"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "not_started"
    assert db.scalars(select(PermitStatusEvent)).all() == []


def test_a_transition_appends_exactly_one_event(
    admin_client: TestClient, permits_url: str, permit_id: str, db: Session
) -> None:
    _move(admin_client, permits_url, permit_id, "preparing", "2026-01-05")

    events = db.scalars(select(PermitStatusEvent)).all()

    assert len(events) == 1
    assert (events[0].from_status, events[0].to_status) == ("not_started", "preparing")


def test_a_refused_transition_leaves_no_trace(
    admin_client: TestClient, permits_url: str, permit_id: str, db: Session
) -> None:
    """Given an invalid move, then no event, no status change and no audit entry.

    The event, the new status and the audit record commit together or not at
    all; a rejected move must not leave an orphan behind.
    """
    _move(admin_client, permits_url, permit_id, "issued", "2026-02-01")

    assert db.scalars(select(PermitStatusEvent)).all() == []
    assert db.scalars(select(Permit)).one().status == "not_started"
    assert (
        db.scalars(select(AuditEvent).where(AuditEvent.action == "permit.status_changed")).all()
        == []
    )


def test_a_transition_is_audited_alongside_its_event(
    admin_client: TestClient, permits_url: str, permit_id: str, db: Session
) -> None:
    """Given a move, then both records exist: operational history and accountability."""
    _move(
        admin_client,
        permits_url,
        permit_id,
        "withdrawn",
        "2026-01-05",
        reason="Scheme dropped",
    )

    event = db.scalars(select(PermitStatusEvent)).one()
    audit = db.scalars(select(AuditEvent).where(AuditEvent.action == "permit.status_changed")).one()

    assert event.reason == "Scheme dropped"
    assert audit.reason == "Scheme dropped"
    assert audit.before_data["status"] == "not_started"
    assert audit.after_data["status"] == "withdrawn"


def test_status_history_is_readable_and_ordered(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    _walk_to(
        admin_client,
        permits_url,
        permit_id,
        ("preparing", "2026-01-05"),
        ("submitted", "2026-01-10"),
    )

    history = admin_client.get(f"{permits_url}/{permit_id}/status-history").json()

    assert [(row["from_status"], row["to_status"]) for row in history] == [
        ("not_started", "preparing"),
        ("preparing", "submitted"),
    ]


def test_status_history_has_no_write_endpoints(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given the history, then it is append-only: nothing edits or removes it."""
    _walk_to(admin_client, permits_url, permit_id, ("preparing", "2026-01-05"))
    url = f"{permits_url}/{permit_id}/status-history"

    assert admin_client.patch(url, json={}).status_code == 404
    assert admin_client.delete(url).status_code == 404
    assert admin_client.post(url, json={}).status_code == 404


# --------------------------------------------------------------------------- #
# Identity freeze after submission
# --------------------------------------------------------------------------- #


def test_identity_is_editable_before_submission(
    admin_client: TestClient, project_id: str, permits_url: str, permit_id: str
) -> None:
    """Given the application has not gone in, then a correction is ordinary work."""
    parcel = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]

    response = admin_client.patch(
        f"{permits_url}/{permit_id}",
        json={"authority": "Ministry of Public Works", "parcel_id": parcel},
    )

    assert response.status_code == 200
    assert response.json()["authority"] == "Ministry of Public Works"


@pytest.mark.parametrize(
    "field,value",
    [
        ("authority", "Someone Else"),
        ("permit_type_code", "PLANNING"),
    ],
)
def test_identity_freezes_once_submitted(
    admin_client: TestClient, permits_url: str, permit_id: str, field: str, value: str
) -> None:
    """Given the application is with the authority, then it cannot be repointed.

    A statutory submission exists; changing what it is would silently make the
    record describe a different application.
    """
    _walk_to(
        admin_client,
        permits_url,
        permit_id,
        ("preparing", "2026-01-05"),
        ("submitted", "2026-01-10"),
    )

    response = admin_client.patch(f"{permits_url}/{permit_id}", json={field: value})

    assert response.status_code == 409
    assert "fixed once the application" in response.json()["detail"]


def test_the_parcel_link_freezes_once_submitted(
    admin_client: TestClient, project_id: str, permits_url: str, permit_id: str
) -> None:
    parcel = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]
    _walk_to(
        admin_client,
        permits_url,
        permit_id,
        ("preparing", "2026-01-05"),
        ("submitted", "2026-01-10"),
    )

    response = admin_client.patch(f"{permits_url}/{permit_id}", json={"parcel_id": parcel})

    assert response.status_code == 409


def test_operational_fields_stay_editable_after_submission(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given a live application, then the fields it is actually managed by still move."""
    _walk_to(
        admin_client,
        permits_url,
        permit_id,
        ("preparing", "2026-01-05"),
        ("submitted", "2026-01-10"),
    )

    response = admin_client.patch(
        f"{permits_url}/{permit_id}",
        json={
            "forecast_issue_date": "2026-06-01",
            "next_action": "Chase case officer",
            "is_blocking": True,
            "statutory_sla_days": 45,
            "conditions": "Subject to parking survey",
        },
    )

    assert response.status_code == 200
    assert response.json()["is_blocking"] is True
    assert response.json()["next_action"] == "Chase case officer"


def test_the_permit_code_is_immutable_from_creation(
    admin_client: TestClient, permits_url: str, permit_id: str
) -> None:
    """Given an update naming a permit code, then the field is not accepted at all."""
    response = admin_client.patch(f"{permits_url}/{permit_id}", json={"permit_code": "OTHER-1"})

    assert response.status_code == 200
    assert response.json()["permit_code"] == "BLD-001"
