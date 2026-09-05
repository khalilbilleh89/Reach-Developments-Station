"""A batch is applied once, and a batch that never landed can be retried.

Those two sentences are in tension and both have to hold. The first is why a
claim exists at all: an operator whose connection dropped mid-apply will run the
command again, and without a record the second run duplicates everything the
first committed. The second is why the claim may not be written in a transaction
of its own: a claim that committed ahead of its data would refuse the retry of a
batch that never landed, which is the same accident wearing the opposite mask.

The race at the end is the reason for the lock. Two operators starting one batch
at the same moment both read "not applied" and both proceed, and no unique index
saves them — ``audit_events.correlation_id`` groups events, so many rows share
one value by design and a constraint there would break the audit trail to fix
the cutover. The lock is the project row, through the contract the rest of this
repository already uses. The harness mirrors the concurrency files in
inventory, pricing, sales, payment plans, collections, unit economics,
construction and cashflow; it is copied rather than shared because a test file
that cannot be read on its own is a test file nobody reads.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.modules.access.models import User
from app.modules.audit.models import AUDIT_SOURCE_API, AUDIT_SOURCE_BOOTSTRAP, AuditEvent
from app.modules.projects.models import Project
from scripts.migration import CONTRACT_VERSION
from scripts.migration.batch import (
    AUDIT_SOURCE_CUTOVER,
    BATCH_APPLIED,
    BATCH_ENTITY_TYPE,
    BatchAlreadyApplied,
    SessionNotClean,
    UnknownProject,
    applying,
    claim,
    claim_of,
    describe,
)
from scripts.migration.manifest import Manifest, SourceFile

PROJECT_CODE = "GALINI-BLU"

#: A hash that is obviously not a real one and still the right shape, so a test
#: reading it cannot mistake it for evidence of anything.
UNITS_SHA = "ab" * 32
CLIENTS_SHA = "cd" * 32


def manifest(**overrides: object) -> Manifest:
    """One sealed batch, declared. Constructed rather than parsed on purpose.

    ``test_cutover_manifest.py`` owns whether the parser is right. What matters
    here is what a claim does with a manifest that is already valid.
    """
    fields: dict[str, object] = {
        "batch_id": uuid.uuid4(),
        "project_code": PROJECT_CODE,
        "source_system": "Legacy sales workbook",
        "extracted_at": datetime(2026, 9, 5, 6, 0, tzinfo=UTC),
        "cutover_date": date(2026, 9, 30),
        "expected_currencies": ("AED",),
        "operator": "A. Operator",
        "reason": "cutover trial",
        "contract_version": CONTRACT_VERSION,
        "files": (
            SourceFile(name="units.csv", sha256=UNITS_SHA, bytes=120),
            SourceFile(name="clients.csv", sha256=CLIENTS_SHA, bytes=64),
        ),
    }
    fields.update(overrides)
    return Manifest(**fields)  # type: ignore[arg-type]


def claims(session: Session, batch_id: uuid.UUID) -> int:
    return session.scalars(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.correlation_id == batch_id, AuditEvent.action == BATCH_APPLIED)
    ).one()


# --------------------------------------------------------------------------- #
# What a claim records
# --------------------------------------------------------------------------- #


def test_a_claim_names_the_batch_as_both_its_subject_and_its_correlation(
    db: Session, admin: User, project_id: str
) -> None:
    """One id, in both columns, because a batch is one operation and one thing.

    ``correlation_id`` is what the duplicate check reads; ``entity_id`` is what
    somebody browsing the audit trail searches. Splitting them would mean a
    batch findable two ways that could disagree.
    """
    declared = manifest()
    event = claim(db, declared, actor_user_id=admin.id)
    db.commit()

    assert event.action == BATCH_APPLIED
    assert event.entity_type == BATCH_ENTITY_TYPE
    assert event.entity_id == declared.batch_id
    assert event.correlation_id == declared.batch_id
    assert event.actor_user_id == admin.id
    assert event.reason == declared.reason


def test_a_cutover_row_can_never_be_mistaken_for_a_native_action(
    db: Session, admin: User, project_id: str
) -> None:
    """The whole provenance argument, at the level of one column.

    An imported batch that recorded itself as ``api`` would be indistinguishable
    from somebody having done the work through the application, which is the
    fabricated-audit-trail failure the intake contract forbids.
    """
    event = claim(db, manifest(), actor_user_id=admin.id)
    db.commit()

    assert event.source == AUDIT_SOURCE_CUTOVER
    assert event.source not in {AUDIT_SOURCE_API, AUDIT_SOURCE_BOOTSTRAP}


def test_the_claim_carries_the_hashes_that_prove_which_bytes_were_applied(
    db: Session, admin: User, project_id: str
) -> None:
    """The bundle is gone in six months; this is what is left of it.

    There is a live trap here. ``snapshot`` redacts any key containing "hash",
    fail-closed and recursively, so filing these under ``file_hashes`` would
    store ``[redacted]`` and the evidence would be silently absent — present in
    shape, empty in substance, which is worse than missing. ``sha256`` is the
    field name and this asserts the values survive.
    """
    declared = manifest()
    event = claim(db, declared, actor_user_id=admin.id)
    db.commit()

    recorded = {entry["name"]: entry["sha256"] for entry in event.after_data["files"]}
    assert recorded == {"units.csv": UNITS_SHA, "clients.csv": CLIENTS_SHA}


def test_the_claim_carries_nothing_that_came_from_the_source(
    db: Session, admin: User, project_id: str
) -> None:
    """A closed set, asserted as closed.

    Every field recorded is from the operator's own declaration. Nothing here
    passes through source rows, so no buyer name, identifier or amount can reach
    the audit trail by this path — and a field added later has to be added to
    this assertion, where somebody has to look at it.
    """
    assert set(describe(manifest())) == {
        "batch_id",
        "project_code",
        "source_system",
        "extracted_at",
        "cutover_date",
        "expected_currencies",
        "operator",
        "contract_version",
        "adapter_version",
        "files",
    }


# --------------------------------------------------------------------------- #
# Applied once
# --------------------------------------------------------------------------- #


def test_a_second_claim_on_the_same_batch_is_refused(
    db: Session, admin: User, project_id: str
) -> None:
    """And the refusal says when the first one happened, because that is the
    first thing anybody asks."""
    declared = manifest()
    first = claim(db, declared, actor_user_id=admin.id)
    db.commit()

    with pytest.raises(BatchAlreadyApplied) as raised:
        claim(db, declared, actor_user_id=admin.id)

    assert raised.value.batch_id == declared.batch_id
    assert raised.value.claim.id == first.id
    assert first.occurred_at.isoformat() in str(raised.value)
    assert claims(db, declared.batch_id) == 1


def test_a_rolled_back_claim_leaves_nothing_to_refuse_the_retry(
    db: Session, admin: User, project_id: str
) -> None:
    """The other half, and the reason ``claim`` does not commit.

    A batch that failed half way through and rolled back did not land. If its
    claim had committed separately, the retry — the correct next action — would
    be refused by a record of something that never happened, and the operator
    would have no way forward that did not involve editing the audit trail.
    """
    declared = manifest()
    claim(db, declared, actor_user_id=admin.id)
    db.rollback()

    assert claim_of(db, declared.batch_id) is None
    retried = claim(db, declared, actor_user_id=admin.id)
    db.commit()
    assert retried.correlation_id == declared.batch_id
    assert claims(db, declared.batch_id) == 1


def test_a_batch_that_never_ran_has_no_claim(db: Session, project_id: str) -> None:
    """The read the target-side preflight makes, and it must not write."""
    before = db.scalars(select(func.count()).select_from(AuditEvent)).one()
    assert claim_of(db, uuid.uuid4()) is None
    assert db.scalars(select(func.count()).select_from(AuditEvent)).one() == before


def test_two_batches_do_not_share_one_claim(db: Session, admin: User, project_id: str) -> None:
    """Two extracts of one project are two batches. Refusing the second would be
    as wrong as accepting a repeat of the first."""
    first, second = manifest(), manifest()
    assert first.batch_id != second.batch_id
    claim(db, first, actor_user_id=admin.id)
    claim(db, second, actor_user_id=admin.id)
    db.commit()
    assert claims(db, first.batch_id) == 1
    assert claims(db, second.batch_id) == 1


# --------------------------------------------------------------------------- #
# The project is resolved, never created
# --------------------------------------------------------------------------- #


def test_an_unknown_project_is_refused_and_not_created(
    db: Session, admin: User, project_id: str
) -> None:
    """A cutover that can bring a project into existence can bring the wrong one."""
    before = db.scalars(select(func.count()).select_from(Project)).one()

    with pytest.raises(UnknownProject, match="NO-SUCH-PROJECT"):
        claim(db, manifest(project_code="NO-SUCH-PROJECT"), actor_user_id=admin.id)
    db.rollback()

    assert db.scalars(select(func.count()).select_from(Project)).one() == before


# --------------------------------------------------------------------------- #
# The race the lock exists for
# --------------------------------------------------------------------------- #


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


def test_two_operators_racing_one_batch_leave_a_single_claim(
    db: Session, admin: User, project_id: str
) -> None:
    """Real PostgreSQL transactions on separate connections, not a mocked order.

    A mock would only prove the lock was called where the test chose to call it,
    which is exactly the thing in question. Without ``lock_project`` both
    sessions read no claim, both record one, and the batch applies twice.
    """
    declared = manifest()
    actor_id = admin.id
    ready = threading.Event()
    release = threading.Event()

    def holder(session: Session) -> object:
        event = claim(session, declared, actor_user_id=actor_id)
        ready.set()
        assert release.wait(timeout=15)
        session.commit()
        return event.id

    def contender(session: Session) -> object:
        recorded = claim(session, declared, actor_user_id=actor_id)
        session.commit()
        return recorded.id

    first_thread, first = _run(holder)
    assert ready.wait(timeout=15), "the first operator never reached the lock"

    second_thread, second = _run(contender)
    assert _wait_until_a_backend_blocks(), "the second operator never blocked on the lock"

    release.set()
    first_thread.join(timeout=20)
    second_thread.join(timeout=20)

    assert not isinstance(first[0], BaseException), first[0]
    assert isinstance(second[0], BatchAlreadyApplied), second[0]
    assert claims(db, declared.batch_id) == 1


# --------------------------------------------------------------------------- #
# One transaction, or none of it
# --------------------------------------------------------------------------- #


def written_by(session: Session, batch_id: uuid.UUID) -> int:
    """Everything recorded under this batch's correlation id, claim included."""
    return session.scalars(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.correlation_id == batch_id)
    ).one()


