"""Real PostgreSQL action workflow, authorization and source independence."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access, permit_payload

BASE = "/api/v1/portfolio/actions"


def test_versioned_lifecycle_and_immutable_history(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    owner = make_user(db, email="action-owner@example.com", roles=("project_manager",))
    other = make_user(db, email="action-other@example.com", roles=("finance",))
    grant_access(admin_client, project_id, owner)
    grant_access(admin_client, project_id, other)
    today = datetime.now(UTC).date()
    reply = admin_client.post(
        BASE,
        json={
            "project_id": project_id,
            "title": "Resolve funding review",
            "owner_user_id": str(owner.id),
            "due_date": str(today - timedelta(days=1)),
        },
    )
    assert reply.status_code == 201, reply.text
    action = reply.json()
    assert action["version"] == 1 and action["due_state"] == "overdue"
    url = f"{BASE}/{action['id']}"
    reply = admin_client.patch(url, json={"expected_version": 1, "owner_user_id": str(other.id)})
    assert reply.status_code == 200, reply.text
    assert reply.json()["version"] == 2
    assert (
        admin_client.patch(url, json={"expected_version": 1, "title": "Lost update"}).status_code
        == 409
    )
    assert (
        admin_client.patch(url, json={"expected_version": 2, "due_date": str(today)}).status_code
        == 422
    )
    reply = admin_client.patch(
        url,
        json={"expected_version": 2, "due_date": str(today), "reason": "Review scheduled today"},
    )
    assert reply.status_code == 200, reply.text
    version = 3
    for status in ("in_progress", "completed", "open", "completed"):
        reply = admin_client.post(
            f"{url}/transitions",
            json={
                "expected_version": version,
                "status": status,
                "reason": "Review further evidence" if status == "open" else None,
            },
        )
        assert reply.status_code == 200, reply.text
        version += 1
        assert reply.json()["version"] == version
        assert (reply.json()["completed_at"] is not None) == (status == "completed")
    history = admin_client.get(f"{url}/history").json()
    assert history["total"] == 7
    assert [row["version"] for row in history["items"]] == list(range(1, 8))
    assert history["items"][0]["changes"]["owner_user_id"]["new"] == str(owner.id)
    assert history["items"][2]["reason"] == "Review scheduled today"
    assert admin_client.delete(url).status_code in {404, 405}
    assert admin_client.patch(f"{url}/history", json={}).status_code in {404, 405}
    assert admin_client.get(BASE, params={"due_state": "overdue"}).json()["total"] == 0


def test_action_scope_owner_and_read_only_roles(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    today = str(datetime.now(UTC).date())
    hidden = make_user(db, email="hidden-owner@example.com", roles=("finance",))
    payload = {
        "project_id": project_id,
        "title": "Scoped action",
        "due_date": today,
        "owner_user_id": str(hidden.id),
    }
    assert admin_client.post(BASE, json=payload).status_code == 422
    grant_access(admin_client, project_id, hidden)
    reply = admin_client.post(BASE, json=payload)
    assert reply.status_code == 201, reply.text
    url = f"{BASE}/{reply.json()['id']}"
    for role in ("project_manager", "finance", "approver_cfo", "executive_viewer", "auditor"):
        user = make_user(db, email=f"action-{role}@example.com", roles=(role,))
        with client_for(user.email) as client:
            assert client.get(BASE).json()["total"] == 0
            assert client.get(url).status_code == 404
            grant_access(admin_client, project_id, user)
            assert client.get(BASE).json()["total"] == 1
            if role != "project_manager":
                assert client.post(BASE, json=payload).status_code == 403
                assert (
                    client.get(f"{BASE}/assignees", params={"project_id": project_id}).status_code
                    == 403
                )
            assert (
                admin_client.patch(
                    f"/api/v1/projects/{project_id}/access/{user.id}/phase-scope",
                    json={"phase_scope": "selected"},
                ).status_code
                == 200
            )
            assert client.get(BASE).json()["total"] == 0
            assert client.get(url).status_code == 404
            assert client.get(f"{url}/history").status_code == 404
            assert client.get(f"{url}/source").status_code == 404


def test_risk_action_does_not_resolve_permit(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    owner = make_user(db, email="risk-action-owner@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, owner)
    reply = admin_client.post(
        f"/api/v1/projects/{project_id}/permits", json=permit_payload(is_blocking=True)
    )
    assert reply.status_code == 201, reply.text
    before = admin_client.get("/api/v1/portfolio/risks").json()
    risk = next(row for row in before["items"] if row["risk_code"] == "UNRESOLVED_BLOCKING_PERMIT")
    payload = {
        "project_id": project_id,
        "title": "Progress blocking permit",
        "owner_user_id": str(owner.id),
        "due_date": str(datetime.now(UTC).date()),
        "source_type": "portfolio_risk",
        "source_code": risk["risk_code"],
        "source_key": risk["risk_id"],
        "source_observation_date": risk["observation_date"],
    }
    bad = admin_client.post(BASE, json={**payload, "source_key": "forged"})
    assert bad.status_code == 422
    reply = admin_client.post(BASE, json=payload)
    assert reply.status_code == 201, reply.text
    url = f"{BASE}/{reply.json()['id']}"
    assert (
        admin_client.post(
            f"{url}/transitions", json={"expected_version": 1, "status": "completed"}
        ).status_code
        == 200
    )
    assert admin_client.get("/api/v1/portfolio/risks").json() == before


def test_outlook_horizons_and_action_due_independence(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    owner = make_user(db, email="outlook-action-owner@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, owner)
    today = datetime.now(UTC).date()
    for days in (-1, 0, 30, 31, 60, 90, 91):
        reply = admin_client.post(
            BASE,
            json={
                "project_id": project_id,
                "title": f"Due {days}",
                "owner_user_id": str(owner.id),
                "due_date": str(today + timedelta(days=days)),
            },
        )
        assert reply.status_code == 201, reply.text
    for horizon, count in ((30, 3), (60, 5), (90, 6)):
        reply = admin_client.get(
            "/api/v1/portfolio/outlook",
            params={"horizon_days": horizon, "item_type": "management_action_due"},
        )
        assert reply.status_code == 200, reply.text
        body = reply.json()
        assert body["total"] == count
        assert body["horizon_end"] == str(today + timedelta(days=horizon))
        assert body["authorized_project_count"] == 1
    assert admin_client.get("/api/v1/portfolio/outlook?horizon_days=45").status_code == 422
