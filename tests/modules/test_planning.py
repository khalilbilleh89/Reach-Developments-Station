"""Planning controls: the current planning envelope for one parcel."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.projects.models import PlanningControl
from tests.factories import client_for
from tests.modules.conftest import PROJECTS, grant_access, parcel_payload, project_payload


def _controls(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "permitted_uses": "Residential apartments, ground-floor retail",
        "site_coverage_rate_fraction": "0.450000",
        "far_ratio": "4.5000",
        "maximum_gfa": "20250.0000",
        "maximum_floors": 8,
        "maximum_height": "28.0000",
        "front_setback": "5.0000",
        "side_setback": "3.0000",
        "rear_setback": "3.0000",
        "parking_requirement": "1 space per apartment plus 1 per 50 sqm retail",
        "variance_required": False,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def parcel_id(admin_client: TestClient, project_id: str) -> str:
    response = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload())
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _url(project_id: str, parcel_id: str) -> str:
    return f"{PROJECTS}/{project_id}/parcels/{parcel_id}/planning-controls"


def test_planning_controls_are_recorded_and_read_back_exactly(
    admin_client: TestClient, project_id: str, parcel_id: str, db: Session
) -> None:
    """Given a planning envelope, then every limit round-trips as an exact decimal."""
    response = admin_client.put(_url(project_id, parcel_id), json=_controls())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["site_coverage_rate_fraction"] == "0.450000"
    assert body["far_ratio"] == "4.5000"
    assert body["maximum_floors"] == 8
    stored = db.scalars(select(PlanningControl)).one()
    assert stored.maximum_gfa == Decimal("20250.0000")
    assert isinstance(stored.maximum_gfa, Decimal)


def test_unrecorded_planning_controls_report_not_found(
    admin_client: TestClient, project_id: str, parcel_id: str
) -> None:
    """Given nothing recorded yet, then reading is a 404, not an empty envelope."""
    response = admin_client.get(_url(project_id, parcel_id))

    assert response.status_code == 404


def test_a_second_write_replaces_rather_than_duplicates(
    admin_client: TestClient, project_id: str, parcel_id: str, db: Session
) -> None:
    """Given a revised envelope, then the parcel still has exactly one."""
    admin_client.put(_url(project_id, parcel_id), json=_controls())

    response = admin_client.put(
        _url(project_id, parcel_id), json=_controls(maximum_floors=10, far_ratio="5.0000")
    )

    assert response.status_code == 200
    rows = db.scalars(select(PlanningControl)).all()
    assert len(rows) == 1
    assert rows[0].maximum_floors == 10


def test_a_replacement_clears_a_control_the_authority_dropped(
    admin_client: TestClient, project_id: str, parcel_id: str
) -> None:
    """Given a control is omitted from the new envelope, then it is cleared.

    A full replacement, not a patch: a half-updated envelope would describe a
    planning position no authority granted.
    """
    admin_client.put(_url(project_id, parcel_id), json=_controls())

    response = admin_client.put(
        _url(project_id, parcel_id), json={"far_ratio": "3.0000", "variance_required": False}
    )

    assert response.status_code == 200
    assert response.json()["maximum_floors"] is None
    assert response.json()["far_ratio"] == "3.0000"


@pytest.mark.parametrize(
    "field,value",
    [
        ("site_coverage_rate_fraction", "1.500000"),
        ("site_coverage_rate_fraction", "-0.100000"),
        ("far_ratio", "-1.0000"),
        ("maximum_gfa", "-1.0000"),
        ("maximum_floors", 0),
        ("maximum_height", "-0.5000"),
        ("front_setback", "-1.0000"),
        ("minimum_plot_area", "-1.0000"),
        ("minimum_frontage", "-1.0000"),
        ("density", "-1.0000"),
    ],
)
def test_planning_numbers_outside_their_bounds_are_rejected(
    admin_client: TestClient, project_id: str, parcel_id: str, field: str, value: object
) -> None:
    """Given an impossible planning limit, then the write is refused."""
    response = admin_client.put(_url(project_id, parcel_id), json=_controls(**{field: value}))

    assert response.status_code == 422


def test_a_jurisdiction_may_leave_controls_unset(
    admin_client: TestClient, project_id: str, parcel_id: str
) -> None:
    """Given an authority that does not use a control, then it stays null.

    Not every planning regime uses every lever; forcing a number would invent
    one.
    """
    response = admin_client.put(
        _url(project_id, parcel_id),
        json={"permitted_uses": "Mixed use", "variance_required": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["far_ratio"] is None
    assert body["maximum_floors"] is None
    assert body["variance_required"] is True


def test_design_engineering_maintains_planning_controls(
    admin_client: TestClient, engineer: User, project_id: str, parcel_id: str
) -> None:
    """Given an engineer, then planning is theirs to maintain even though land is not."""
    grant_access(admin_client, project_id, engineer)
    client = client_for(engineer.email)

    response = client.put(_url(project_id, parcel_id), json=_controls())

    assert response.status_code == 200


def test_a_member_without_a_writing_role_cannot_change_planning(
    admin_client: TestClient, advisor: User, project_id: str, parcel_id: str
) -> None:
    """Given a Sales Advisor with access, then writing planning is forbidden."""
    grant_access(admin_client, project_id, advisor)
    client = client_for(advisor.email)

    assert client.get(_url(project_id, parcel_id)).status_code == 404  # none recorded yet
    assert client.put(_url(project_id, parcel_id), json=_controls()).status_code == 403


def test_planning_is_invisible_without_project_access(
    advisor: User, project_id: str, parcel_id: str
) -> None:
    """Given no access, then even the planning path reports the project missing."""
    client = client_for(advisor.email)

    response = client.get(_url(project_id, parcel_id))

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found."}


def test_a_parcel_from_another_project_cannot_carry_planning_here(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    """Given a foreign parcel identifier, then the project scoping refuses it."""
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    foreign = admin_client.post(f"{PROJECTS}/{other}/parcels", json=parcel_payload()).json()["id"]

    response = admin_client.put(_url(project_id, foreign), json=_controls())

    assert response.status_code == 404
    assert response.json() == {"detail": "Land parcel not found."}


def test_an_unknown_parcel_has_no_planning(admin_client: TestClient, project_id: str) -> None:
    response = admin_client.get(_url(project_id, str(uuid.uuid4())))

    assert response.status_code == 404


def test_planning_changes_are_audited_with_before_and_after(
    admin_client: TestClient, project_id: str, parcel_id: str, db: Session
) -> None:
    """Given a revision, then the previous envelope is recoverable from the trail."""
    admin_client.put(_url(project_id, parcel_id), json=_controls())
    admin_client.put(_url(project_id, parcel_id), json=_controls(maximum_floors=12))

    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action.like("planning_control.%"))
        .order_by(AuditEvent.occurred_at)
    ).all()

    assert [event.action for event in events] == [
        "planning_control.created",
        "planning_control.updated",
    ]
    assert events[0].before_data is None
    assert events[1].before_data["maximum_floors"] == 8
    assert events[1].after_data["maximum_floors"] == 12
