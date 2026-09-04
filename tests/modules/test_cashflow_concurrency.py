"""Four races, on real PostgreSQL transactions across separate connections.

Every one is the same shape: two people read the same remaining capacity, both
act on it, and without a lock both succeed. The capacity differs — an escrow's
unreleased balance, a movement's unconfirmed state, a project's single active
forecast — and so does what it costs to get it wrong.

A mocked session would only prove the mock was called in the order the test
chose, which is exactly the thing under question. The harness mirrors the ones
in the inventory, pricing, sales, payment-plan, collections, unit-economics and
construction concurrency files; it is copied rather than shared because a test
file that cannot be read on its own is a test file nobody reads.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.core.errors import ConflictError, PermissionDeniedError
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.cashflow import service
from app.modules.cashflow.models import (
    FORECAST_ACTIVE,
    MOVEMENT_CONFIRMED,
    CashflowDevelopmentMovement,
    CashflowFinancingMovement,
    CashflowForecastVersion,
    CashflowRestrictionRelease,
)
from app.modules.projects.models import Project
from tests.modules.conftest import (
    cashflow_url,
    confirm_receipt,
    create_cashflow_forecast,
    month_named,
    record_development,
    record_financing,
    record_receipt,
    restrict_receipt,
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


def _race(
    first: Callable[[Session], object],
    second: Callable[[Session], object],
    holder_ready: threading.Event,
    holder_release: threading.Event,
) -> tuple[list[object], list[object]]:
    """Start ``first``, hold its lock, run ``second`` into it, then let go."""
    holder, first_outcome = _run(first)
    assert holder_ready.wait(timeout=15), "the first writer never reached its lock"

    contender, second_outcome = _run(second)
    assert _wait_until_a_backend_blocks(), "the second writer never blocked on a lock"

    holder_release.set()
    holder.join(timeout=20)
    contender.join(timeout=20)
    return first_outcome, second_outcome


@pytest.fixture
def cash_forecast(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    flat_construction_forecast: str,
) -> str:
    from tests.modules.conftest import govern_cashflow_forecast

    created = create_cashflow_forecast(
        finance_client,
        project_id,
        forecast_start_month=month_named(0),
        forecast_end_month=month_named(2),
    )
    assert created.status_code == 201, created.text
    identifier: str = created.json()["id"]
    assert (
        govern_cashflow_forecast(finance_client, cfo_client, project_id, identifier).status_code
        == 200
    )
    return identifier


class TestAnEscrowCannotOverRelease:
    def test_two_releases_of_eighty_against_a_hundred_cannot_both_stand(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        collections_client: TestClient,
        db: Session,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
        finance: User,
    ) -> None:
        """Given / When / Then: both read 100 available; only one may write.

        Without the restriction's row lock both pass their own ceiling check and
        160 is released against 100 held — an escrow account reporting more money
        freed than it ever contained.
        """
        receipt = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "100.00",
            receipt_date=date.today().isoformat(),
        )
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)
        restriction = restrict_receipt(
            finance_client, project_id, receipt_id, restricted_amount="100.00"
        )
        restriction_id = uuid.UUID(restriction.json()["id"])
        second_finance_client.post(
            f"{cashflow_url(project_id)}/restrictions/{restriction_id}/confirm", json={}
        )

        ready = threading.Event()
        release = threading.Event()
        actor = _actor(finance)
        identifier = uuid.UUID(project_id)

        def holder(session: Session) -> object:
            outcome = service.record_release(
                session,
                project=_project(session, identifier),
                actor=actor,
                restriction_id=restriction_id,
                release_date=date.today(),
                amount=Decimal("80.00"),
            )
            ready.set()
            assert release.wait(timeout=15)
            session.commit()
            return outcome

        def contender(session: Session) -> object:
            return service.record_release(
                session,
                project=_project(session, identifier),
                actor=actor,
                restriction_id=restriction_id,
                release_date=date.today(),
                amount=Decimal("80.00"),
            )

        first, second = _race(holder, contender, ready, release)
        assert not isinstance(first[0], BaseException), first[0]
        assert isinstance(second[0], ConflictError), second[0]

        standing = db.scalars(
            select(func.count())
            .select_from(CashflowRestrictionRelease)
            .where(CashflowRestrictionRelease.restriction_id == restriction_id)
        ).one()
        assert standing == 1


class TestOneConfirmationPerMovement:
    def test_two_confirmations_of_one_development_movement_leave_one_truth(
        self,
        finance_client: TestClient,
        db: Session,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
        second_finance: User,
        cfo: User,
    ) -> None:
        """Confirming twice would let one disbursement count as cash twice."""
        movement_id = uuid.UUID(
            record_development(finance_client, project_id, currency_id).json()["id"]
        )
        ready = threading.Event()
        release = threading.Event()
        identifier = uuid.UUID(project_id)
        first_actor, second_actor = _actor(second_finance), _actor(cfo)

        def holder(session: Session) -> object:
            outcome = service.confirm_development_movement(
                session,
                project=_project(session, identifier),
                actor=first_actor,
                movement_id=movement_id,
            )
            ready.set()
            assert release.wait(timeout=15)
            session.commit()
            return outcome

        def contender(session: Session) -> object:
            return service.confirm_development_movement(
                session,
                project=_project(session, identifier),
                actor=second_actor,
                movement_id=movement_id,
            )

        first, second = _race(holder, contender, ready, release)
        assert not isinstance(first[0], BaseException), first[0]
        assert isinstance(second[0], ConflictError), second[0]

        confirmed = db.scalars(
            select(func.count())
            .select_from(CashflowDevelopmentMovement)
            .where(
                CashflowDevelopmentMovement.id == movement_id,
                CashflowDevelopmentMovement.status == MOVEMENT_CONFIRMED,
            )
        ).one()
        assert confirmed == 1

    def test_two_confirmations_of_one_financing_movement_leave_one_truth(
        self,
        finance_client: TestClient,
        db: Session,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
        second_finance: User,
        cfo: User,
    ) -> None:
        """The same race on the other side of the ledger: equity counted twice."""
        movement_id = uuid.UUID(
            record_financing(finance_client, project_id, currency_id).json()["id"]
        )
        ready = threading.Event()
        release = threading.Event()
        identifier = uuid.UUID(project_id)
        first_actor, second_actor = _actor(second_finance), _actor(cfo)

        def holder(session: Session) -> object:
            outcome = service.confirm_financing_movement(
                session,
                project=_project(session, identifier),
                actor=first_actor,
                movement_id=movement_id,
            )
            ready.set()
            assert release.wait(timeout=15)
            session.commit()
            return outcome

        def contender(session: Session) -> object:
            return service.confirm_financing_movement(
                session,
                project=_project(session, identifier),
                actor=second_actor,
                movement_id=movement_id,
            )

        first, second = _race(holder, contender, ready, release)
        assert not isinstance(first[0], BaseException), first[0]
        assert isinstance(second[0], ConflictError), second[0]

        confirmed = db.scalars(
            select(func.count())
            .select_from(CashflowFinancingMovement)
            .where(
                CashflowFinancingMovement.id == movement_id,
                CashflowFinancingMovement.status == MOVEMENT_CONFIRMED,
            )
        ).one()
        assert confirmed == 1


class TestOneActiveForecast:
    def test_two_approved_versions_racing_to_activate_leave_exactly_one_in_force(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        db: Session,
        project_id: str,
        flat_construction_forecast: str,
        finance: User,
        cfo: User,
    ) -> None:
        """Two forecasts in force is two answers to what the company will fund.

        The partial unique index would refuse the second write even if the lock
        did not, which is the belt-and-braces this asserts: whichever mechanism
        catches it, exactly one version is active afterwards.
        """
        first_id = create_cashflow_forecast(
            finance_client,
            project_id,
            forecast_start_month=month_named(0),
            forecast_end_month=month_named(2),
        ).json()["id"]
        base = f"{cashflow_url(project_id)}/forecasts/{first_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200

        ready = threading.Event()
        release = threading.Event()
        identifier = uuid.UUID(project_id)
        version_id = uuid.UUID(first_id)
        first_actor, second_actor = _actor(finance), _actor(cfo)

        def holder(session: Session) -> object:
            outcome = service.activate_forecast(
                session,
                project=_project(session, identifier),
                actor=first_actor,
                version_id=version_id,
            )
            ready.set()
            assert release.wait(timeout=15)
            session.commit()
            return outcome

        def contender(session: Session) -> object:
            return service.activate_forecast(
                session,
                project=_project(session, identifier),
                actor=second_actor,
                version_id=version_id,
            )

        first, second = _race(holder, contender, ready, release)
        assert not isinstance(first[0], BaseException), first[0]
        assert isinstance(second[0], BaseException), second[0]

        active = db.scalars(
            select(func.count())
            .select_from(CashflowForecastVersion)
            .where(
                CashflowForecastVersion.project_id == identifier,
                CashflowForecastVersion.status == FORECAST_ACTIVE,
            )
        ).one()
        assert active == 1


class TestTheMakerRuleSurvivesTheRace:
    def test_the_recorder_is_refused_even_when_they_get_there_first(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
        finance: User,
    ) -> None:
        """A lock orders writers; it does not make one of them a second person."""
        movement_id = uuid.UUID(
            record_development(finance_client, project_id, currency_id).json()["id"]
        )
        session = get_session_factory()()
        try:
            with pytest.raises(PermissionDeniedError):
                service.confirm_development_movement(
                    session,
                    project=_project(session, uuid.UUID(project_id)),
                    actor=_actor(finance),
                    movement_id=movement_id,
                )
        finally:
            session.rollback()
            session.close()
