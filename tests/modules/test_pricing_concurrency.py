"""Concurrency: the pricing invariants a second writer could otherwise walk past.

Every test here runs two real PostgreSQL transactions on separate connections.
A mocked session would only prove the mock was called in the order the test
chose, which is exactly the thing under question.

The pattern throughout: one transaction takes the same row lock the service
takes and holds it, the test waits until the second is genuinely blocked — by
polling PostgreSQL's own view of who is waiting rather than sleeping and hoping
— then the holder commits. The second writer must then decide against the
committed state, not the state it read before it blocked.

The harness below mirrors the one in ``test_inventory_concurrency``. It is
copied rather than shared because a test file that cannot be read on its own is
a test file nobody reads.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.inventory import service as inventory
from app.modules.inventory.models import Unit, UnitAreaSchedule
from app.modules.pricing import service
from app.modules.pricing.models import PricingConfiguration, UnitPriceVersion
from app.modules.projects.models import Project
from tests.modules.conftest import approve_areas, configuration_payload, inventory_url, pricing_url


def _wait_until_a_backend_blocks(timeout: float = 15.0) -> bool:
    """Poll until another backend in this database is waiting on a lock."""
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
    """Start ``target`` on its own connection, carrying its outcome back."""
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


# --------------------------------------------------------------------------- #
# One active pricing configuration
# --------------------------------------------------------------------------- #


def test_two_configurations_cannot_both_become_active(
    finance_client: TestClient,
    cfo_client: TestClient,
    cfo: User,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
    db: Session,
) -> None:
    """Given a held project lock, then the second activation sees the first.

    Without the lock both writers read "nothing is active", both supersede
    nothing, and the project ends up with two live pricing policies — which
    makes "what rate is this development priced at" a question with two answers.
    """
    second = finance_client.post(
        f"{pricing_url(project_id)}/configurations",
        json=configuration_payload(currency_id, name="Second", base_internal_rate="1650.00"),
    ).json()["id"]
    finance_client.post(
        f"{pricing_url(project_id)}/configurations/{second}/area-rules",
        json={"area_type_id": area_types["INTERNAL"], "pricing_method": "internal_base"},
    )
    for configuration_id in (draft_configuration, second):
        base = f"{pricing_url(project_id)}/configurations/{configuration_id}"
        finance_client.post(f"{base}/submit", json={})
        cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update())

    def activate_second(session: Session) -> str:
        configuration = service.get_configuration(
            session,
            project_id=uuid.UUID(project_id),
            configuration_id=uuid.UUID(second),
        )
        service.activate_configuration(
            session,
            project=_project(session, project_id),
            configuration=configuration,
            actor=_actor(cfo),
        )
        return "activated"

    thread, outcome = _run(activate_second)
    try:
        blocked = _wait_until_a_backend_blocks()
        locked = holder.scalars(
            select(PricingConfiguration).where(
                PricingConfiguration.id == uuid.UUID(draft_configuration)
            )
        ).one()
        locked.status = "active"
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the activation decided without taking the project lock"
    assert not isinstance(outcome[0], BaseException), outcome[0]
    db.expire_all()
    statuses = {str(row.id): row.status for row in db.scalars(select(PricingConfiguration)).all()}
    assert statuses[second] == "active"
    assert statuses[draft_configuration] == "superseded"


def test_the_database_refuses_a_second_active_configuration(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    active_configuration: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """The service lock could be removed by a careless refactor; this could not."""
    second = finance_client.post(
        f"{pricing_url(project_id)}/configurations",
        json=configuration_payload(currency_id, name="Second"),
    ).json()["id"]

    row = db.scalars(
        select(PricingConfiguration).where(PricingConfiguration.id == uuid.UUID(second))
    ).one()
    row.status = "active"
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --------------------------------------------------------------------------- #
# Version numbers
# --------------------------------------------------------------------------- #


def test_two_writers_cannot_produce_two_version_fours(
    admin_client: TestClient,
    finance_client: TestClient,
    finance: User,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Given a held unit lock, then the next version number is read after the wait.

    ``SELECT max(version_number)`` and hope is the shape that produces two rows
    both claiming to be version 2, one of which loses at the unique index with
    nothing useful to say about why.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    finance_client.post(f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={})

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(unit_id)).with_for_update())

    def generate(session: Session) -> int:
        unit = session.scalars(select(Unit).where(Unit.id == uuid.UUID(unit_id))).one()
        version = service.generate_price_version(
            session, project=_project(session, project_id), unit=unit, actor=_actor(finance)
        )
        return version.version_number

    thread, outcome = _run(generate)
    try:
        blocked = _wait_until_a_backend_blocks()
        # The holder inserts version 2 while the other writer is still waiting.
        existing = holder.scalars(
            select(UnitPriceVersion).where(UnitPriceVersion.unit_id == uuid.UUID(unit_id))
        ).one()
        holder.add(
            UnitPriceVersion(
                project_id=existing.project_id,
                unit_id=existing.unit_id,
                version_number=2,
                pricing_configuration_id=existing.pricing_configuration_id,
                unit_area_schedule_id=existing.unit_area_schedule_id,
                status="draft",
                currency_id=existing.currency_id,
                base_area_value=Decimal("0.00"),
                scope_adjustment_total=Decimal("0.00"),
                premium_total=Decimal("0.00"),
                premium_cap_adjustment=Decimal("0.00"),
                escalation_total=Decimal("0.00"),
                paid_upgrade_total=Decimal("0.00"),
                reference_price_ex_tax=Decimal("0.00"),
                basis_snapshot_json={},
                created_by_user_id=existing.created_by_user_id,
            )
        )
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the version number was read without taking the unit lock"
    assert outcome[0] == 3, outcome[0]
    db.expire_all()
    numbers = sorted(row.version_number for row in db.scalars(select(UnitPriceVersion)))
    assert numbers == [1, 2, 3]


def test_the_database_refuses_a_duplicate_version_number(
    project_id: str, unit_id: str, priced_unit: str, db: Session
) -> None:
    existing = db.scalars(select(UnitPriceVersion)).one()

    db.add(
        UnitPriceVersion(
            project_id=existing.project_id,
            unit_id=existing.unit_id,
            version_number=existing.version_number,
            pricing_configuration_id=existing.pricing_configuration_id,
            unit_area_schedule_id=existing.unit_area_schedule_id,
            status="draft",
            currency_id=existing.currency_id,
            base_area_value=Decimal("0.00"),
            scope_adjustment_total=Decimal("0.00"),
            premium_total=Decimal("0.00"),
            premium_cap_adjustment=Decimal("0.00"),
            escalation_total=Decimal("0.00"),
            paid_upgrade_total=Decimal("0.00"),
            reference_price_ex_tax=Decimal("0.00"),
            basis_snapshot_json={},
            created_by_user_id=existing.created_by_user_id,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --------------------------------------------------------------------------- #
# One active price per unit
# --------------------------------------------------------------------------- #


def test_two_approved_prices_cannot_both_become_the_list_price(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    cfo: User,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Given a held unit lock, then the second activation supersedes the first."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    versions = []
    for _ in range(2):
        version = finance_client.post(
            f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
        ).json()["id"]
        base = f"{pricing_url(project_id)}/price-versions/{version}"
        finance_client.post(f"{base}/submit", json={})
        cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})
        versions.append(version)

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(unit_id)).with_for_update())

    def activate_second(session: Session) -> str:
        version = service.get_price_version(
            session,
            project_id=uuid.UUID(project_id),
            version_id=uuid.UUID(versions[1]),
        )
        service.activate_price_version(
            session,
            project=_project(session, project_id),
            version=version,
            actor=_actor(cfo),
        )
        return "activated"

    thread, outcome = _run(activate_second)
    try:
        blocked = _wait_until_a_backend_blocks()
        first = holder.scalars(
            select(UnitPriceVersion).where(UnitPriceVersion.id == uuid.UUID(versions[0]))
        ).one()
        first.status = "active"
        first.valid_from = date(2026, 1, 1)
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the activation decided without taking the unit lock"
    assert not isinstance(outcome[0], BaseException), outcome[0]
    db.expire_all()
    statuses = {str(row.id): row.status for row in db.scalars(select(UnitPriceVersion))}
    assert statuses[versions[1]] == "active"
    assert statuses[versions[0]] == "superseded"
    assert sum(1 for status in statuses.values() if status == "active") == 1


def test_the_database_refuses_a_second_active_price(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    second = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    ).json()["id"]

    row = db.scalars(select(UnitPriceVersion).where(UnitPriceVersion.id == uuid.UUID(second))).one()
    row.status = "active"
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --------------------------------------------------------------------------- #
# Pricing against inventory
# --------------------------------------------------------------------------- #


def test_a_draft_price_is_never_calculated_from_superseded_geometry(
    admin_client: TestClient,
    finance_client: TestClient,
    finance: User,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Given an area approval committing during the wait, then the price uses it.

    Price generation and area approval both take the unit lock, so they
    serialise. The writer that waits re-reads the approved schedule afterwards
    and prices the measurement that is current now — not the one that was
    current when the request arrived.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    revised = admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules",
        json={
            "revision_code": "R1",
            "reconciled": True,
            "values": [
                {"area_type_id": area_types["INTERNAL"], "raw_area": "120.0000"},
                {"area_type_id": area_types["BALCONY"], "raw_area": "20.0000"},
            ],
        },
    ).json()["id"]

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(unit_id)).with_for_update())

    def generate(session: Session) -> str:
        unit = session.scalars(select(Unit).where(Unit.id == uuid.UUID(unit_id))).one()
        version = service.generate_price_version(
            session, project=_project(session, project_id), unit=unit, actor=_actor(finance)
        )
        return str(version.reference_price_ex_tax)

    thread, outcome = _run(generate)
    try:
        blocked = _wait_until_a_backend_blocks()
        # The new measurement is approved while the price generator waits.
        # ``approved_complete`` requires the approver and the timestamp beside
        # the status, so the direct write sets what the API would have set.
        approver = holder.scalars(select(User)).first()
        for schedule in holder.scalars(select(UnitAreaSchedule)):
            if schedule.revision_code == "R0":
                schedule.status = "superseded"
            else:
                schedule.status = "approved"
                schedule.approved_by_user_id = approver.id
                schedule.approved_at = datetime.now(UTC)
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the price was calculated without taking the unit lock"
    assert not isinstance(outcome[0], BaseException), outcome[0]
    # 120 sqm at 1,500 plus 20 sqm at 750 — the revised measurement, not the old.
    assert outcome[0] == "195000.00"
    db.expire_all()
    version = db.scalars(select(UnitPriceVersion)).one()
    assert str(version.unit_area_schedule_id) == revised


def test_a_feature_change_committing_first_refuses_the_activation(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    cfo: User,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Given the unit changing during the wait, then the price is not put live.

    The impossible outcome this rules out: a changed unit, a stale price
    accepted as current, and ``pricing_approved`` true — a releasable unit whose
    list price describes something that no longer exists.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    version_id = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    ).json()["id"]
    base = f"{pricing_url(project_id)}/price-versions/{version_id}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(unit_id)).with_for_update())

    def activate(session: Session) -> str:
        version = service.get_price_version(
            session, project_id=uuid.UUID(project_id), version_id=uuid.UUID(version_id)
        )
        service.activate_price_version(
            session,
            project=_project(session, project_id),
            version=version,
            actor=_actor(cfo),
        )
        return "activated"

    thread, outcome = _run(activate)
    try:
        blocked = _wait_until_a_backend_blocks()
        locked = holder.scalars(select(Unit).where(Unit.id == uuid.UUID(unit_id))).one()
        locked.view_class_code = "SEA"
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the activation decided without taking the unit lock"
    assert isinstance(outcome[0], BaseException), outcome[0]
    assert "basis changed" in str(outcome[0])
    db.expire_all()
    unit = db.scalars(select(Unit)).one()
    assert unit.pricing_approved is False
    assert db.scalars(select(UnitPriceVersion)).one().status == "approved"


def test_an_activation_that_wins_the_race_leaves_the_change_to_invalidate_it(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    priced_unit: str,
    db: Session,
) -> None:
    """The other serialisation, and it is also correct.

    The price went live against the unit as it was; the feature change lands
    afterwards and withdraws the approval itself. Both orders end somewhere
    coherent, which is the whole point of serialising them.
    """
    assert db.scalars(select(Unit)).one().pricing_approved is True

    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"view_class_code": "SEA"}
    )

    db.expire_all()
    assert db.scalars(select(Unit)).one().pricing_approved is False
    assert db.scalars(select(UnitPriceVersion)).one().status == "active"


def test_the_lock_order_is_project_then_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    finance: User,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Given a held project lock, then price generation waits before touching the unit.

    Pricing joins the order PR-MVP-02 established and PR-MVP-03 extended —
    project, then hierarchy child, then unit — rather than starting its own. A
    path that took the unit first would deadlock against every path that does
    not.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update())

    def generate(session: Session) -> str:
        unit = session.scalars(select(Unit).where(Unit.id == uuid.UUID(unit_id))).one()
        version = service.generate_price_version(
            session, project=_project(session, project_id), unit=unit, actor=_actor(finance)
        )
        return str(version.id)

    thread, outcome = _run(generate)
    try:
        blocked = _wait_until_a_backend_blocks()
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "price generation did not take the project lock"
    assert not isinstance(outcome[0], BaseException), outcome[0]
    db.expire_all()
    assert db.scalars(select(UnitPriceVersion)).one().status == "draft"
    assert inventory.lock_unit is not None