def _stand_in_write(session: Session, declared: Manifest, actor_id: uuid.UUID) -> None:
    """A row the batch writes, standing in for domain data ``apply`` will write.

    An audit row rather than a sale contract because the point under test is the
    transaction boundary, and a contract would need the whole pricing chain to
    exist first. What matters is that it is a real INSERT in the same session.
    """
    from app.modules.audit.service import record_event

    record_event(
        session,
        action="cutover.row_imported",
        entity_type="cutover_row",
        entity_id=declared.batch_id,
        correlation_id=declared.batch_id,
        actor_user_id=actor_id,
        source=AUDIT_SOURCE_CUTOVER,
    )


def _durable(batch_id: uuid.UUID) -> int:
    """What a *different* connection can see, which is what committed means.

    Reading through the session under test cannot tell a commit from a flush:
    both make rows visible inside that session's own transaction. A mutation
    replacing ``session.commit()`` with ``session.flush()`` passed every test
    here until this existed — the fourth guard on this branch to be caught
    observing a thing through itself.
    """
    from app.core.database import get_session_factory

    other = get_session_factory()()
    try:
        return other.scalars(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.correlation_id == batch_id)
        ).one()
    finally:
        other.rollback()
        other.close()


def test_a_successful_batch_commits_the_claim_and_its_rows_together(
    db: Session, admin: User, project_id: str
) -> None:
    """Durable, not merely flushed — asserted from outside the transaction."""
    declared = manifest()
    with applying(db, declared, actor_user_id=admin.id) as record:
        assert record.correlation_id == declared.batch_id
        _stand_in_write(db, declared, admin.id)
        _stand_in_write(db, declared, admin.id)
        assert _durable(declared.batch_id) == 0, "nothing escapes before the commit"

    assert written_by(db, declared.batch_id) == 3, "the claim and both rows"
    assert claims(db, declared.batch_id) == 1
    assert _durable(declared.batch_id) == 3, "and another connection can see all three"


