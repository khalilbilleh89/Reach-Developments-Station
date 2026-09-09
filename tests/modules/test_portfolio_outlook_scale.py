"""Populated set-based outlook reads, action indexes and hidden-source isolation."""

import uuid
from datetime import UTC, datetime, timedelta
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import event, insert, select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.management_actions import repository
from app.modules.management_actions.models import ManagementAction, ManagementActionHistory
from app.modules.portfolio import outlook
from app.modules.projects.models import Project
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access, permit_payload
from tests.modules.test_portfolio_scale import copy_project


def test_outlook_and_actions_scale_with_scoped_global_pages(
    project_id: str,
    confirmed_receipt: str,
    active_construction_forecast: str,
    admin_client: TestClient,
    db: Session,
) -> None:
    today = datetime.now(UTC).date()
    owner = db.scalar(select(User).where(User.email == "admin@example.com"))
    permit = admin_client.post(
        f"/api/v1/projects/{project_id}/permits",
        json=permit_payload(status_effective_date=str(today), statutory_sla_days=20),
    )
    assert permit.status_code == 201
    pids = [uuid.UUID(project_id)]
    for index in range(1, 50):
        pids.append(copy_project(db, pids[0], f"OUT-{index:02}"))
    action_rows, history_rows = [], []
    for pid in pids:
        for index in range(200):
            aid = uuid.uuid4()
            action_rows.append(
                {
                    "id": aid,
                    "project_id": pid,
                    "title": f"Scale action {index}",
                    "owner_user_id": owner.id,
                    "created_by_user_id": owner.id,
                    "status": "open" if index % 4 else "in_progress",
                    "source_type": "manual",
                    "version": 1,
                    "due_date": today + timedelta(days=index - 100),
                }
            )
            history_rows.append(
                {
                    "id": uuid.uuid4(),
                    "action_id": aid,
                    "version": 1,
                    "actor_user_id": owner.id,
                    "event_type": "created",
                    "changes": {"title": {"old": None, "new": f"Scale action {index}"}},
                }
            )
    db.execute(insert(ManagementAction), action_rows)
    db.execute(insert(ManagementActionHistory), history_rows)
    db.commit()
    captured = []

    def capture(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        captured.append((statement, parameters))

    counts = []
    for size in (1, 20, 50):
        captured.clear()
        scope = select(Project.id).where(Project.id.in_(pids[:size]))
        event.listen(db.bind, "before_cursor_execute", capture)
        started = perf_counter()
        try:
            result = outlook.page(db, scope, today, horizon_days=90, limit=20, offset=20)
        finally:
            event.remove(db.bind, "before_cursor_execute", capture)
        elapsed = perf_counter() - started
        counts.append(len(captured))
        assert len(result.items) == 20
        assert all(row.project_id in pids[:size] for row in result.items)
        assert all(sql.lstrip().upper().startswith("SELECT") for sql, _ in captured)
        print(
            f"OUTLOOK projects={size}, queries={len(captured)}, "
            f"seconds={elapsed:.3f}, total={result.total}"
        )
    assert len(set(counts)) == 1
    scope = select(Project.id).where(Project.id.in_(pids))
    for label, filters in (
        ("first", {}),
        ("owner", {"owner_user_id": owner.id}),
        ("overdue", {"due": "overdue"}),
        ("project", {}),
    ):
        current_scope = (
            select(Project.id).where(Project.id == pids[0]) if label == "project" else scope
        )
        ids = repository.filtered(current_scope, today, **filters)
        captured.clear()
        event.listen(db.bind, "before_cursor_execute", capture)
        started = perf_counter()
        try:
            result = repository.page(db, ids, today, limit=20, offset=0)
        finally:
            event.remove(db.bind, "before_cursor_execute", capture)
        assert len(captured) == 2 and len(result.items) == 20
        assert result.items[0].due_date == today - timedelta(days=100)
        print(
            f"ACTIONS filter={label}, queries={len(captured)}, "
            f"seconds={perf_counter() - started:.3f}, total={result.total}"
        )
        for sql, parameters in captured:
            plan = (
                db.connection()
                .exec_driver_sql("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, parameters)
                .scalar_one()
            )
            print(f"ACTION EXPLAIN {label}: {plan}")


def test_hidden_actions_sources_and_phase_scope_do_not_affect_outlook(
    project_id: str,
    confirmed_receipt: str,
    active_construction_forecast: str,
    admin_client: TestClient,
    db: Session,
) -> None:
    # Clone before granting A-only membership; fixture cloning copies membership rows.
    hidden = copy_project(db, uuid.UUID(project_id), "HIDDEN-B")
    phase = copy_project(db, uuid.UUID(project_id), "PHASE-C")
    reader = make_user(db, email="outlook-a-only@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, reader)
    grant_access(admin_client, str(phase), reader)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{phase}/access/{reader.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    owner = db.scalar(select(User).where(User.email == "admin@example.com"))
    today = datetime.now(UTC).date()
    with client_for(reader.email) as client:
        before = client.get("/api/v1/portfolio/outlook").json()
        for pid in (hidden, phase):
            for index in range(20):
                reply = admin_client.post(
                    "/api/v1/portfolio/actions",
                    json={
                        "project_id": str(pid),
                        "title": f"Hidden overdue {index}",
                        "owner_user_id": str(owner.id),
                        "due_date": str(today - timedelta(days=10)),
                    },
                )
                assert reply.status_code == 201, reply.text
                aid = reply.json()["id"]
        assert client.get("/api/v1/portfolio/outlook").json() == before
        assert before["authorized_project_count"] == 1
        for params in (
            {},
            {"project_id": str(hidden)},
            {"project_id": str(phase)},
            {"due_state": "overdue"},
            {"owner_user_id": str(owner.id)},
            {"offset": 20},
        ):
            assert client.get("/api/v1/portfolio/actions", params=params).json()["total"] == 0
        for suffix in ("", "/source", "/history"):
            assert client.get(f"/api/v1/portfolio/actions/{aid}{suffix}").status_code == 404
        for pid in (hidden, phase):
            assert (
                client.get("/api/v1/portfolio/outlook", params={"project_id": str(pid)}).json()[
                    "authorized_project_count"
                ]
                == 0
            )
            reply = client.post(
                "/api/v1/portfolio/actions",
                json={
                    "project_id": str(pid),
                    "title": "Not authorized",
                    "owner_user_id": str(owner.id),
                    "due_date": str(today),
                },
            )
            assert reply.status_code == 404
