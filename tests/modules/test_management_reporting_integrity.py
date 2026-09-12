"""Real PostgreSQL immutability, complete scope, atomicity and MVCC evidence."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Select, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.modules.portfolio.schemas import ProjectSummary
from app.modules.projects.models import Project
from tests.conftest import alembic_config
from tests.modules.test_commissions_review import snapshot as source_rows
from tests.modules.test_management_reporting import ROOT, capture
from tests.modules.test_portfolio_scale import copy_project
from tests.test_migrations import HEAD_REVISION

TABLES = ("management_report_snapshots", "management_report_snapshot_projects")


def test_snapshot_db_immutability_scope_integrity_retained_downgrade(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    other = copy_project(db, uuid.UUID(project_id), "OTHER-SCOPE")
    original = source_rows(db, TABLES)
    report = capture(admin_client, project_id)
    assert source_rows(db, TABLES) == original
    for table in TABLES:
        for statement in (
            f"DELETE FROM {table}",
            f"UPDATE {table} SET {'id = id' if table == TABLES[0] else 'project_id = project_id'}",
        ):
            with pytest.raises(SQLAlchemyError, match="immutable"), db.begin_nested():
                db.execute(text(statement))
    with pytest.raises(SQLAlchemyError, match="scope"), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO management_report_snapshot_projects "
                "(snapshot_id, project_id) VALUES (:sid,:pid)"
            ),
            {"sid": report["id"], "pid": other},
        )
        db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    db.rollback()
    retained_rows = source_rows(db)
    # Release snapshot read locks before Alembic uses a separate connection.
    # Newer revisions may alter these source tables before reaching the guard.
    db.rollback()
    with pytest.raises(SQLAlchemyError, match="Retained management snapshots"):
        command.downgrade(alembic_config(), "0019_management_actions")
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION
    assert source_rows(db) == retained_rows
    assert admin_client.get(f"{ROOT}/snapshots/{report['id']}").json() == report
    # Test cleanup uses the suite's administrative TRUNCATE, not a product API.
    db.execute(text("TRUNCATE management_report_snapshot_projects, management_report_snapshots"))
    db.commit()
    command.downgrade(alembic_config(), "0019_management_actions")
    assert not set(TABLES) & set(inspect(get_engine()).get_table_names())
    command.upgrade(alembic_config(), "head")
    command.check(alembic_config())


def test_capture_reuses_one_repeatable_read_view(
    admin_client: TestClient,
    project_id: str,
    confirmed_receipt: str,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.collections.models import CollectionReceipt
    from app.modules.management_reporting import snapshot

    before = capture(admin_client, project_id)
    original = snapshot.service.summaries
    seen = []

    def compose_then_concurrent_write(
        session: Session, scope: Select, as_of: date
    ) -> list[ProjectSummary]:
        seen.append(session.scalar(text("SHOW transaction_isolation")))
        result = original(session, scope, as_of)

        def write() -> None:
            with get_session_factory()() as other:
                other.get(Project, uuid.UUID(project_id)).name = "Concurrent renamed project"
                receipt = other.get(CollectionReceipt, uuid.UUID(confirmed_receipt))
                receipt.amount += 900000
                other.commit()

        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(write).result(timeout=30)
        return result

    monkeypatch.setattr(snapshot.service, "summaries", compose_then_concurrent_write)
    captured = capture(admin_client, project_id)
    assert seen == ["repeatable read"]
    assert captured["payload"] == before["payload"]
    db.expire_all()
    assert db.get(Project, uuid.UUID(project_id)).name == "Concurrent renamed project"
    assert all(
        i["project_name"] != "Concurrent renamed project"
        for o in captured["payload"]["outlooks"]
        for i in o["items"]
    )


def test_capture_compare_and_board_write_only_snapshot_tables(
    admin_client: TestClient,
    project_id: str,
    confirmed_receipt: str,
    active_construction_forecast: str,
    db: Session,
) -> None:
    before = source_rows(db, TABLES)
    a = capture(admin_client, project_id)
    b = capture(admin_client, project_id)
    assert (
        admin_client.get(
            f"{ROOT}/snapshots/{b['id']}/board-pack?compare_to_snapshot_id={a['id']}"
        ).status_code
        == 200
    )
    assert source_rows(db, TABLES) == before
