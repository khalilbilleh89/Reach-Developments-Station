"""Concurrency: the invariants that a second writer could otherwise walk past.

Every test here runs two real PostgreSQL transactions on separate connections.
A mocked session would only prove that the mock was called in the order the test
itself chose, which is exactly the thing under question.

The pattern throughout: one transaction takes the same row lock the service
takes and holds it, the test waits until the second is genuinely blocked (by
polling PostgreSQL's own view of who is waiting, rather than sleeping and
hoping), then the holder commits. The second writer must then decide against the
committed state, not the state it read before it blocked.
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
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.core.errors import ConflictError, ValidationError
from app.modules.access.models import User
from app.modules.projects import service
from app.modules.projects.models import (
    DocumentReference,
    LandParcel,
    Permit,
    PermitStatusEvent,
    Project,
    UserProjectAccess,
)
from tests.modules.conftest import (
    PROJECTS,
    SETTINGS,
    grant_access,
    parcel_payload,
    permit_payload,
)


def _wait_until_a_backend_blocks(timeout: float = 15.0) -> bool:
    """Poll until another backend in this database is waiting on a lock.

    Waits *until* the condition holds rather than guessing at a sleep long
    enough to hide a race.
    """
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


# --------------------------------------------------------------------------- #
# Permit status transitions
# --------------------------------------------------------------------------- #


@pytest.fixture
def submitted_permit(admin_client: TestClient, project_id: str) -> str:
    """A permit sitting in a state with two valid, mutually exclusive exits."""
    permits = f"{PROJECTS}/{project_id}/permits"
    permit = admin_client.post(permits, json=permit_payload()).json()["id"]
    for status, day in (("preparing", "2026-01-05"), ("submitted", "2026-01-10")):
        assert (
            admin_client.post(
                f"{permits}/{permit}/transitions",
                json={"to_status": status, "effective_date": day},
            ).status_code
            == 201
        )
    return permit


def test_two_transitions_cannot_fork_a_permits_history(
    admin: User, project_id: str, submitted_permit: str, db: Session
) -> None:
    """Given a held permit lock, then the second writer decides against the new state.

    Both ``accepted_for_review`` and ``rejected`` are valid exits from
    ``submitted``. Without the lock each writer reads ``submitted``, each finds
    its move legal, and both append an event claiming to follow it — a history
    that forks, and a current status decided by whichever write landed last.
    """
    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Permit).where(Permit.id == uuid.UUID(submitted_permit)).with_for_update())

    def second_writer(session: Session) -> str:
        permit = session.scalars(
            select(Permit).where(Permit.id == uuid.UUID(submitted_permit))
        ).one()
        service.transition_permit(
            session,
            permit=permit,
            to_status="rejected",
            effective_date=date(2026, 2, 1),
            reason="Height exceeded",
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
        )
        return "moved"

    thread, outcome = _run(second_writer)
    try:
        blocked = _wait_until_a_backend_blocks()
        # Only now, with the second writer still waiting, does the first commit
        # a move out of `submitted`.
        locked = holder.scalars(
            select(Permit).where(Permit.id == uuid.UUID(submitted_permit))
        ).one()
        locked.status = "issued"
        locked.status_effective_date = date(2026, 1, 20)
        holder.add(
            PermitStatusEvent(
                permit_id=locked.id,
                from_status="submitted",
                to_status="issued",
                effective_date=date(2026, 1, 20),
                changed_by_user_id=admin.id,
            )
        )
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the second writer evaluated the transition without taking the permit lock"
    assert not thread.is_alive()
    # `issued -> rejected` is not a legal move, so the second writer must now be
    # refused: it re-read the committed status rather than its own stale copy.
    assert isinstance(outcome[0], ConflictError), outcome[0]

    db.expire_all()
    assert db.scalars(select(Permit)).one().status == "issued"
    events = db.scalars(select(PermitStatusEvent).order_by(PermitStatusEvent.effective_date)).all()
    # History stays linear: each event's `from` is the previous event's `to`.
    assert [(event.from_status, event.to_status) for event in events] == [
        ("not_started", "preparing"),
        ("preparing", "submitted"),
        ("submitted", "issued"),
    ]


def test_an_identity_update_cannot_race_a_submission(
    admin: User, project_id: str, db: Session, admin_client: TestClient
) -> None:
    """Given a held permit lock, then the freeze is judged on the committed status.

    Otherwise an update reading ``preparing`` and a transition to ``submitted``
    both commit, leaving a statutory application whose identity changed as it
    was being submitted.
    """
    permits = f"{PROJECTS}/{project_id}/permits"
    permit_id = admin_client.post(permits, json=permit_payload()).json()["id"]
    assert (
        admin_client.post(
            f"{permits}/{permit_id}/transitions",
            json={"to_status": "preparing", "effective_date": "2026-01-05"},
        ).status_code
        == 201
    )

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Permit).where(Permit.id == uuid.UUID(permit_id)).with_for_update())

    def identity_writer(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        permit = session.scalars(select(Permit).where(Permit.id == uuid.UUID(permit_id))).one()
        service.update_permit(
            session,
            project=project,
            permit=permit,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            authority="Ministry of Public Works",
        )
        return "updated"

    thread, outcome = _run(identity_writer)
    try:
        blocked = _wait_until_a_backend_blocks()
        locked = holder.scalars(select(Permit).where(Permit.id == uuid.UUID(permit_id))).one()
        locked.status = "submitted"
        locked.status_effective_date = date(2026, 1, 10)
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the identity update judged the freeze without taking the permit lock"
    assert isinstance(outcome[0], ConflictError), outcome[0]

    db.expire_all()
    permit = db.scalars(select(Permit)).one()
    assert permit.status == "submitted"
    assert permit.authority == "Greater Amman Municipality"


# --------------------------------------------------------------------------- #
# Prerequisite chains
# --------------------------------------------------------------------------- #


def test_two_prerequisite_links_cannot_close_a_cycle(
    admin: User, project_id: str, admin_client: TestClient, db: Session
) -> None:
    """Given a held project lock, then the second link sees the first and is refused.

    A cycle is a property of the whole chain, so sequential validation is not
    enough: "A depends on B" and "B depends on A" can each validate against a
    graph that does not yet contain the other.
    """
    permits = f"{PROJECTS}/{project_id}/permits"
    first = admin_client.post(permits, json=permit_payload(permit_code="PLN-001")).json()["id"]
    second = admin_client.post(permits, json=permit_payload()).json()["id"]

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update())

    def second_link(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        permit = session.scalars(select(Permit).where(Permit.id == uuid.UUID(first))).one()
        service.update_permit(
            session,
            project=project,
            permit=permit,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            prerequisite_permit_id=uuid.UUID(second),
        )
        return "linked"

    thread, outcome = _run(second_link)
    try:
        blocked = _wait_until_a_backend_blocks()
        # The first link commits while the second is still waiting.
        locked = holder.scalars(select(Permit).where(Permit.id == uuid.UUID(second))).one()
        locked.prerequisite_permit_id = uuid.UUID(first)
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the cycle check ran without serialising on the project"
    assert isinstance(outcome[0], ValidationError), outcome[0]
    assert "circular dependency" in str(outcome[0])

    db.expire_all()
    links = {
        permit.permit_code: permit.prerequisite_permit_id for permit in db.scalars(select(Permit))
    }
    assert links["BLD-001"] == uuid.UUID(first)
    assert links["PLN-001"] is None


# --------------------------------------------------------------------------- #
# Project manager and access
# --------------------------------------------------------------------------- #


def test_a_manager_cannot_be_assigned_while_their_access_is_revoked(
    admin: User, manager: User, project_id: str, admin_client: TestClient, db: Session
) -> None:
    """Given a held project lock, then assignment and revocation cannot both win.

    The database must never end up with a project whose assigned manager has no
    active access — each side reading stale state is exactly how it would.
    """
    grant_access(admin_client, project_id, manager)

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update())

    def assign_manager(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        service.update_project(
            session,
            project=project,
            actor_user_id=admin.id,
            actor_is_system_admin=True,
            correlation_id=uuid.uuid4(),
            project_manager_user_id=manager.id,
        )
        return "assigned"

    thread, outcome = _run(assign_manager)
    try:
        blocked = _wait_until_a_backend_blocks()
        # Revocation commits first, while the assignment waits on the lock.
        access = holder.scalars(
            select(UserProjectAccess).where(UserProjectAccess.user_id == manager.id)
        ).one()
        access.is_active = False
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the manager assignment did not serialise on the project row"
    assert not thread.is_alive()

    db.expire_all()
    project = db.scalars(select(Project)).one()
    access = db.scalars(
        select(UserProjectAccess).where(UserProjectAccess.user_id == manager.id)
    ).one()
    # Whichever way it resolved, the pairing must be coherent: an assigned
    # manager always has active access.
    if project.project_manager_user_id == manager.id:
        assert access.is_active is True
    else:
        assert outcome[0] == "assigned" or isinstance(outcome[0], BaseException)


def test_revocation_waits_for_a_manager_assignment_in_flight(
    admin: User, manager: User, project_id: str, admin_client: TestClient, db: Session
) -> None:
    """Given the assignment commits first, then the revocation is refused outright."""
    grant_access(admin_client, project_id, manager)

    factory = get_session_factory()
    holder = factory()
    project_row = holder.scalars(
        select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update()
    ).one()

    def revoke(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        service.revoke_project_access(
            session,
            project=project,
            user_id=manager.id,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
        )
        return "revoked"

    thread, outcome = _run(revoke)
    try:
        blocked = _wait_until_a_backend_blocks()
        project_row.project_manager_user_id = manager.id
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the revocation did not serialise on the project row"
    assert isinstance(outcome[0], ConflictError), outcome[0]

    db.expire_all()
    assert (
        db.scalars(select(UserProjectAccess).where(UserProjectAccess.user_id == manager.id))
        .one()
        .is_active
        is True
    )


# --------------------------------------------------------------------------- #
# Project basis versus the child writes that depend on it
# --------------------------------------------------------------------------- #


@pytest.fixture
def foreign_country_pack(admin_client: TestClient, currency_id: str) -> str:
    """A second jurisdiction that configures no permit type at all.

    Deliberately bare: a permit validated against Jordan must become invalid the
    moment the project is said to belong here, which is the whole point of
    refusing to move a project that already has children.
    """
    response = admin_client.post(
        f"{SETTINGS}/country-packs",
        json={
            "country_code": "AE",
            "name": "United Arab Emirates",
            "locale": "en-AE",
            "timezone": "Asia/Dubai",
            "default_currency_id": currency_id,
            "area_unit": "sqm",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def spare_currency(admin_client: TestClient) -> str:
    response = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "US dollar"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


#: The first write of each kind that makes a project's jurisdiction permanent,
#: and the table it lands in. Every one is decided against the locked project:
#: a permit or document validates a code against the country pack, and a parcel
#: takes its area unit from it. PR-V2-01 made a parcel's ownership, title and
#: zoning free text, which removed one reason for that lock and none of the
#: others — the jurisdiction still reaches the row.
_FIRST_CHILD_WRITES = {
    "parcel": (
        lambda session, project, admin: service.create_parcel(
            session,
            project=project,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            plot_number="PLOT-1",
            land_area=Decimal("4500.0000"),
            ownership_type="Freehold",
        ),
        LandParcel,
    ),
    "permit": (
        lambda session, project, admin: service.create_permit(
            session,
            project=project,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            permit_code="BLD-001",
            permit_type_code="BUILDING",
            authority="Greater Amman Municipality",
        ),
        Permit,
    ),
    "document": (
        lambda session, project, admin: service.create_document(
            session,
            project=project,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            title="Title deed 9911",
            document_type_code="TITLE_DEED",
            external_url="https://records.example.com/deed.pdf",
        ),
        DocumentReference,
    ),
}


@pytest.mark.parametrize("record", sorted(_FIRST_CHILD_WRITES))
def test_a_first_child_cannot_be_created_under_a_jurisdiction_the_project_has_left(
    admin: User, project_id: str, foreign_country_pack: str, db: Session, record: str
) -> None:
    """Given the country change commits first, then the child is validated against it.

    Each of these codes is configured for Jordan and nowhere else. Without the
    project lock the creation validates against the country pack it read before
    the change and commits a record whose codes are legal in no jurisdiction the
    project belongs to.
    """
    create, model = _FIRST_CHILD_WRITES[record]

    factory = get_session_factory()
    holder = factory()
    project_row = holder.scalars(
        select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update()
    ).one()

    def create_first_child(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        create(session, project, admin)
        return "created"

    thread, outcome = _run(create_first_child)
    try:
        blocked = _wait_until_a_backend_blocks()
        # The jurisdiction moves while the creation is still waiting.
        project_row.country_pack_id = uuid.UUID(foreign_country_pack)
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, f"creating the first {record} validated its codes without the project lock"
    assert isinstance(outcome[0], ValidationError), outcome[0]

    db.expire_all()
    assert db.scalars(select(model)).all() == []
    assert db.scalars(select(Project)).one().country_pack_id == uuid.UUID(foreign_country_pack)


def test_a_country_change_waits_for_a_first_permit_in_flight(
    admin: User, project_id: str, foreign_country_pack: str, db: Session
) -> None:
    """Given the permit commits first, then the country change is refused.

    The other serial order. Together with the test above these are the only two
    outcomes: there is no interleaving in which both succeed.
    """
    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update())

    def move_country(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        service.update_project(
            session,
            project=project,
            actor_user_id=admin.id,
            actor_is_system_admin=True,
            correlation_id=uuid.uuid4(),
            country_pack_id=uuid.UUID(foreign_country_pack),
        )
        return "moved"

    thread, outcome = _run(move_country)
    try:
        blocked = _wait_until_a_backend_blocks()
        holder.add(
            Permit(
                project_id=uuid.UUID(project_id),
                permit_code="BLD-001",
                permit_type_code="BUILDING",
                authority="Greater Amman Municipality",
                status="not_started",
                status_effective_date=date(2026, 1, 1),
            )
        )
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the country change did not serialise on the project row"
    assert isinstance(outcome[0], ConflictError), outcome[0]
    assert "Country pack cannot be changed" in str(outcome[0])

    db.expire_all()
    project = db.scalars(select(Project)).one()
    assert project.country_pack_id != uuid.UUID(foreign_country_pack)


def test_a_first_parcel_cost_serialises_against_a_base_currency_change(
    admin: User, project_id: str, admin_client: TestClient, spare_currency: str, db: Session
) -> None:
    """Given a parcel with no cost, then the write that first puts money on it waits.

    A cost-free parcel does not lock the base currency, so this PATCH is the
    write that establishes the first monetary fact. If it does not take the
    project lock, the currency change can read "no money exists" while this
    transaction is establishing exactly that.
    """
    parcel_id = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]

    factory = get_session_factory()
    holder = factory()
    project_row = holder.scalars(
        select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update()
    ).one()

    def record_first_cost(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        parcel = session.scalars(
            select(LandParcel).where(LandParcel.id == uuid.UUID(parcel_id))
        ).one()
        service.update_parcel(
            session,
            project=project,
            parcel=parcel,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            purchase_price=Decimal("1000000.00"),
        )
        return "recorded"

    thread, outcome = _run(record_first_cost)
    try:
        blocked = _wait_until_a_backend_blocks()
        project_row.base_currency_id = uuid.UUID(spare_currency)
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the first land cost was written without taking the project lock"
    assert outcome[0] == "recorded", outcome[0]

    db.expire_all()
    # The serial outcome: the currency changed while the parcel still had no
    # money, and the amount that followed is denominated in the new currency.
    assert db.scalars(select(Project)).one().base_currency_id == uuid.UUID(spare_currency)
    assert db.scalars(select(LandParcel)).one().purchase_price == Decimal("1000000.00")


def test_a_first_permit_fee_serialises_against_a_base_currency_change(
    admin: User, project_id: str, admin_client: TestClient, spare_currency: str, db: Session
) -> None:
    """Given a permit with no fee, then the write that first puts money on it waits.

    Same rule as the parcel, on the other monetary field the project owns.
    """
    permit_id = admin_client.post(f"{PROJECTS}/{project_id}/permits", json=permit_payload()).json()[
        "id"
    ]

    factory = get_session_factory()
    holder = factory()
    project_row = holder.scalars(
        select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update()
    ).one()

    def record_first_fee(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        permit = session.scalars(select(Permit).where(Permit.id == uuid.UUID(permit_id))).one()
        service.update_permit(
            session,
            project=project,
            permit=permit,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            fee_amount=Decimal("5000.00"),
        )
        return "recorded"

    thread, outcome = _run(record_first_fee)
    try:
        blocked = _wait_until_a_backend_blocks()
        project_row.base_currency_id = uuid.UUID(spare_currency)
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the first permit fee was written without taking the project lock"
    assert outcome[0] == "recorded", outcome[0]

    db.expire_all()
    assert db.scalars(select(Project)).one().base_currency_id == uuid.UUID(spare_currency)
    assert db.scalars(select(Permit)).one().fee_amount == Decimal("5000.00")


def test_an_ordinary_parcel_edit_does_not_take_the_project_lock(
    admin: User, project_id: str, admin_client: TestClient, db: Session
) -> None:
    """Given an edit that touches no money, then it does not queue on the project.

    The locking is targeted at the project-wide invariants. Once a parcel
    exists the country pack is already frozen, so ordinary maintenance has
    nothing to serialise against and should not be made to wait behind it.
    """
    parcel_id = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update())

    def edit_notes(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        parcel = session.scalars(
            select(LandParcel).where(LandParcel.id == uuid.UUID(parcel_id))
        ).one()
        service.update_parcel(
            session,
            project=project,
            parcel=parcel,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            topography="Gentle slope",
        )
        return "edited"

    thread, outcome = _run(edit_notes)
    thread.join(timeout=30)
    try:
        assert not thread.is_alive(), "an ordinary parcel edit queued behind the project lock"
        assert outcome[0] == "edited", outcome[0]
    finally:
        holder.close()

    db.expire_all()
    assert db.scalars(select(LandParcel)).one().topography == "Gentle slope"