def test_a_failure_after_several_writes_leaves_nothing_behind(
    db: Session, admin: User, project_id: str
) -> None:
    """The forced late failure, which is the only interesting kind.

    A batch that fails on its first row is easy. The one that costs a night
    fails on row nine hundred, having already written eight hundred and
    ninety-nine — and the claim. Either all of that is durable or none of it is;
    a partially applied batch is the state nobody can reason about.
    """
    declared = manifest()

    class Deliberate(RuntimeError):
        pass

    with pytest.raises(Deliberate), applying(db, declared, actor_user_id=admin.id):
        _stand_in_write(db, declared, admin.id)
        _stand_in_write(db, declared, admin.id)
        raise Deliberate("row 900 of 1200")

    assert written_by(db, declared.batch_id) == 0, "not the rows, and not the claim"
    assert _durable(declared.batch_id) == 0, "and nothing reached another connection"


def test_the_failure_is_re_raised_rather_than_swallowed(
    db: Session, admin: User, project_id: str
) -> None:
    """A batch that failed must look like a batch that failed.

    Rolling back and returning quietly would leave the operator's terminal
    saying nothing went wrong while nothing was applied — and the runbook's next
    step would be whatever follows success.
    """
    declared = manifest()
    with (
        pytest.raises(ValueError, match="the real cause"),
        applying(db, declared, actor_user_id=admin.id),
    ):
        raise ValueError("the real cause")


