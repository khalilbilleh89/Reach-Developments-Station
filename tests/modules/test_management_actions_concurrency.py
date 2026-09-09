"""Real competing requests cannot lose an action update or rewrite history."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access
from tests.modules.test_commissions_review import snapshot


def test_competing_updates_and_source_tables_unchanged(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    owner = make_user(db, email="race-action-owner@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, owner)
    with client_for(owner.email) as first, client_for(owner.email) as second:
        before = snapshot(db, ("management_actions", "management_action_history"))
        reply = admin_client.post(
            "/api/v1/portfolio/actions",
            json={
                "project_id": project_id,
                "title": "Before race",
                "owner_user_id": str(owner.id),
                "due_date": str(datetime.now(UTC).date()),
            },
        )
        assert reply.status_code == 201, reply.text
        url = f"/api/v1/portfolio/actions/{reply.json()['id']}"
        barrier = Barrier(2)

        def write(client: TestClient, title: str) -> int:
            barrier.wait(timeout=10)
            return client.patch(url, json={"expected_version": 1, "title": title}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            left = pool.submit(write, first, "First competing change")
            right = pool.submit(write, second, "Second competing change")
            assert sorted((left.result(timeout=30), right.result(timeout=30))) == [200, 409]
        assert first.get(url).json()["version"] == 2
        assert first.get(f"{url}/history").json()["total"] == 2
        version = 2
        for status in ("in_progress", "cancelled", "open", "completed", "open", "completed"):
            reply = first.post(
                f"{url}/transitions",
                json={
                    "expected_version": version,
                    "status": status,
                    "reason": "Operational evidence",
                },
            )
            assert reply.status_code == 200, reply.text
            version += 1
        assert snapshot(db, ("management_actions", "management_action_history")) == before
