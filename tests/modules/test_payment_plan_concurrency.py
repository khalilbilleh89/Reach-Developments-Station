"""Concurrency: the schedules a second writer could otherwise walk past.

Real PostgreSQL transactions on separate connections. A mocked session would
only prove the mock was called in the order the test chose, which is exactly
the thing under question.

The pattern: one transaction takes the same row lock the service takes and
holds it, the test waits until the second is genuinely blocked — by polling
PostgreSQL's own view of who is waiting rather than sleeping and hoping — then
the holder commits. The second writer must decide against the committed state,
not the state it read before it blocked.

The harness mirrors the ones in the inventory, pricing and sales concurrency
files. It is copied rather than shared because a test file that cannot be read
on its own is a test file nobody reads.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.core.errors import ConflictError
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.payment_plans import service
from app.modules.payment_plans.models import PaymentPlan, PaymentPlanVersion
from app.modules.projects.models import Project
from tests.modules.conftest import plans_url


def _wait_until_a_backend_blocks(timeout: float = 15.0) -> bool:
    query = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() "
        "AND pid <> pg_backend_pid() "
        "AND wait_event_type = 'Lock'"
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with get_engine().connect() as connection:
            if connection.execute(query).scalar():
                return True
        time.sleep(0.05)
    return False


def _run(target: Callable[[Session], object]) -> tuple[threading.Thread, list[object]]:
    outcome: list[object] = []

    def wrapper() -> None:
        session = get_session_factory()()
        try:
            outcome.append(target(session))
        # Deliberately broad: whatever the writer raises has to reach the
        # asserting thread, which cannot see this thread's traceback.
        except BaseException as exc:
            outcome.append(exc)
        finally:
            session.rollback()
            session.close()

    thread = threading.Thread(target=wrapper)
    thread.start()
    return thread, outcome


def _actor(user: User) -> ActorContext:
    return ActorContext(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role_keys=user.role_keys,
        correlation_id=uuid.uuid4(),
        must_change_password=False,
    )


def _project(session: Session, project_id: str) -> Project:
    return session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()


def test_two_revisions_cannot_take_the_same_version_number(
    db: Session,
    collections_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
    collections_officer: User,
) -> None:
    """Both writers ask for "the next version". They must not both get 2."""
    plan_id, _version_id = active_plan
    actor = _actor(collections_officer)

    def revise(session: Session) -> object:
        version = service.create_version(
            session,
            project=_project(session, project_id),
            actor=actor,
            plan_id=uuid.UUID(plan_id),
            change_reason="Concurrent revision",
            reservation_treatment=None,
            effective_date=None,
            correlation_id=uuid.uuid4(),
        )
        session.commit()
        return version.version_number

    holder_session = get_session_factory()()
    try:
        # Hold the plan row exactly as the service does.
        holder_session.scalars(
            select(PaymentPlan).where(PaymentPlan.id == uuid.UUID(plan_id)).with_for_update()
        ).one()
        thread, outcome = _run(revise)
        assert _wait_until_a_backend_blocks(), "the second writer never blocked"
        holder_session.rollback()
        thread.join(timeout=20)
    finally:
        holder_session.close()

    assert outcome and outcome[0] == 2

    # A second revision, now that one is open, is refused rather than duplicated.
    second = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions", json={"change_reason": "Another"}
    )
    assert second.status_code == 409

    numbers = [
        version.version_number
        for version in db.scalars(
            select(PaymentPlanVersion).where(
                PaymentPlanVersion.payment_plan_id == uuid.UUID(plan_id)
            )
        )
    ]
    assert sorted(numbers) == [1, 2]


def test_only_one_version_survives_a_race_to_activate(
    db: Session,
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
    cfo: User,
) -> None:
    """Two approved schedules, both activating. One must end up governing."""
    plan_id, first_version = active_plan
    created = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions", json={"change_reason": "Revision"}
    )
    second_version = created.json()["version"]["id"]
    base = f"{plans_url(project_id)}/{plan_id}/versions/{second_version}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Agreed"}).status_code == 200

    actor = _actor(cfo)

    def activate(session: Session) -> object:
        version = service.activate_version(
            session,
            project=_project(session, project_id),
            actor=actor,
            plan_id=uuid.UUID(plan_id),
            version_id=uuid.UUID(second_version),
            correlation_id=uuid.uuid4(),
        )
        session.commit()
        return version.status

    holder_session = get_session_factory()()
    try:
        holder_session.scalars(
            select(PaymentPlan).where(PaymentPlan.id == uuid.UUID(plan_id)).with_for_update()
        ).one()
        thread, outcome = _run(activate)
        assert _wait_until_a_backend_blocks(), "the activation never blocked"
        holder_session.rollback()
        thread.join(timeout=20)
    finally:
        holder_session.close()

    assert outcome and outcome[0] == "active"

    db.expire_all()
    active = [
        version.id
        for version in db.scalars(
            select(PaymentPlanVersion).where(
                PaymentPlanVersion.payment_plan_id == uuid.UUID(plan_id),
                PaymentPlanVersion.status == "active",
            )
        )
    ]
    assert len(active) == 1
    assert str(active[0]) == second_version
    superseded = db.scalars(
        select(PaymentPlanVersion).where(PaymentPlanVersion.id == uuid.UUID(first_version))
    ).one()
    assert superseded.status == "superseded"


def test_activating_an_already_superseded_version_is_refused(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
    cfo: User,
) -> None:
    """The loser of the race decides against committed state, not stale state."""
    plan_id, first_version = active_plan
    created = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions", json={"change_reason": "Revision"}
    )
    second_version = created.json()["version"]["id"]
    base = f"{plans_url(project_id)}/{plan_id}/versions/{second_version}"
    collections_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "Agreed"})
    assert cfo_client.post(f"{base}/activate", json={}).status_code == 200

    refused = cfo_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{first_version}/activate", json={}
    )
    assert refused.status_code == 409
    assert "approved schedule" in refused.json()["detail"]


def test_a_schedule_replacement_and_a_submission_cannot_interleave(
    db: Session,
    collections_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
    collections_officer: User,
) -> None:
    """Never half the old schedule and half the new one.

    The submitting writer blocks on the version row the replacement holds, and
    when it proceeds it reconciles the committed schedule — so it either sees
    the whole replacement or the whole original.
    """
    plan_id, version_id = reconciled_plan
    actor = _actor(collections_officer)

    def submit(session: Session) -> object:
        version = service.submit_version(
            session,
            project=_project(session, project_id),
            actor=actor,
            plan_id=uuid.UUID(plan_id),
            version_id=uuid.UUID(version_id),
            correlation_id=uuid.uuid4(),
        )
        session.commit()
        return version.status

    holder_session = get_session_factory()()
    try:
        holder_session.scalars(
            select(PaymentPlanVersion)
            .where(PaymentPlanVersion.id == uuid.UUID(version_id))
            .with_for_update()
        ).one()
        # Replace the schedule with one that does NOT reconcile, then commit.
        holder_session.execute(
            text("DELETE FROM payment_plan_installments WHERE payment_plan_version_id = :v"),
            {"v": version_id},
        )
        holder_session.execute(
            text(
                "INSERT INTO payment_plan_installments (id, project_id,"
                " payment_plan_version_id, sequence, label, trigger_type,"
                " contractual_due_date, trigger_status, grace_days, principal_amount,"
                " principal_fraction, tax_amount, fee_amount)"
                " VALUES (:id, :p, :v, 1, 'Half', 'fixed_date', '2026-03-01', 'scheduled',"
                " 0, 1.00, 0.500000, 0, 0)"
            ),
            {"id": uuid.uuid4(), "p": project_id, "v": version_id},
        )
        thread, outcome = _run(submit)
        assert _wait_until_a_backend_blocks(), "the submission never blocked"
        holder_session.commit()
        thread.join(timeout=20)
    finally:
        holder_session.close()

    # The submission saw the committed replacement, and refused it.
    assert outcome
    assert isinstance(outcome[0], ConflictError), outcome[0]

    db.expire_all()
    version = db.scalars(
        select(PaymentPlanVersion).where(PaymentPlanVersion.id == uuid.UUID(version_id))
    ).one()
    assert version.status == "draft"


def test_a_second_plan_for_one_sale_loses_at_the_unique_index(
    db: Session, project_id: str, active_sale: str, plan_id: str, collections_officer: User
) -> None:
    """The service refuses it first; the index is the backstop if it does not."""
    plan = db.scalars(select(PaymentPlan).where(PaymentPlan.id == uuid.UUID(plan_id))).one()
    duplicate = PaymentPlan(
        project_id=plan.project_id,
        sale_contract_id=plan.sale_contract_id,
        plan_number="PLN-000900",
        name="Racing duplicate",
        created_by_user_id=collections_officer.id,
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
