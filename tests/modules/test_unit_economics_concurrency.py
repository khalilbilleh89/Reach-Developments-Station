"""Concurrency: two people making one project's cost basis current at once.

Real PostgreSQL transactions on separate connections. A mocked session would
only prove the mock was called in the order the test chose, which is exactly the
thing under question.

The invariant is that a project has at most one current cost allocation basis.
Two active versions would mean two answers to "what does this unit cost", and
the two would be reported side by side without either being marked wrong. The
partial unique index makes it impossible; the project lock is what turns the
loser's outcome from a constraint violation into a sentence somebody can act on.

The second case is subtler and matters more. One person calculates and approves
a basis; somebody else re-approves an area schedule; the first person activates.
Nothing here is contended — the two never touch the same row — and the result is
still an approved allocation of a project that no longer exists. Freshness is
re-checked at activation for exactly that reason.

The harness mirrors the ones in the inventory, pricing, sales, payment-plan and
collections concurrency files. It is copied rather than shared because a test
file that cannot be read on its own is a test file nobody reads.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.core.errors import ConflictError
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.projects.models import Project
from app.modules.unit_economics import service
from app.modules.unit_economics.models import VERSION_ACTIVE, AllocationVersion
from tests.modules.conftest import (
    approve_areas,
    cover_required_pools,
    create_version,
    economics_url,
    today,
)


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
    """Built in the main thread and passed in, so no worker touches a detached row."""
    return ActorContext(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role_keys=user.role_keys,
        correlation_id=uuid.uuid4(),
        must_change_password=False,
    )


def _project(session: Session, project_id: uuid.UUID) -> Project:
    return session.scalars(select(Project).where(Project.id == project_id)).one()


@pytest.fixture
def two_approved_bases(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    priced_pair: tuple[str, str],
) -> tuple[str, str]:
    """Two rival cost bases for the same period, both approved, neither activated.

    Both start today deliberately, and on the same day. Two candidates for
    *different* periods are not a race at all — the later one legitimately
    supersedes the earlier — so a fixture that dated them apart would prove the
    supersede path and call it a conflict test. Today rather than a fixed date
    because a replacement may only ever take effect today; a past date would be
    refused before the race could happen, and the test would pass for the wrong
    reason.
    """
    del priced_pair
    approved: list[str] = []
    for index, hard in enumerate(("100000.00", "200000.00"), start=1):
        version_id = create_version(
            finance_client,
            project_id,
            effective_from=today(),
            reason=f"Candidate {index}",
        )
        cover_required_pools(finance_client, project_id, version_id, hard=hard)
        base = f"{economics_url(project_id)}/allocation-versions/{version_id}"
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Checked"}).status_code == 200
        approved.append(version_id)
    return approved[0], approved[1]


class TestTheActivationRace:
    """Given two approved bases, when both are activated at the same moment."""

    def test_only_one_becomes_current(
        self,
        db: Session,
        finance: User,
        second_finance: User,
        project_id: str,
        two_approved_bases: tuple[str, str],
    ) -> None:
        first, second = two_approved_bases
        project_uuid = uuid.UUID(project_id)
        holder_ready = threading.Event()
        holder_release = threading.Event()

        def make(
            actor_for: ActorContext, version_id: str, ready: threading.Event | None
        ) -> Callable[[Session], object]:
            def run(session: Session) -> object:
                local_project = _project(session, project_uuid)
                version = service.activate_version(
                    session,
                    project=local_project,
                    actor=actor_for,
                    version_id=uuid.UUID(version_id),
                    correlation_id=uuid.uuid4(),
                )
                if ready is not None:
                    ready.set()
                    holder_release.wait(timeout=15)
                session.commit()
                return version.status

            return run

        first_thread, first_outcome = _run(make(_actor(finance), first, holder_ready))
        assert holder_ready.wait(timeout=20)
        second_thread, second_outcome = _run(make(_actor(second_finance), second, None))
        assert _wait_until_a_backend_blocks(), "the second activation was never blocked"

        holder_release.set()
        first_thread.join(timeout=20)
        second_thread.join(timeout=20)

        assert first_outcome[0] == VERSION_ACTIVE
        assert isinstance(second_outcome[0], Exception), second_outcome[0]

        db.expire_all()
        active = db.scalars(
            select(AllocationVersion).where(
                AllocationVersion.project_id == project_uuid,
                AllocationVersion.status == VERSION_ACTIVE,
            )
        ).all()
        assert len(active) == 1
        assert str(active[0].id) == first

    def test_the_loser_is_told_what_happened_rather_than_shown_a_constraint(
        self,
        db: Session,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        two_approved_bases: tuple[str, str],
    ) -> None:
        """Sequentially, not concurrently: the same refusal, in a sentence."""
        first, second = two_approved_bases
        base = f"{economics_url(project_id)}/allocation-versions"
        assert finance_client.post(f"{base}/{first}/activate", json={}).status_code == 200
        losing = finance_client.post(f"{base}/{second}/activate", json={})
        assert losing.status_code == 409
        assert "already been governed" in losing.json()["detail"]

        db.expire_all()
        count = db.scalar(
            select(func.count())
            .select_from(AllocationVersion)
            .where(
                AllocationVersion.project_id == uuid.UUID(project_id),
                AllocationVersion.status == VERSION_ACTIVE,
            )
        )
        assert count == 1
        del cfo_client


class TestTheStaleSourceRace:
    """Given an approved basis, when its sources move before it is activated."""

    def test_activation_refuses_a_basis_whose_areas_changed_after_approval(
        self,
        finance: User,
        admin_client: TestClient,
        finance_client: TestClient,
        cfo_client: TestClient,
        db: Session,
        project_id: str,
        priced_pair: tuple[str, str],
        area_types: dict[str, str],
    ) -> None:
        """Nothing is contended here, and the answer would still be wrong."""
        first, _second = priced_pair
        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id)
        added = finance_client.post(
            f"{economics_url(project_id)}/allocation-versions/{version_id}/pools",
            json={
                "pool_number": "HARD-02",
                "name": "Construction",
                "category": "hard",
                "source_kind": "manual",
                "amount": "500000.00",
                "allocation_method": "weighted_area",
            },
        )
        assert added.status_code == 201, added.text
        base = f"{economics_url(project_id)}/allocation-versions/{version_id}"
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Checked"}).status_code == 200

        approve_areas(
            admin_client, project_id, first, area_types, internal="150.0000", revision="R2"
        )

        project_uuid = uuid.UUID(project_id)
        thread, outcome = _run(
            lambda session: service.activate_version(
                session,
                project=_project(session, project_uuid),
                actor=_actor(finance),
                version_id=uuid.UUID(version_id),
                correlation_id=uuid.uuid4(),
            )
        )
        thread.join(timeout=20)
        assert isinstance(outcome[0], ConflictError), outcome[0]
        assert "approved area schedule changed" in outcome[0].detail

        db.expire_all()
        assert (
            db.scalar(
                select(func.count())
                .select_from(AllocationVersion)
                .where(
                    AllocationVersion.project_id == project_uuid,
                    AllocationVersion.status == VERSION_ACTIVE,
                )
            )
            == 0
        )
