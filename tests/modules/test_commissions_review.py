"""Review evidence: sale eligibility, independent finances, history, and real races."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.core.errors import ConflictError
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.commissions import schemas, service
from app.modules.projects.models import Project
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/commissions"


def snapshot(db: Session, excluded: tuple[str, ...] = ()) -> dict:
    """Compare full persisted rows, including values and timestamps, not just counts."""
    tables = db.scalars(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
    ).all()
    return {
        table: db.execute(text(f'SELECT to_jsonb(t) FROM "{table}" t ORDER BY to_jsonb(t)::text'))
        .scalars()
        .all()
        for table in tables
        if table not in (*excluded, "user_sessions")
    }


def prepare(client: TestClient, project_id: str, sale_id: str) -> dict:
    result = client.post(
        root(project_id),
        json={
            "sale_contract_id": sale_id,
            "commissionable_base_amount": "100",
            "granted_rate_fraction": "0.1",
        },
    )
    assert result.status_code == 201, result.text
    identifier = result.json()["id"]
    result = client.post(
        f"{root(project_id)}/{identifier}/allocations",
        json={
            "beneficiary_name": "Branch",
            "rate_fraction": "0.1",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["is_reconciled"]
    return result.json()


def actor(user: User) -> ActorContext:
    return ActorContext(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role_keys=user.role_keys,
        correlation_id=uuid.uuid4(),
        must_change_password=False,
    )


def test_financial_independence_and_immutable_history(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
    db: Session,
    cfo: User,
) -> None:
    # Includes populated sale, pricing and physical-unit state; also guards every
    # empty downstream ledger against an unexpected insert.
    before = snapshot(db, ("audit_events", "commission_grants", "commission_allocations"))
    grant = prepare(finance_client, project_id, active_sale)
    url = f"{root(project_id)}/{grant['id']}"
    released = cfo_client.post(f"{url}/release")
    assert released.status_code == 200, released.text
    assert snapshot(db, ("audit_events", "commission_grants", "commission_allocations")) == before
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "commission.released")).one()
    assert event.actor_user_id == cfo.id and str(event.entity_id) == grant["id"]
    assert event.before_data == {"status": "draft"}
    assert event.after_data == {"status": "released", "project_id": project_id}
    # An upstream status change after release does not alter historical distribution.
    db.execute(
        text("UPDATE sale_contracts SET status='cancelled' WHERE id=CAST(:id AS uuid)"),
        {"id": active_sale},
    )
    db.commit()
    history = cfo_client.get(url).json()
    assert history["status"] == "released" and history["sale_status"] == "cancelled"
    for key in ("released_at", "released_by_user_id", "commission_total", "allocations"):
        assert history[key] == released.json()[key]
    forbidden = finance_client.put(
        url,
        json={
            "commissionable_base_amount": "90",
            "granted_rate_fraction": "0.1",
            "expected_updated_at": history["updated_at"],
        },
    )
    assert forbidden.status_code == 409
    reversed_result = cfo_client.post(f"{url}/reverse", json={"reason": "Sale cancelled"})
    assert reversed_result.status_code == 200
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "commission.reversed")).one()
    assert event.actor_user_id == cfo.id and str(event.entity_id) == grant["id"]
    assert event.after_data == {"status": "reversed", "project_id": project_id}
    assert cfo_client.post(f"{url}/reverse", json={"reason": "Again"}).status_code == 409
    assert (
        len(db.scalars(select(AuditEvent).where(AuditEvent.action == "commission.reversed")).all())
        == 1
    )


def test_cancelled_sale_refuses_release_without_side_effect(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
    db: Session,
) -> None:
    grant = prepare(finance_client, project_id, active_sale)
    db.execute(
        text("UPDATE sale_contracts SET status='cancelled' WHERE id=CAST(:id AS uuid)"),
        {"id": active_sale},
    )
    db.commit()
    before = snapshot(db)
    result = cfo_client.post(f"{root(project_id)}/{grant['id']}/release")
    assert result.status_code == 409 and "active sale" in result.json()["detail"]
    assert snapshot(db) == before
    assert cfo_client.get(f"{root(project_id)}/{grant['id']}").json()["status"] == "draft"
    assert (
        db.scalar(select(AuditEvent.id).where(AuditEvent.action == "commission.released")) is None
    )


def test_draft_terms_and_beneficiaries_can_be_corrected(
    finance_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    grant = prepare(finance_client, project_id, active_sale)
    url = f"{root(project_id)}/{grant['id']}"
    updated = finance_client.put(
        url,
        json={
            "commissionable_base_amount": "80",
            "granted_rate_fraction": "0.2",
            "notes": "Corrected terms",
            "expected_updated_at": grant["updated_at"],
        },
    )
    assert updated.status_code == 200, updated.text
    grant = updated.json()
    assert grant["commission_total"] == "16.00" and not grant["is_reconciled"]
    allocation = grant["allocations"][0]
    changed = finance_client.put(
        f"{url}/allocations/{allocation['id']}",
        json={
            "beneficiary_name": "Corrected branch",
            "rate_fraction": "0.2",
            "notes": "Corrected beneficiary",
            "expected_updated_at": allocation["updated_at"],
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["is_reconciled"]
    assert changed.json()["allocations"][0]["calculated_amount"] == "16.00"
    removed = finance_client.delete(f"{url}/allocations/{allocation['id']}")
    assert removed.status_code == 200
    assert removed.json()["allocations"] == [] and not removed.json()["is_reconciled"]


def test_retained_commission_refuses_downgrade(
    finance_client: TestClient,
    project_id: str,
    active_sale: str,
    db: Session,
) -> None:
    prepare(finance_client, project_id, active_sale)
    before = snapshot(db)
    db.rollback()
    try:
        with pytest.raises(
            SQLAlchemyError, match="cannot downgrade while consultant or commission"
        ):
            command.downgrade(alembic_config(), "0016_prelaunch_utilities")
        assert snapshot(db) == before
        assert (
            db.scalar(text("SELECT version_num FROM alembic_version"))
            == "0017_consultant_commissions"
        )
    finally:
        db.rollback()
        command.upgrade(alembic_config(), "head")


def test_two_live_creations_and_two_releases(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
    finance: User,
    cfo: User,
    db: Session,
) -> None:
    del finance_client, cfo_client
    maker, checker = actor(finance), actor(cfo)
    project_uuid = uuid.UUID(project_id)
    barrier = Barrier(2)

    def create() -> object:
        with get_session_factory()() as session:
            project = session.get(Project, project_uuid)
            barrier.wait(timeout=15)
            try:
                return service.create(
                    session,
                    project,
                    maker,
                    schemas.GrantCreate(
                        sale_contract_id=active_sale,
                        commissionable_base_amount="100",
                        granted_rate_fraction="0.1",
                    ),
                )
            except ConflictError as exc:
                return exc

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(create) for _ in range(2)]
        outcomes = [future.result(timeout=30) for future in futures]
    assert sum(isinstance(x, ConflictError) for x in outcomes) == 1
    assert db.scalar(text("SELECT count(*) FROM commission_grants WHERE status='draft'")) == 1
    identifier = db.scalar(text("SELECT id FROM commission_grants"))
    with get_session_factory()() as session:
        service.add_allocation(
            session,
            session.get(Project, project_uuid),
            maker,
            identifier,
            schemas.AllocationWrite(beneficiary_name="Branch", rate_fraction="0.1"),
        )
    barrier = Barrier(2)

    def release() -> object:
        with get_session_factory()() as session:
            project = session.get(Project, project_uuid)
            # Preload to exercise refresh after the competing transaction commits.
            service._get(session, project, identifier)
            barrier.wait(timeout=15)
            try:
                return service.release(session, project, checker, identifier)
            except ConflictError as exc:
                return exc

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(release) for _ in range(2)]
        outcomes = [future.result(timeout=30) for future in futures]
    assert sum(isinstance(x, ConflictError) for x in outcomes) == 1
    assert db.scalar(text("SELECT count(*) FROM commission_grants WHERE status='released'")) == 1
    assert db.scalar(text("SELECT count(*) FROM commission_allocations")) == 1
    assert (
        db.scalar(text("SELECT count(*) FROM audit_events WHERE action='commission.released'")) == 1
    )
    get_engine().dispose()


def test_phase_and_role_boundaries(
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
    db: Session,
    advisor_client: TestClient,
    sales_ops_client: TestClient,
    active_sale: str,
) -> None:
    assert advisor_client.get(root(project_id)).status_code == 403
    grant = prepare(sales_ops_client, project_id, active_sale)
    assert sales_ops_client.post(f"{root(project_id)}/{grant['id']}/release").status_code == 403
    scoped = make_user(db, email="phase-commission@example.com", roles=("finance",))
    grant_access(admin_client, project_id, scoped)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{scoped.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    admin_client.put(f"/api/v1/projects/{project_id}/access/{scoped.id}/phases/{phase_id}")
    assert client_for(scoped.email).get(root(project_id)).status_code == 403
