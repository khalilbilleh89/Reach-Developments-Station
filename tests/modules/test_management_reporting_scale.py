"""Populated capture, payload and historical read cost; synthetic evidence only."""

import json
import uuid
from datetime import UTC, datetime
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import event, insert, select, text
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.management_actions.models import ManagementAction, ManagementActionHistory
from app.modules.management_reporting import board, comparison, repository, snapshot
from app.modules.management_reporting.schemas import Create
from tests.factories import make_user
from tests.modules.conftest import grant_access
from tests.modules.test_management_reporting import capture
from tests.modules.test_portfolio_scale import copy_project


def test_set_based_capture_one_twenty_fifty_and_historical_reads(
    admin_client: TestClient,
    project_id: str,
    confirmed_receipt: str,
    active_construction_forecast: str,
    db: Session,
) -> None:
    pids = [uuid.UUID(project_id)]
    for i in range(1, 50):
        pids.append(copy_project(db, pids[0], f"REPORT-{i:02}"))
    manager = make_user(db, email="report-scale@example.com", roles=("project_manager",))
    actor = ActorContext(
        user_id=manager.id,
        email=manager.email,
        display_name=manager.display_name,
        role_keys=frozenset({"project_manager"}),
        correlation_id=uuid.uuid4(),
        must_change_password=False,
    )
    captured = []

    def record(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        captured.append((statement, parameters))

    counts = []
    reports = []
    granted = 0
    engine = get_engine()
    for size in (1, 20, 50):
        for pid in pids[granted:size]:
            grant_access(admin_client, str(pid), manager)
        granted = size
        captured.clear()
        event.listen(engine, "before_cursor_execute", record)
        started = perf_counter()
        try:
            report = snapshot.capture(actor, Create(scope="portfolio"))
        finally:
            event.remove(engine, "before_cursor_execute", record)
        elapsed = perf_counter() - started
        assert report.project_count == size
        counts.append(len(captured))
        reports.append(report)
        print(
            f"CAPTURE projects={size} queries={len(captured)} seconds={elapsed:.4f} "
            f"payload_bytes={len(report.payload.model_dump_json().encode('utf-8'))}",
            flush=True,
        )
    assert max(counts) - min(counts) <= 2, counts
    assert max(counts) < 220, counts
    for name, read in (
        (
            "list",
            lambda: repository.page(
                db,
                actor,
                scope=None,
                project_id=None,
                created_from=None,
                created_to=None,
                limit=20,
                offset=0,
            ),
        ),
        ("detail", lambda: repository.detail(db, actor, reports[-1].id)),
        ("comparison", lambda: comparison.compare(db, reports[0], reports[-1])),
        ("board", lambda: board.board_pack(reports[-1], None)),
    ):
        captured.clear()
        event.listen(db.bind, "before_cursor_execute", record)
        started = perf_counter()
        try:
            result = read()
        finally:
            event.remove(db.bind, "before_cursor_execute", record)
        print(
            f"READ {name} queries={len(captured)} seconds={perf_counter() - started:.4f} "
            f"payload_bytes={len(result.model_dump_json().encode('utf-8'))}",
            flush=True,
        )
        assert len(captured) <= 2
    # Real stored snapshot list ordering/limit and scope relation index shapes.
    for sql in (
        "SELECT id FROM management_report_snapshots ORDER BY captured_at DESC,id DESC LIMIT 20",
        "SELECT snapshot_id FROM management_report_snapshot_projects "
        f"WHERE project_id='{project_id}'",
    ):
        plan = db.execute(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)).scalar_one()
        print("EXPLAIN", json.dumps(plan), flush=True)


def test_terminal_action_payload_retains_only_compact_visibility(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    now = datetime.now(UTC)
    owner = db.scalar(select(User).where(User.email == "admin@example.com"))
    rows, history = [], []
    for index in range(1000):
        aid = uuid.uuid4()
        title = f"Completed management commitment {index}: " + "historical detail " * 7
        rows.append(
            {
                "id": aid,
                "project_id": uuid.UUID(project_id),
                "title": title,
                "owner_user_id": owner.id,
                "created_by_user_id": owner.id,
                "status": "completed",
                "source_type": "manual",
                "version": 2,
                "due_date": now.date(),
                "completed_at": now,
            }
        )
        for version, event_type, changes in (
            (1, "created", {"title": {"old": None, "new": title}}),
            (2, "status_changed", {"status": {"old": "open", "new": "completed"}}),
        ):
            history.append(
                {
                    "action_id": aid,
                    "version": version,
                    "actor_user_id": owner.id,
                    "event_type": event_type,
                    "changes": changes,
                    "occurred_at": now,
                }
            )
    db.execute(insert(ManagementAction), rows)
    db.execute(insert(ManagementActionHistory), history)
    db.commit()
    report = capture(admin_client, project_id)
    assert report["payload"]["actions"] == []
    assert report["payload"]["action_counts"]["completed"] == 1000
    frontier = report["payload"]["action_frontier"]
    assert len(frontier) == 1000
    assert all(set(row) == {"id", "project_id", "version"} for row in frontier)
    from app.modules.management_actions import reporting
    from app.modules.projects.models import Project

    full = reporting.position(
        db, select(Project.id).where(Project.id == uuid.UUID(project_id)), now.date()
    )
    old_bytes = len(json.dumps([a.model_dump(mode="json") for a in full]).encode())
    new_bytes = len(json.dumps(frontier).encode())
    assert new_bytes < old_bytes // 2
    print(
        f"TERMINAL actions=1000 full_detail_bytes={old_bytes} frontier_bytes={new_bytes}",
        flush=True,
    )