def test_a_batch_that_rolled_back_can_be_retried_end_to_end(
    db: Session, admin: User, project_id: str
) -> None:
    """The retry property through the seam rather than through ``claim`` alone."""
    declared = manifest()
    with pytest.raises(RuntimeError), applying(db, declared, actor_user_id=admin.id):
        _stand_in_write(db, declared, admin.id)
        raise RuntimeError("dropped connection")

    with applying(db, declared, actor_user_id=admin.id):
        _stand_in_write(db, declared, admin.id)

    assert claims(db, declared.batch_id) == 1
    assert written_by(db, declared.batch_id) == 2


def test_a_batch_that_committed_cannot_be_applied_again_end_to_end(
    db: Session, admin: User, project_id: str
) -> None:
    """The other side of the same mechanism."""
    declared = manifest()
    with applying(db, declared, actor_user_id=admin.id):
        _stand_in_write(db, declared, admin.id)

    with pytest.raises(BatchAlreadyApplied), applying(db, declared, actor_user_id=admin.id):
        _stand_in_write(db, declared, admin.id)

    assert written_by(db, declared.batch_id) == 2, "the first run's claim and row, unchanged"


def test_a_session_holding_somebody_elses_work_is_refused(
    db: Session, admin: User, project_id: str
) -> None:
    """A batch owns its transaction, and may not adopt what it finds in one.

    Committing here would make an unrelated pending change durable under this
    batch's correlation id; failing here would destroy it. Both are the caller's
    work disposed of by an operation that never mentioned it.
    """
    declared = manifest()
    db.add(
        AuditEvent(
            action="something.else",
            entity_type="other",
            entity_id=None,
            correlation_id=uuid.uuid4(),
        )
    )

    with (
        pytest.raises(SessionNotClean, match="uncommitted"),
        applying(db, declared, actor_user_id=admin.id),
    ):
        pass

    db.rollback()
    assert claim_of(db, declared.batch_id) is None, "and no claim was taken on the way past"
