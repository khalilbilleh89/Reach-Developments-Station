"""Five races, on real PostgreSQL transactions across separate connections.

Every one of them is the same shape: two people read the same remaining
capacity, both act on it, and without a lock both succeed. The capacity differs
— budget headroom, a contract's commitment, a certificate's net due, an
invoice's outstanding balance, a milestone's certification — and so does what it
costs to get it wrong.

A mocked session would only prove the mock was called in the order the test
chose, which is exactly the thing under question. The harness mirrors the ones
in the inventory, pricing, sales, payment-plan, collections and unit-economics
concurrency files; it is copied rather than shared because a test file that
cannot be read on its own is a test file nobody reads.
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
from app.core.errors import ConflictError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.construction import service
from app.modules.construction.models import (
    CONTRACT_ACTIVE,
    MILESTONE_CERTIFIED,
    PAYMENT_CONFIRMED,
    Certificate,
    Contract,
    Invoice,
    Milestone,
    Payment,
)
from app.modules.projects.models import Project
from tests.modules.conftest import (
    construction_url,
    create_certificate,
    create_contract,
    create_milestone,
    record_invoice,
    record_payment,
    set_certificate_line,
    set_contract_line,
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
def two_contracts_on_one_headroom(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    cost_codes: dict[str, str],
    active_budget: str,
) -> tuple[str, str]:
    """Two submitted contracts of 6,000,000 each against 10,000,000 of headroom.

    Either one fits. Both together do not, and neither can see the other while
    it is only submitted — which is the entire race.
    """
    submitted: list[str] = []
    for number in ("CT-A", "CT-B"):
        created = create_contract(
            finance_client,
            project_id,
            currency_id,
            contract_number=number,
            original_contract_value_ex_tax="6000000.00",
        )
        assert created.status_code == 201, created.text
        contract_id = created.json()["id"]
        line = set_contract_line(
            finance_client,
            project_id,
            contract_id,
            sequence=1,
            cost_code_id=cost_codes["hard"],
            original_amount_ex_tax="6000000.00",
        )
        assert line.status_code == 200, line.text
        assert (
            finance_client.post(
                f"{construction_url(project_id)}/contracts/{contract_id}/submit", json={}
            ).status_code
            == 200
        )
        submitted.append(contract_id)
    return submitted[0], submitted[1]


class TestTheBudgetHeadroomRace:
    """Given two contracts that each fit, when both are activated at once."""

    def test_only_one_commitment_is_taken(
        self,
        db: Session,
        cfo: User,
        project_id: str,
        two_contracts_on_one_headroom: tuple[str, str],
    ) -> None:
        first, second = two_contracts_on_one_headroom
        project_uuid = uuid.UUID(project_id)
        holder_ready = threading.Event()
        holder_release = threading.Event()
        actor = _actor(cfo)

        def make(contract_id: str, hold: bool) -> Callable[[Session], object]:
            def run(session: Session) -> object:
                contract = service.activate_contract(
                    session,
                    project=_project(session, project_uuid),
                    actor=actor,
                    contract_id=uuid.UUID(contract_id),
                )
                if hold:
                    holder_ready.set()
                    holder_release.wait(timeout=15)
                session.commit()
                return contract.id

            return run

        won, lost = _race(
            make(first, hold=True), make(second, hold=False), holder_ready, holder_release
        )
        assert isinstance(won[0], uuid.UUID), won[0]
        assert isinstance(lost[0], ConflictError), lost[0]

        live = db.scalars(
            select(func.count(Contract.id)).where(
                Contract.project_id == project_uuid, Contract.status == CONTRACT_ACTIVE
            )
        ).one()
        assert live == 1


class TestTheCertificationRace:
    """Given two certificates that each fit the commitment, when both are certified."""

    def test_only_one_certification_is_recorded(
        self,
        db: Session,
        finance_client: TestClient,
        manager: User,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        submitted: list[str] = []
        for index, number in enumerate(("IPC-A", "IPC-B"), start=1):
            created = create_certificate(
                finance_client,
                project_id,
                active_contract,
                certificate_number=number,
                period_start=f"2026-0{index}-01",
                period_end=f"2026-0{index}-28",
                certificate_date=f"2026-0{index + 1}-05",
            )
            assert created.status_code == 201, created.text
            certificate_id = created.json()["id"]
            assert (
                set_certificate_line(
                    finance_client,
                    project_id,
                    certificate_id,
                    cost_code_id=cost_codes["hard"],
                    current_work_value_ex_tax="600000.00",
                ).status_code
                == 200
            )
            assert (
                finance_client.post(
                    f"{construction_url(project_id)}/certificates/{certificate_id}/submit",
                    json={},
                ).status_code
                == 200
            )
            submitted.append(certificate_id)

        project_uuid = uuid.UUID(project_id)
        holder_ready = threading.Event()
        holder_release = threading.Event()
        actor = _actor(manager)

        def make(certificate_id: str, hold: bool) -> Callable[[Session], object]:
            def run(session: Session) -> object:
                certificate = service.certify_certificate(
                    session,
                    project=_project(session, project_uuid),
                    actor=actor,
                    certificate_id=uuid.UUID(certificate_id),
                )
                if hold:
                    holder_ready.set()
                    holder_release.wait(timeout=15)
                session.commit()
                return certificate.id

            return run

        won, lost = _race(
            make(submitted[0], hold=True),
            make(submitted[1], hold=False),
            holder_ready,
            holder_release,
        )
        assert isinstance(won[0], uuid.UUID), won[0]
        assert isinstance(lost[0], ConflictError), lost[0]

        certified = db.scalars(
            select(func.count(Certificate.id)).where(
                Certificate.project_id == project_uuid, Certificate.status == "certified"
            )
        ).one()
        assert certified == 1


class TestTheInvoiceAuthorisationRace:
    """Given two claims against one certificate, when both are approved at once."""

    def test_only_one_claim_gets_the_certificates_ceiling(
        self,
        db: Session,
        finance_client: TestClient,
        cfo: User,
        project_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        recorded: list[str] = []
        for number in ("INV-A", "INV-B"):
            invoice = record_invoice(
                finance_client,
                project_id,
                active_contract,
                invoice_number=number,
                certificate_id=certified_certificate,
                amount_ex_tax="180000.00",
            )
            assert invoice.status_code == 201, invoice.text
            recorded.append(invoice.json()["id"])

        project_uuid = uuid.UUID(project_id)
        holder_ready = threading.Event()
        holder_release = threading.Event()
        actor = _actor(cfo)

        def make(invoice_id: str, hold: bool) -> Callable[[Session], object]:
            def run(session: Session) -> object:
                invoice = service.approve_invoice(
                    session,
                    project=_project(session, project_uuid),
                    actor=actor,
                    invoice_id=uuid.UUID(invoice_id),
                )
                if hold:
                    holder_ready.set()
                    holder_release.wait(timeout=15)
                session.commit()
                return invoice.id

            return run

        won, lost = _race(
            make(recorded[0], hold=True),
            make(recorded[1], hold=False),
            holder_ready,
            holder_release,
        )
        assert isinstance(won[0], uuid.UUID), won[0]
        assert isinstance(lost[0], ConflictError), lost[0]

        approved = db.scalars(
            select(func.count(Invoice.id)).where(
                Invoice.project_id == project_uuid, Invoice.status == "approved"
            )
        ).one()
        assert approved == 1


class TestThePaymentRace:
    """Given two payments settling one invoice, when both are confirmed at once."""

    def test_only_one_payment_settles_it(
        self,
        db: Session,
        finance_client: TestClient,
        second_finance_client: TestClient,
        cfo: User,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        assert invoice.status_code == 201, invoice.text
        invoice_id = invoice.json()["id"]
        assert (
            second_finance_client.post(
                f"{construction_url(project_id)}/invoices/{invoice_id}/approve", json={}
            ).status_code
            == 200
        )

        recorded: list[str] = []
        for reference in ("PMT-A", "PMT-B"):
            payment = record_payment(
                finance_client,
                project_id,
                active_contract,
                currency_id,
                payment_reference=reference,
                amount="180000.00",
            )
            assert payment.status_code == 201, payment.text
            payment_id = payment.json()["id"]
            allocated = finance_client.put(
                f"{construction_url(project_id)}/payments/{payment_id}/allocations",
                json={"invoice_id": invoice_id, "amount": "180000.00"},
            )
            assert allocated.status_code == 200, allocated.text
            recorded.append(payment_id)

        project_uuid = uuid.UUID(project_id)
        holder_ready = threading.Event()
        holder_release = threading.Event()
        actor = _actor(cfo)

        def make(payment_id: str, hold: bool) -> Callable[[Session], object]:
            def run(session: Session) -> object:
                payment = service.confirm_payment(
                    session,
                    project=_project(session, project_uuid),
                    actor=actor,
                    payment_id=uuid.UUID(payment_id),
                )
                if hold:
                    holder_ready.set()
                    holder_release.wait(timeout=15)
                session.commit()
                return payment.id

            return run

        won, lost = _race(
            make(recorded[0], hold=True),
            make(recorded[1], hold=False),
            holder_ready,
            holder_release,
        )
        assert isinstance(won[0], uuid.UUID), won[0]
        assert isinstance(lost[0], ConflictError | ValidationError), lost[0]

        confirmed = db.scalars(
            select(func.count(Payment.id)).where(
                Payment.project_id == project_uuid, Payment.status == PAYMENT_CONFIRMED
            )
        ).one()
        assert confirmed == 1
        assert Decimal(
            finance_client.get(f"{construction_url(project_id)}/summary").json()["payable"][
                "confirmed_paid"
            ]
        ) == Decimal("180000.00")


class TestTheMilestoneCertificationRace:
    """Given one milestone certified twice at once, when both carry a date."""

    def test_it_is_certified_once_and_on_one_date(
        self,
        db: Session,
        manager_member_client: TestClient,
        manager: User,
        project_id: str,
        active_budget: str,
    ) -> None:
        """The half that reaches a buyer's schedule must not run twice."""
        created = create_milestone(manager_member_client, project_id)
        assert created.status_code == 201, created.text
        milestone_id = uuid.UUID(created.json()["id"])

        project_uuid = uuid.UUID(project_id)
        holder_ready = threading.Event()
        holder_release = threading.Event()
        actor = _actor(manager)

        def make(certified_date: date, hold: bool) -> Callable[[Session], object]:
            def run(session: Session) -> object:
                milestone, _ = service.certify_milestone(
                    session,
                    project=_project(session, project_uuid),
                    actor=actor,
                    milestone_id=milestone_id,
                    certified_date=certified_date,
                )
                if hold:
                    holder_ready.set()
                    holder_release.wait(timeout=15)
                session.commit()
                return milestone.certified_date

            return run

        won, lost = _race(
            make(date(2026, 5, 2), hold=True),
            make(date(2026, 6, 2), hold=False),
            holder_ready,
            holder_release,
        )
        assert won[0] == date(2026, 5, 2), won[0]
        assert isinstance(lost[0], ConflictError), lost[0]

        milestone = db.scalars(select(Milestone).where(Milestone.id == milestone_id)).one()
        assert milestone.status == MILESTONE_CERTIFIED
        assert milestone.certified_date == date(2026, 5, 2)
