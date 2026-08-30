"""Four independent status dimensions, and the one inventory is allowed to move.

Commercial, legal, collection and delivery answer different questions for
different departments. Inventory owns three commercial states and nothing else:
reserved and contracted are made by real sales, and a button here that produced
one would put an invented sale in the register.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit, UnitStatusEvent
from tests.modules.conftest import inventory_url, make_releasable


def _transitions(project_id: str, unit_id: str) -> str:
    return f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions"


def test_a_hold_records_an_event(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given a hold, then the move, its reason and its date are all recorded."""
    response = admin_client.post(
        _transitions(project_id, unit_id),
        json={
            "to_status": "held",
            "effective_date": "2026-02-01",
            "reason": "Broker hold pending decision",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["commercial_status"] == "held"
    event = db.scalars(select(UnitStatusEvent)).one()
    assert (event.dimension, event.from_status, event.to_status) == (
        "commercial",
        "unreleased",
        "held",
    )
    assert event.reason == "Broker hold pending decision"


def test_a_hold_requires_a_reason(admin_client: TestClient, project_id: str, unit_id: str) -> None:
    response = admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": "held", "effective_date": "2026-02-01"},
    )

    assert response.status_code == 422
    assert "reason is required" in response.json()["detail"]


def test_returning_to_unreleased_requires_a_reason(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": "held", "effective_date": "2026-02-01", "reason": "Hold"},
    )

    response = admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": "unreleased", "effective_date": "2026-02-02"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("status", ["reserved", "contracted", "cancelled", "returned"])
def test_inventory_cannot_fake_a_sales_status(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session, status: str
) -> None:
    """Given a sales status, then inventory refuses it and writes nothing.

    These states are created by a real transaction in PR-MVP-05. A register that
    can be told a unit is contracted, with no contract behind it, is not a
    record of anything.
    """
    response = admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": status, "effective_date": "2026-02-01", "reason": "Pretend"},
    )

    assert response.status_code == 422
    assert db.scalars(select(UnitStatusEvent)).all() == []
    assert db.scalars(select(Unit)).one().commercial_status == "unreleased"


def test_an_unknown_status_is_refused(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    response = admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": "sold", "effective_date": "2026-02-01"},
    )

    assert response.status_code == 422


def test_a_transition_to_the_same_status_is_refused(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    response = admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": "unreleased", "effective_date": "2026-02-01", "reason": "Again"},
    )

    assert response.status_code == 422
    assert "already in this status" in response.json()["detail"]


def test_a_refused_transition_leaves_no_trace(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given the release checks fail, then no event, no status and no audit entry."""
    response = admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": "available", "effective_date": "2026-02-01"},
    )

    assert response.status_code == 409
    assert db.scalars(select(UnitStatusEvent)).all() == []
    assert db.scalars(select(Unit)).one().commercial_status == "unreleased"
    assert (
        db.scalars(
            select(AuditEvent).where(AuditEvent.action == "unit.commercial_status_changed")
        ).all()
        == []
    )


def test_status_history_is_append_only(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": "held", "effective_date": "2026-02-01", "reason": "Hold"},
    )
    history_url = f"{inventory_url(project_id)}/units/{unit_id}/status-history"

    assert admin_client.get(history_url).status_code == 200
    assert admin_client.patch(history_url, json={}).status_code == 404
    assert admin_client.delete(history_url).status_code == 404


def test_the_history_stays_linear(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Given a walk through three states, then each event follows the last."""
    make_releasable(admin_client, project_id, unit_id, area_types, db)
    for to_status, day, reason in (
        ("held", "2026-02-01", "Hold"),
        ("available", "2026-02-02", None),
        ("unreleased", "2026-02-03", "Withdrawn from sale"),
    ):
        body: dict[str, object] = {"to_status": to_status, "effective_date": day}
        if reason:
            body["reason"] = reason
        response = admin_client.post(_transitions(project_id, unit_id), json=body)
        assert response.status_code == 201, response.text

    events = db.scalars(select(UnitStatusEvent).order_by(UnitStatusEvent.effective_date)).all()
    assert [(event.from_status, event.to_status) for event in events] == [
        ("unreleased", "held"),
        ("held", "available"),
        ("available", "unreleased"),
    ]


def test_the_other_dimensions_are_untouched_by_a_commercial_move(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given a hold, then legal, collection and delivery do not move with it."""
    admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": "held", "effective_date": "2026-02-01", "reason": "Hold"},
    )

    unit = db.scalars(select(Unit)).one()
    assert unit.legal_status == "no_spa"
    assert unit.collection_status == "not_started"
    assert unit.delivery_status == "not_started"


def test_a_transition_refuses_an_unknown_field(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    response = admin_client.post(
        _transitions(project_id, unit_id),
        json={"to_status": "held", "effective_date": "2026-02-01", "reasn": "typo"},
    )

    assert response.status_code == 422


def test_only_release_writers_may_transition(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    from tests.factories import client_for, make_user
    from tests.modules.conftest import PROJECTS

    engineer = make_user(db, email="eng3@example.com", roles=("design_engineering",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{engineer.id}")

    response = client_for(engineer.email).post(
        _transitions(project_id, unit_id),
        json={"to_status": "held", "effective_date": "2026-02-01", "reason": "Hold"},
    )

    assert response.status_code == 403


def test_sales_operations_may_transition(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    from tests.factories import client_for, make_user
    from tests.modules.conftest import PROJECTS

    ops = make_user(db, email="ops@example.com", roles=("sales_operations",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{ops.id}")

    response = client_for(ops.email).post(
        _transitions(project_id, unit_id),
        json={"to_status": "held", "effective_date": "2026-02-01", "reason": "Hold"},
    )

    assert response.status_code == 201, response.text
