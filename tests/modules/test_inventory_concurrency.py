"""Concurrency: the inventory invariants a second writer could otherwise walk past.

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

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.core.errors import ConflictError
from app.modules.access.models import User
from app.modules.inventory import service
from app.modules.inventory.models import (
    Unit,
    UnitAreaSchedule,
    UnitCustomFieldValue,
)
from app.modules.projects.models import Project, UserProjectAccess
from tests.modules.conftest import PROJECTS, inventory_url


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
# Area schedule approval
# --------------------------------------------------------------------------- #


def test_two_area_approvals_cannot_both_become_current(
    admin: User,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Given a held unit lock, then the second approval decides against the first.

    Without the lock both writers read "no approved schedule", both supersede
    nothing, and the unit ends up with two current measurements — which is the
    one thing an area register must never have.
    """
    schedules = f"{inventory_url(project_id)}/units/{unit_id}/area-schedules"
    first, second = (
        admin_client.post(
            schedules,
            json={
                "revision_code": revision,
                "reconciled": True,
                "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": area}],
            },
        ).json()["id"]
        for revision, area in (("R0", "100.0000"), ("R1", "105.0000"))
    )

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(unit_id)).with_for_update())

    def approve_second(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        unit = session.scalars(select(Unit).where(Unit.id == uuid.UUID(unit_id))).one()
        schedule = session.scalars(
            select(UnitAreaSchedule).where(UnitAreaSchedule.id == uuid.UUID(second))
        ).one()
        service.approve_area_schedule(
            session,
            project=project,
            unit=unit,
            schedule=schedule,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
        )
        return "approved"

    thread, outcome = _run(approve_second)
    try:
        blocked = _wait_until_a_backend_blocks()
        # The first approval commits while the second is still waiting.
        locked = holder.scalars(
            select(UnitAreaSchedule).where(UnitAreaSchedule.id == uuid.UUID(first))
        ).one()
        locked.status = "approved"
        locked.approved_by_user_id = admin.id
        locked.approved_at = date.today()
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the second approval ran without taking the unit lock"
    assert not thread.is_alive()
    assert not isinstance(outcome[0], BaseException), outcome[0]

    db.expire_all()
    approved = [
        schedule.revision_code
        for schedule in db.scalars(select(UnitAreaSchedule))
        if schedule.status == "approved"
    ]
    assert approved == ["R1"]
    superseded = [
        schedule.revision_code
        for schedule in db.scalars(select(UnitAreaSchedule))
        if schedule.status == "superseded"
    ]
    assert superseded == ["R0"]


def test_the_database_refuses_a_second_current_schedule(
    admin: User,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Given a direct UPDATE, then the partial index still refuses it.

    The service lock could be removed by a careless refactor; this could not.
    """
    from tests.modules.conftest import approve_areas

    approve_areas(admin_client, project_id, unit_id, area_types)
    schedules = f"{inventory_url(project_id)}/units/{unit_id}/area-schedules"
    second = admin_client.post(
        schedules,
        json={
            "revision_code": "R1",
            "reconciled": True,
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "105.0000"}],
        },
    ).json()["id"]

    row = db.scalars(select(UnitAreaSchedule).where(UnitAreaSchedule.id == uuid.UUID(second))).one()
    row.status = "approved"
    row.approved_by_user_id = admin.id
    row.approved_at = date.today()
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --------------------------------------------------------------------------- #
# Commercial status
# --------------------------------------------------------------------------- #


def test_two_commercial_transitions_cannot_fork_a_units_history(
    admin: User,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Given a held unit lock, then the second writer sees the committed status.

    Both ``held`` and ``available`` are valid exits from ``unreleased``. Without
    the lock each writer reads ``unreleased``, each finds its move legal, and
    both append an event claiming to follow it.
    """
    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(unit_id)).with_for_update())

    def second_writer(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        unit = session.scalars(select(Unit).where(Unit.id == uuid.UUID(unit_id))).one()
        service.transition_commercial_status(
            session,
            project=project,
            unit=unit,
            to_status="held",
            effective_date=date(2026, 2, 2),
            reason="Broker hold",
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
        )
        return "moved"

    thread, outcome = _run(second_writer)
    try:
        blocked = _wait_until_a_backend_blocks()
        locked = holder.scalars(select(Unit).where(Unit.id == uuid.UUID(unit_id))).one()
        locked.commercial_status = "held"
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the transition was judged without taking the unit lock"
    # The first writer already moved it to `held`, so the second must be refused
    # rather than appending a second unreleased -> held event.
    assert isinstance(outcome[0], BaseException), outcome[0]

    db.expire_all()
    assert db.scalars(select(Unit)).one().commercial_status == "held"


# --------------------------------------------------------------------------- #
# Unique custom values
# --------------------------------------------------------------------------- #


def test_two_units_cannot_take_the_same_unique_custom_value(
    admin_client: TestClient, project_id: str, floor_id: str, db: Session
) -> None:
    """Given a unique field, then the database decides between two claimants.

    A read-then-write check would let both writers see "not taken" and both
    commit. The partial index is what actually settles it.
    """
    from tests.modules.conftest import unit_payload

    admin_client.post(
        f"{PROJECTS}/{project_id}/field-definitions",
        json={
            "entity_type": "unit",
            "field_key": "meter_serial",
            "display_label": "Meter serial",
            "data_type": "text",
            "scope_type": "project",
            "project_id": project_id,
            "is_unique": True,
        },
    )
    units = [
        admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number=f"10{index}", unit_reference=f"B1-10{index}"),
        ).json()["id"]
        for index in (1, 2)
    ]

    first = admin_client.put(
        f"{inventory_url(project_id)}/units/{units[0]}/custom-values",
        json={"values": {"meter_serial": "SN-0001"}},
    )
    second = admin_client.put(
        f"{inventory_url(project_id)}/units/{units[1]}/custom-values",
        json={"values": {"meter_serial": "SN-0001"}},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 409
    assert "already used" in second.json()["detail"]
    assert len(db.scalars(select(UnitCustomFieldValue)).all()) == 1


def test_the_unique_index_is_enforced_by_the_database(
    admin_client: TestClient, project_id: str, floor_id: str, db: Session
) -> None:
    """Given a direct INSERT past the service, then PostgreSQL still refuses it."""
    from tests.modules.conftest import unit_payload

    definition = admin_client.post(
        f"{PROJECTS}/{project_id}/field-definitions",
        json={
            "entity_type": "unit",
            "field_key": "meter_serial",
            "display_label": "Meter serial",
            "data_type": "text",
            "scope_type": "project",
            "project_id": project_id,
            "is_unique": True,
        },
    ).json()["id"]
    units = [
        admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number=f"10{index}", unit_reference=f"B1-10{index}"),
        ).json()["id"]
        for index in (1, 2)
    ]
    admin_client.put(
        f"{inventory_url(project_id)}/units/{units[0]}/custom-values",
        json={"values": {"meter_serial": "SN-0001"}},
    )
    admin = db.scalars(select(User)).first()

    db.add(
        UnitCustomFieldValue(
            definition_id=uuid.UUID(definition),
            unit_id=uuid.UUID(units[1]),
            value_json="SN-0001",
            unique_value="sn-0001",
            updated_by_user_id=admin.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --------------------------------------------------------------------------- #
# Phase scope and the assigned manager
# --------------------------------------------------------------------------- #


def test_narrowing_a_scope_cannot_race_a_manager_assignment(
    admin: User, manager: User, admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given a held project lock, then the narrowing sees the committed manager.

    The database must never end up with an assigned project manager who can only
    see half the inventory — each side reading stale state is how it would.
    """
    from tests.modules.conftest import grant_access

    grant_access(admin_client, project_id, manager)

    factory = get_session_factory()
    holder = factory()
    project_row = holder.scalars(
        select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update()
    ).one()

    def narrow_scope(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        service.set_phase_scope(
            session,
            project=project,
            user_id=manager.id,
            phase_scope="selected",
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
        )
        return "narrowed"

    thread, outcome = _run(narrow_scope)
    try:
        blocked = _wait_until_a_backend_blocks()
        # The assignment commits first, while the narrowing waits on the lock.
        project_row.project_manager_user_id = manager.id
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the scope change did not serialise on the project row"
    assert isinstance(outcome[0], ConflictError), outcome[0]

    db.expire_all()
    membership = db.scalars(
        select(UserProjectAccess).where(UserProjectAccess.user_id == manager.id)
    ).one()
    assert membership.phase_scope == "all"


# --------------------------------------------------------------------------- #
# Hierarchy: retiring a parent against creating a child
# --------------------------------------------------------------------------- #


def _child_then_deactivate(
    *,
    project_id: str,
    add_child: Callable[[Session, Project], None],
    deactivate: Callable[[Session, Project], object],
) -> tuple[list[object], bool]:
    """Create a child under a held project lock, then try to retire its parent.

    This is the direction that actually tests the deactivation. The child's own
    creation path takes the project lock already, so racing *it* proves nothing
    about the retirement — the retirement is the side that used to read "no
    active children" from before the child existed and commit anyway.

    The holder inserts the child and keeps the lock. The retirement must block,
    re-read after the commit, and refuse.
    """
    factory = get_session_factory()
    holder = factory()
    project_row = holder.scalars(
        select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update()
    ).one()
    add_child(holder, project_row)
    holder.flush()

    def second(session: Session) -> object:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        return deactivate(session, project)

    thread, outcome = _run(second)
    try:
        blocked = _wait_until_a_backend_blocks()
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)
    return outcome, blocked


def test_retiring_a_phase_cannot_race_a_new_building(
    admin: User, project_id: str, phase_id: str, db: Session
) -> None:
    """Given a building committing, then the phase retirement must see it.

    Without the lock both transactions are right about what they read: the
    retirement sees no buildings, the creation sees an active phase. They commit
    into a register saying the phase is closed and its building is open.
    """
    from app.modules.inventory.models import Building, Phase

    def add_child(session: Session, project: Project) -> None:
        session.add(
            Building(
                project_id=project.id,
                phase_id=uuid.UUID(phase_id),
                code="B9",
                name="Late Tower",
                created_by_user_id=admin.id,
            )
        )

    def deactivate(session: Session, project: Project) -> object:
        phase = session.scalars(select(Phase).where(Phase.id == uuid.UUID(phase_id))).one()
        return service.update_phase(
            session,
            phase=phase,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            is_active=False,
        )

    outcome, blocked = _child_then_deactivate(
        project_id=project_id, add_child=add_child, deactivate=deactivate
    )

    assert blocked, "the phase retirement did not serialise on the project row"
    assert isinstance(outcome[0], ConflictError), outcome[0]
    db.expire_all()
    phase = db.scalars(select(Phase).where(Phase.id == uuid.UUID(phase_id))).one()
    building = db.scalars(select(Building).where(Building.code == "B9")).one()
    assert not (phase.is_active is False and building.is_active is True)
    assert phase.is_active is True


def test_retiring_a_building_cannot_race_a_new_floor(
    admin: User, project_id: str, building_id: str, db: Session
) -> None:
    from app.modules.inventory.models import Building, Floor

    def add_child(session: Session, project: Project) -> None:
        session.add(
            Floor(
                project_id=project.id,
                building_id=uuid.UUID(building_id),
                code="09",
                label="Late floor",
                created_by_user_id=admin.id,
            )
        )

    def deactivate(session: Session, project: Project) -> object:
        building = session.scalars(
            select(Building).where(Building.id == uuid.UUID(building_id))
        ).one()
        return service.update_building(
            session,
            building=building,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            is_active=False,
        )

    outcome, blocked = _child_then_deactivate(
        project_id=project_id, add_child=add_child, deactivate=deactivate
    )

    assert blocked, "the building retirement did not serialise on the project row"
    assert isinstance(outcome[0], ConflictError), outcome[0]
    db.expire_all()
    building = db.scalars(select(Building).where(Building.id == uuid.UUID(building_id))).one()
    floor = db.scalars(select(Floor).where(Floor.code == "09")).one()
    assert not (building.is_active is False and floor.is_active is True)
    assert building.is_active is True


def test_retiring_a_floor_cannot_race_a_new_unit(
    admin: User, project_id: str, floor_id: str, db: Session
) -> None:
    from app.modules.inventory.models import Floor

    def add_child(session: Session, project: Project) -> None:
        session.add(
            Unit(
                project_id=project.id,
                floor_id=uuid.UUID(floor_id),
                unit_number="909",
                unit_reference="B1-909",
                asset_class="apartment",
                created_by_user_id=admin.id,
            )
        )

    def deactivate(session: Session, project: Project) -> object:
        floor = session.scalars(select(Floor).where(Floor.id == uuid.UUID(floor_id))).one()
        return service.update_floor(
            session,
            floor=floor,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            is_active=False,
        )

    outcome, blocked = _child_then_deactivate(
        project_id=project_id, add_child=add_child, deactivate=deactivate
    )

    assert blocked, "the floor retirement did not serialise on the project row"
    assert isinstance(outcome[0], ConflictError), outcome[0]
    db.expire_all()
    floor = db.scalars(select(Floor).where(Floor.id == uuid.UUID(floor_id))).one()
    unit = db.scalars(select(Unit).where(Unit.unit_reference == "B1-909")).one()
    assert not (floor.is_active is False and unit.is_active is True)
    assert floor.is_active is True


def test_creating_a_building_re_reads_the_phase_it_waited_for(
    admin: User, project_id: str, phase_id: str, db: Session
) -> None:
    """The other direction, and the reason the lock is not enough on its own.

    The route loads the phase, then the service waits for the project lock. By
    the time the wait ends the phase may have been retired by whoever held it —
    but the object in memory still says active. Deciding from that copy creates
    a building under a closed phase, with the lock dutifully held throughout.
    """
    from app.modules.inventory.models import Building, Phase

    factory = get_session_factory()
    holder = factory()
    holder.scalars(
        select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update()
    ).one()

    def create_late(session: Session) -> object:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        # Loaded before the lock is available, exactly as the route does.
        phase = session.scalars(select(Phase).where(Phase.id == uuid.UUID(phase_id))).one()
        assert phase.is_active is True
        return service.create_building(
            session,
            project=project,
            phase=phase,
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
            code="B9",
            name="Late Tower",
        )

    thread, outcome = _run(create_late)
    try:
        blocked = _wait_until_a_backend_blocks()
        retired = holder.scalars(select(Phase).where(Phase.id == uuid.UUID(phase_id))).one()
        retired.is_active = False
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "building creation did not serialise on the project row"
    assert isinstance(outcome[0], ConflictError), outcome[0]
    db.expire_all()
    assert db.scalars(select(Building).where(Building.code == "B9")).all() == []


def test_assigning_a_manager_cannot_race_a_scope_narrowing(
    admin: User, manager: User, project_id: str, db: Session
) -> None:
    """The mirror of the existing race, run the other way round.

    The narrowing commits first; the assignment must then widen the membership
    it finds rather than leaving a formal project manager who sees one phase.
    """
    from app.modules.projects import service as projects_service

    admin_access = db.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
    assert admin_access is not None

    factory = get_session_factory()
    holder = factory()
    project_row = holder.scalars(
        select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update()
    ).one()

    def assign(session: Session) -> str:
        project = session.scalars(select(Project).where(Project.id == uuid.UUID(project_id))).one()
        projects_service.update_project(
            session,
            project=project,
            actor_user_id=admin.id,
            actor_is_system_admin=True,
            correlation_id=uuid.uuid4(),
            project_manager_user_id=manager.id,
        )
        return "assigned"

    # The manager is a member first, narrowed to selected phases.
    holder.add(
        UserProjectAccess(
            project_id=project_row.id,
            user_id=manager.id,
            is_active=True,
            phase_scope="selected",
            granted_by_user_id=admin.id,
        )
    )
    holder.flush()

    thread, outcome = _run(assign)
    try:
        blocked = _wait_until_a_backend_blocks()
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the assignment did not serialise on the project row"
    assert outcome[0] == "assigned", outcome[0]

    db.expire_all()
    membership = db.scalars(
        select(UserProjectAccess).where(UserProjectAccess.user_id == manager.id)
    ).one()
    assert membership.phase_scope == "all"
