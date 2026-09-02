"""Concurrency: the cash a second writer could otherwise walk past.

Real PostgreSQL transactions on separate connections. A mocked session would
only prove the mock was called in the order the test chose, which is exactly the
thing under question.

The pattern: one transaction takes the same row lock the service takes and holds
it, the test waits until the second is genuinely blocked — by polling
PostgreSQL's own view of who is waiting rather than sleeping and hoping — then
the holder commits. The second writer must decide against the committed state,
not the state it read before it blocked.

Two collections officers filling the same instalment from different receipts is
not a hypothetical. Each reads ten thousand outstanding, each allocates eight,
and without a lock the instalment ends up holding sixteen thousand against a
ten-thousand obligation — an over-allocation that no later report can explain.

The harness mirrors the ones in the inventory, pricing, sales and payment-plan
concurrency files. It is copied rather than shared because a test file that
cannot be read on its own is a test file nobody reads.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.core.errors import ConflictError, PermissionDeniedError
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.collections import service
from app.modules.collections.models import (
    ALLOCATION_ACTIVE,
    RECEIPT_CONFIRMED,
    RECEIPT_REVERSED,
    CollectionReceipt,
    CollectionReceiptAllocation,
    CollectionRefund,
)
from app.modules.payment_plans.models import PaymentPlanInstallment
from app.modules.projects.models import Project
from tests.modules.conftest import (
    collections_url,
    confirm_receipt,
    governing_installments,
    record_receipt,
    sales_url,
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
def two_receipts(
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
) -> dict[str, str]:
    """Two confirmed receipts, each holding 60% of the first instalment.

    Sized off the instalment rather than fixed, so the arithmetic of the race is
    guaranteed whatever the fixture contract is worth: either receipt alone fits
    comfortably, and the two together cannot possibly both be applied.
    """
    rows = governing_installments(collections_client, project_id, collecting_sale)
    room = Decimal(rows[0]["outstanding"])
    each = (room * Decimal("0.6")).quantize(Decimal("0.01"))

    ids: list[str] = []
    for _ in range(2):
        recorded = record_receipt(collections_client, project_id, collecting_sale, str(each))
        assert recorded.status_code == 201, recorded.text
        receipt_id = recorded.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
        ids.append(receipt_id)
    return {
        "first": ids[0],
        "second": ids[1],
        "installment_id": rows[0]["installment_id"],
        "sale_id": collecting_sale,
        "each": str(each),
        "room": str(room),
    }


class TestAllocationRace:
    """Given one instalment and two officers, when both allocate at once."""

    def test_two_allocations_cannot_between_them_exceed_the_instalment(
        self,
        db: Session,
        project_id: str,
        two_receipts: dict[str, str],
        collections_officer: User,
        second_collections_officer: User,
        collections_client: TestClient,
        second_collections_client: TestClient,
    ) -> None:
        """Both read the same remaining balance; only one result may commit.

        The instalment row owns the invariant, so it is taken for update before
        the remaining balance is read. The second writer blocks, then re-reads
        against committed state and is told what is actually left.
        """
        del collections_client, second_collections_client
        installment_id = uuid.UUID(two_receipts["installment_id"])
        scheduled = db.scalars(
            select(PaymentPlanInstallment).where(PaymentPlanInstallment.id == installment_id)
        ).one()
        room = scheduled.principal_amount + scheduled.tax_amount + scheduled.fee_amount
        # Each writer takes 60% of the instalment. Either alone is fine; both
        # would be 120% of an amount that may not exceed 100%.
        each = Decimal(two_receipts["each"])
        assert each * 2 > room

        project_uuid = uuid.UUID(project_id)
        holder_actor = _actor(collections_officer)
        contender_actor = _actor(second_collections_officer)
        holder_ready = threading.Event()
        holder_release = threading.Event()

        def holder(session: Session) -> object:
            actor = holder_actor
            local_project = _project(session, project_uuid)
            allocation = service.create_allocation(
                session,
                project=local_project,
                actor=actor,
                receipt_id=uuid.UUID(two_receipts["first"]),
                installment_id=installment_id,
                amount=each,
                correlation_id=uuid.uuid4(),
            )
            holder_ready.set()
            holder_release.wait(timeout=15)
            session.commit()
            return allocation.id

        def contender(session: Session) -> object:
            actor = contender_actor
            local_project = _project(session, project_uuid)
            allocation = service.create_allocation(
                session,
                project=local_project,
                actor=actor,
                receipt_id=uuid.UUID(two_receipts["second"]),
                installment_id=installment_id,
                amount=each,
                correlation_id=uuid.uuid4(),
            )
            session.commit()
            return allocation.id

        first_thread, first_outcome = _run(holder)
        if not holder_ready.wait(timeout=20):
            first_thread.join(timeout=5)
            raise AssertionError(f"the first writer never took its lock: {first_outcome}")

        second_thread, second_outcome = _run(contender)
        assert _wait_until_a_backend_blocks(), "the second writer was never blocked"

        holder_release.set()
        first_thread.join(timeout=20)
        second_thread.join(timeout=20)

        assert not isinstance(first_outcome[0], BaseException), first_outcome[0]
        assert isinstance(second_outcome[0], ConflictError), second_outcome[0]
        assert "remaining" in second_outcome[0].detail

        db.expire_all()
        applied = db.scalar(
            select(func.coalesce(func.sum(CollectionReceiptAllocation.amount), 0)).where(
                CollectionReceiptAllocation.installment_id == installment_id,
                CollectionReceiptAllocation.status == ALLOCATION_ACTIVE,
            )
        )
        assert Decimal(applied) <= room


class TestReceiptRace:
    """Given one receipt, when it is confirmed and reversed at the same time."""

    def test_a_receipt_cannot_end_up_both_confirmed_and_reversed(
        self,
        db: Session,
        project_id: str,
        collecting_sale: str,
        recorded_receipt: str,
        finance: User,
        second_finance: User,
        finance_client: TestClient,
        second_finance_client: TestClient,
    ) -> None:
        del collecting_sale, finance_client, second_finance_client
        receipt_id = uuid.UUID(recorded_receipt)
        project_uuid = uuid.UUID(project_id)
        confirmer_actor = _actor(finance)
        reverser_actor = _actor(second_finance)
        holder_ready = threading.Event()
        holder_release = threading.Event()

        def confirmer(session: Session) -> object:
            actor = confirmer_actor
            local_project = _project(session, project_uuid)
            receipt = service.confirm_receipt(
                session,
                project=local_project,
                actor=actor,
                receipt_id=receipt_id,
                correlation_id=uuid.uuid4(),
            )
            holder_ready.set()
            holder_release.wait(timeout=15)
            session.commit()
            return receipt.status

        def reverser(session: Session) -> object:
            actor = reverser_actor
            local_project = _project(session, project_uuid)
            receipt = service.reverse_receipt(
                session,
                project=local_project,
                actor=actor,
                receipt_id=receipt_id,
                reason="Recalled by the bank",
                correlation_id=uuid.uuid4(),
            )
            session.commit()
            return receipt.status

        first_thread, first_outcome = _run(confirmer)
        assert holder_ready.wait(timeout=20), "the confirmation never took its lock"

        second_thread, second_outcome = _run(reverser)
        assert _wait_until_a_backend_blocks(), "the reversal was never blocked"

        holder_release.set()
        first_thread.join(timeout=20)
        second_thread.join(timeout=20)

        assert first_outcome[0] == RECEIPT_CONFIRMED
        # The reversal serialised behind the confirmation and then succeeded
        # against the state it found. Either way the row holds one status.
        assert second_outcome[0] in (RECEIPT_REVERSED,) or isinstance(
            second_outcome[0], ConflictError
        )

        db.expire_all()
        receipt = db.scalars(
            select(CollectionReceipt).where(CollectionReceipt.id == receipt_id)
        ).one()
        assert receipt.status in (RECEIPT_CONFIRMED, RECEIPT_REVERSED)
        if receipt.status == RECEIPT_REVERSED:
            assert receipt.reversal_reason is not None
            assert receipt.reversed_by_user_id is not None

    def test_the_same_receipt_cannot_be_confirmed_twice_concurrently(
        self,
        db: Session,
        project_id: str,
        collecting_sale: str,
        recorded_receipt: str,
        finance: User,
        second_finance: User,
        finance_client: TestClient,
        second_finance_client: TestClient,
    ) -> None:
        del collecting_sale, finance_client, second_finance_client
        receipt_id = uuid.UUID(recorded_receipt)
        project_uuid = uuid.UUID(project_id)
        holder_ready = threading.Event()
        holder_release = threading.Event()

        def make(
            actor_for: ActorContext, ready: threading.Event | None
        ) -> Callable[[Session], object]:
            def run(session: Session) -> object:
                actor = actor_for
                local_project = _project(session, project_uuid)
                receipt = service.confirm_receipt(
                    session,
                    project=local_project,
                    actor=actor,
                    receipt_id=receipt_id,
                    correlation_id=uuid.uuid4(),
                )
                if ready is not None:
                    ready.set()
                    holder_release.wait(timeout=15)
                session.commit()
                return receipt.status

            return run

        first_thread, first_outcome = _run(make(_actor(finance), holder_ready))
        assert holder_ready.wait(timeout=20)
        second_thread, second_outcome = _run(make(_actor(second_finance), None))
        assert _wait_until_a_backend_blocks()

        holder_release.set()
        first_thread.join(timeout=20)
        second_thread.join(timeout=20)

        assert first_outcome[0] == RECEIPT_CONFIRMED
        assert isinstance(second_outcome[0], ConflictError)
        assert "already been confirmed" in second_outcome[0].detail


class TestRestructureRace:
    """Given a restructure applying, when cash is allocated at the same time."""

    def test_an_allocation_cannot_land_on_a_schedule_being_replaced(
        self,
        db: Session,
        collections_client: TestClient,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        active_plan: tuple[str, str],
        collections_officer: User,
        second_collections_officer: User,
    ) -> None:
        """Both writers take the project row first, so they serialise.

        The point is not which one wins but that no cash is ever assigned to
        both the old and the new active schedule: the loser is refused against
        committed state.
        """
        from tests.modules.conftest import plans_url, write_schedule

        plan_id, _ = active_plan
        rows = governing_installments(collections_client, project_id, collecting_sale)
        first = record_receipt(collections_client, project_id, collecting_sale, "5000.00").json()
        confirm_receipt(finance_client, project_id, first["id"])
        collections_client.post(
            f"{collections_url(project_id)}/receipts/{first['id']}/allocations",
            json={"installment_id": rows[0]["installment_id"], "amount": "5000.00"},
        )
        spare = record_receipt(collections_client, project_id, collecting_sale, "1000.00").json()
        confirm_receipt(finance_client, project_id, spare["id"])

        restructure = collections_client.post(
            f"{collections_url(project_id)}/sales/{collecting_sale}/restructures",
            json={"reason": "Rescheduled"},
        ).json()
        version_id = restructure["replacement_version_id"]
        write_schedule(
            collections_client,
            project_id,
            plan_id,
            version_id,
            [
                {
                    "sequence": 1,
                    "label": "Instalment 1",
                    "trigger_type": "fixed_date",
                    "contractual_due_date": "2026-03-01",
                    "principal_fraction": "0.400000",
                },
                {
                    "sequence": 2,
                    "label": "Instalment 2",
                    "trigger_type": "fixed_date",
                    "contractual_due_date": "2026-09-01",
                    "principal_fraction": "0.600000",
                },
            ],
        )
        base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
        collections_client.post(f"{base}/submit", json={})
        cfo_client.post(f"{base}/approve", json={"reason": "Agreed"})

        project_uuid = uuid.UUID(project_id)
        holder_actor = _actor(collections_officer)
        contender_actor = _actor(second_collections_officer)
        holder_ready = threading.Event()
        holder_release = threading.Event()

        def applier(session: Session) -> object:
            actor = holder_actor
            local_project = _project(session, project_uuid)
            applied = service.apply_restructure(
                session,
                project=local_project,
                actor=actor,
                restructure_id=uuid.UUID(restructure["id"]),
                correlation_id=uuid.uuid4(),
            )
            holder_ready.set()
            holder_release.wait(timeout=15)
            session.commit()
            return applied.status

        def allocator(session: Session) -> object:
            actor = contender_actor
            local_project = _project(session, project_uuid)
            allocation = service.create_allocation(
                session,
                project=local_project,
                actor=actor,
                receipt_id=uuid.UUID(spare["id"]),
                installment_id=uuid.UUID(rows[1]["installment_id"]),
                amount=Decimal("1000.00"),
                correlation_id=uuid.uuid4(),
            )
            session.commit()
            return allocation.id

        first_thread, first_outcome = _run(applier)
        if not holder_ready.wait(timeout=20):
            first_thread.join(timeout=5)
            raise AssertionError(f"the restructure never took its locks: {first_outcome}")
        second_thread, second_outcome = _run(allocator)
        assert _wait_until_a_backend_blocks(), "the allocation was never blocked"

        holder_release.set()
        first_thread.join(timeout=20)
        second_thread.join(timeout=20)

        assert first_outcome[0] == "applied", first_outcome[0]
        # The instalment it aimed at belongs to the superseded schedule now.
        assert isinstance(second_outcome[0], BaseException), second_outcome[0]

        db.expire_all()
        active = db.scalars(
            select(CollectionReceiptAllocation).where(
                CollectionReceiptAllocation.sale_contract_id == uuid.UUID(collecting_sale),
                CollectionReceiptAllocation.status == ALLOCATION_ACTIVE,
            )
        ).all()
        versions = {row.payment_plan_version_id for row in active}
        assert len(versions) == 1, "cash is only ever active against one schedule"


class TestRefundRace:
    """Given one cancellation, when two refunds are confirmed at once."""

    def test_two_confirmations_cannot_exceed_the_amount_due(
        self,
        db: Session,
        collections_client: TestClient,
        sales_ops_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        finance: User,
        second_finance: User,
    ) -> None:
        cancellation = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation",
            json={
                "initiated_by_party": "buyer",
                "initiation_date": "2026-05-01",
                "reason": "Buyer withdrew",
                "refund_due_amount": "10000.00",
            },
        )
        assert cancellation.status_code == 201, cancellation.text
        cancellation_id = cancellation.json()["id"]

        # A proposed refund is not a debt until a financial approver signs it,
        # and money does not leave on an unsigned one. Without this the race
        # being tested could not happen in production at all.
        approved = cfo_client.post(
            f"{sales_url(project_id)}/cancellations/{cancellation_id}/approve-financial-terms",
            json={"reason": "Terms reviewed against the contract"},
        )
        assert approved.status_code == 200, approved.text

        refunds = []
        for _ in range(2):
            recorded = collections_client.post(
                f"{collections_url(project_id)}/sales/{collecting_sale}/refunds",
                json={
                    "cancellation_id": cancellation_id,
                    "amount": "8000.00",
                    "refund_date": "2026-06-01",
                },
            )
            assert recorded.status_code == 201, recorded.text
            refunds.append(recorded.json()["id"])

        project_uuid = uuid.UUID(project_id)
        holder_ready = threading.Event()
        holder_release = threading.Event()

        def make(
            actor_for: ActorContext, refund_id: str, ready: threading.Event | None
        ) -> Callable[[Session], object]:
            def run(session: Session) -> object:
                actor = actor_for
                local_project = _project(session, project_uuid)
                refund = service.confirm_refund(
                    session,
                    project=local_project,
                    actor=actor,
                    refund_id=uuid.UUID(refund_id),
                    correlation_id=uuid.uuid4(),
                )
                if ready is not None:
                    ready.set()
                    holder_release.wait(timeout=15)
                session.commit()
                return refund.status

            return run

        first_thread, first_outcome = _run(make(_actor(finance), refunds[0], holder_ready))
        assert holder_ready.wait(timeout=20)
        second_thread, second_outcome = _run(make(_actor(second_finance), refunds[1], None))
        assert _wait_until_a_backend_blocks(), "the second confirmation was never blocked"

        holder_release.set()
        first_thread.join(timeout=20)
        second_thread.join(timeout=20)

        assert first_outcome[0] == "confirmed"
        assert isinstance(second_outcome[0], ConflictError | PermissionDeniedError), second_outcome[
            0
        ]

        db.expire_all()
        total = db.scalar(
            select(func.coalesce(func.sum(CollectionRefund.amount), 0)).where(
                CollectionRefund.cancellation_id == uuid.UUID(cancellation_id),
                CollectionRefund.status == "confirmed",
            )
        )
        assert Decimal(total) <= Decimal("10000.00")
