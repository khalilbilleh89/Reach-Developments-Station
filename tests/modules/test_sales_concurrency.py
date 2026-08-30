"""Concurrency: the commitments a second writer could otherwise walk past.

Every test here runs real PostgreSQL transactions on separate connections. A
mocked session would only prove the mock was called in the order the test chose,
which is exactly the thing under question.

The pattern throughout: one transaction takes the same row lock the service
takes and holds it, the test waits until the second is genuinely blocked — by
polling PostgreSQL's own view of who is waiting rather than sleeping and hoping
— then the holder commits. The second writer must then decide against the
committed state, not the state it read before it blocked.

The harness below mirrors the ones in ``test_inventory_concurrency`` and
``test_pricing_concurrency``. It is copied rather than shared because a test
file that cannot be read on its own is a test file nobody reads.
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
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.inventory.models import Unit
from app.modules.projects.models import Project
from app.modules.sales import service
from app.modules.sales.models import Reservation, SaleContract
from tests.modules.conftest import record_legal, sales_url


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


def _second_reservation(client: TestClient, project_id: str, unit_id: str, client_id: str) -> str:
    """A second reservation in preparation on the same unit.

    Created before the first is activated, because a unit that already carries a
    commitment refuses a new one — which is the invariant these tests exist to
    check under contention rather than in sequence.
    """
    created = client.post(
        f"{sales_url(project_id)}/reservations",
        json={"unit_id": unit_id, "client_id": client_id},
    )
    assert created.status_code == 201, created.text
    reservation_id = created.json()["reservation"]["id"]
    confirmed = client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-REF-B"},
    )
    assert confirmed.status_code == 200, confirmed.text
    return reservation_id


def test_two_reservations_cannot_both_commit_the_same_unit(
    sales_ops_client: TestClient,
    sales_ops: User,
    project_id: str,
    released_unit: str,
    buyer_id: str,
    reservation_id: str,
    db: Session,
) -> None:
    """Given a held unit lock, then the second activation sees the first.

    Without the lock both writers read "available", both write "reserved", and
    the development has sold one flat twice.
    """
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-REF-A"},
    )
    second = _second_reservation(sales_ops_client, project_id, released_unit, buyer_id)

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(released_unit)).with_for_update())

    def activate_second(session: Session) -> str:
        service.activate_reservation(
            session,
            project=_project(session, project_id),
            reservation_id=uuid.UUID(second),
            actor=_actor(sales_ops),
        )
        return "activated"

    thread, outcome = _run(activate_second)
    try:
        blocked = _wait_until_a_backend_blocks()
        # The holder commits the first activation while the second is waiting.
        first = holder.scalars(
            select(Reservation).where(Reservation.id == uuid.UUID(reservation_id))
        ).one()
        first.status = "active"
        unit = holder.scalars(select(Unit).where(Unit.id == uuid.UUID(released_unit))).one()
        unit.commercial_status = "reserved"
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the activation decided without taking the unit lock"
    assert isinstance(outcome[0], Exception), outcome[0]
    db.expire_all()
    statuses = {
        str(row.id): row.status
        for row in db.scalars(select(Reservation).where(Reservation.project_id == project_id))
    }
    assert statuses[reservation_id] == "active"
    assert statuses[second] != "active"
    assert (
        db.scalars(select(Unit).where(Unit.id == uuid.UUID(released_unit))).one().commercial_status
        == "reserved"
    )


def test_the_database_refuses_a_second_committed_reservation(
    sales_ops_client: TestClient,
    project_id: str,
    released_unit: str,
    buyer_id: str,
    active_reservation: str,
    db: Session,
) -> None:
    """The service lock could be removed by a careless refactor; this could not."""
    other = db.scalars(
        select(Reservation).where(Reservation.id == uuid.UUID(active_reservation))
    ).one()
    duplicate = Reservation(
        project_id=other.project_id,
        reservation_number="RES-999999",
        unit_id=other.unit_id,
        client_id=other.client_id,
        unit_price_version_id=other.unit_price_version_id,
        status="active",
        reservation_date=other.reservation_date,
        expires_on=other.expires_on,
        price_locked_until=other.price_locked_until,
        deposit_gate_status="not_required",
        currency_id=other.currency_id,
        reference_price_ex_tax=other.reference_price_ex_tax,
        paid_upgrade_amount=other.paid_upgrade_amount,
        payment_plan_adjustment_amount=other.payment_plan_adjustment_amount,
        gross_quoted_price_ex_tax=other.gross_quoted_price_ex_tax,
        cash_discount_amount=other.cash_discount_amount,
        seller_credit_amount=other.seller_credit_amount,
        net_contract_price_ex_tax=other.net_contract_price_ex_tax,
        seller_cost_total=other.seller_cost_total,
        effective_net_revenue_preview=other.effective_net_revenue_preview,
        tax_total=other.tax_total,
        buyer_fee_total=other.buyer_fee_total,
        total_buyer_payable=other.total_buyer_payable,
        exception_approval_required=False,
        exception_approval_status="not_required",
        quote_snapshot_json={},
        created_by_user_id=other.created_by_user_id,
    )
    db.add(duplicate)

    with pytest.raises(IntegrityError) as raised:
        db.flush()

    assert "uq_reservations_committed_unit" in str(raised.value)
    db.rollback()


def test_two_submissions_cannot_both_take_the_unit_from_one_reservation(
    sales_ops_client: TestClient,
    sales_ops: User,
    project_id: str,
    released_unit: str,
    active_reservation: str,
    sale_id: str,
    db: Session,
) -> None:
    """Given a held unit lock, then the second submission sees the first's work."""
    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(released_unit)).with_for_update())

    def submit(session: Session) -> str:
        service.submit_sale(
            session,
            project=_project(session, project_id),
            sale_id=uuid.UUID(sale_id),
            actor=_actor(sales_ops),
        )
        return "submitted"

    thread, outcome = _run(submit)
    try:
        blocked = _wait_until_a_backend_blocks()
        reservation = holder.scalars(
            select(Reservation).where(Reservation.id == uuid.UUID(active_reservation))
        ).one()
        reservation.status = "converted"
        unit = holder.scalars(select(Unit).where(Unit.id == uuid.UUID(released_unit))).one()
        unit.commercial_status = "contract_pending"
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the submission decided without taking the unit lock"
    assert isinstance(outcome[0], Exception), outcome[0]
    db.expire_all()
    sale = db.scalars(select(SaleContract).where(SaleContract.id == uuid.UUID(sale_id))).one()
    assert sale.status == "draft"
    events = db.scalars(
        select(Reservation).where(Reservation.id == uuid.UUID(active_reservation))
    ).one()
    assert events.status == "converted"


def test_the_database_refuses_a_second_committed_contract(
    project_id: str, submitted_sale: str, db: Session
) -> None:
    other = db.scalars(
        select(SaleContract).where(SaleContract.id == uuid.UUID(submitted_sale))
    ).one()
    duplicate = SaleContract(
        project_id=other.project_id,
        sale_number="SALE-999999",
        reservation_id=other.reservation_id,
        unit_id=other.unit_id,
        client_id=other.client_id,
        unit_price_version_id=other.unit_price_version_id,
        currency_id=other.currency_id,
        contract_date=other.contract_date,
        status="active",
        reference_price_ex_tax=other.reference_price_ex_tax,
        gross_quoted_price_ex_tax=other.gross_quoted_price_ex_tax,
        cash_discount_amount=other.cash_discount_amount,
        seller_credit_amount=other.seller_credit_amount,
        net_contract_price_ex_tax=other.net_contract_price_ex_tax,
        seller_cost_total=other.seller_cost_total,
        effective_net_revenue_snapshot=other.effective_net_revenue_snapshot,
        tax_total=other.tax_total,
        buyer_fee_total=other.buyer_fee_total,
        total_contract_price=other.total_contract_price,
        reservation_quote_snapshot_json={},
        first_payment_gate_status="not_required",
        created_by_user_id=other.created_by_user_id,
    )
    db.add(duplicate)

    with pytest.raises(IntegrityError) as raised:
        db.flush()

    assert "uq_sale_contracts_committed_unit" in str(raised.value)
    db.rollback()


def test_two_activations_of_one_contract_produce_one_coherent_result(
    sales_ops_client: TestClient,
    sales_ops: User,
    legal_client: TestClient,
    project_id: str,
    released_unit: str,
    submitted_sale: str,
    db: Session,
) -> None:
    for event_type, event_date in (
        ("spa_drafted", "2026-02-01"),
        ("spa_issued", "2026-02-02"),
        ("buyer_signed", "2026-02-03"),
        ("seller_signed", "2026-02-04"),
    ):
        record_legal(legal_client, project_id, submitted_sale, event_type, event_date)

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(released_unit)).with_for_update())

    def activate(session: Session) -> str:
        service.activate_sale(
            session,
            project=_project(session, project_id),
            sale_id=uuid.UUID(submitted_sale),
            actor=_actor(sales_ops),
        )
        return "activated"

    thread, outcome = _run(activate)
    try:
        blocked = _wait_until_a_backend_blocks()
        sale = holder.scalars(
            select(SaleContract).where(SaleContract.id == uuid.UUID(submitted_sale))
        ).one()
        sale.status = "active"
        unit = holder.scalars(select(Unit).where(Unit.id == uuid.UUID(released_unit))).one()
        unit.commercial_status = "contracted"
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the activation decided without taking the unit lock"
    assert isinstance(outcome[0], Exception), outcome[0]
    db.expire_all()
    from app.modules.inventory.models import UnitStatusEvent

    contracted = db.scalars(
        select(UnitStatusEvent).where(
            UnitStatusEvent.unit_id == uuid.UUID(released_unit),
            UnitStatusEvent.to_status == "contracted",
        )
    ).all()
    # One activation, one recorded movement. Not two.
    assert len(contracted) == 0


def test_a_cancellation_and_a_handover_cannot_both_win(
    sales_ops_client: TestClient,
    sales_ops: User,
    legal_client: TestClient,
    collections_client: TestClient,
    delivery_client: TestClient,
    project_id: str,
    released_unit: str,
    active_sale: str,
    db: Session,
) -> None:
    """A cancelled contract and a handed-over unit cannot coexist from stale reads.

    Both operations serialise on the project row, so the second one to reach it
    re-reads the first's committed state and refuses. The impossible pair — a
    cancelled sale and a unit the buyer has the keys to — has no way to arise.
    """
    handover = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/handover", json={}
    )
    assert handover.status_code == 201, handover.text
    handover_id = handover.json()["handover"]["id"]
    for client, clearance_type in (
        (legal_client, "legal"),
        (collections_client, "collection"),
        (delivery_client, "delivery"),
    ):
        client.post(
            f"{sales_url(project_id)}/handovers/{handover_id}/clearances/{clearance_type}",
            json={"evidence_reference": "OK"},
        )

    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Project).where(Project.id == uuid.UUID(project_id)).with_for_update())

    def complete_handover(session: Session) -> str:
        service.complete_handover(
            session,
            project=_project(session, project_id),
            handover_id=uuid.UUID(handover_id),
            actor=_actor(sales_ops),
            handover_date=date(2026, 6, 1),
            acceptance_document_reference="ACC-1",
        )
        return "handed over"

    thread, outcome = _run(complete_handover)
    try:
        blocked = _wait_until_a_backend_blocks()
        # The cancellation wins the race, committed while the handover waits.
        sale = holder.scalars(
            select(SaleContract).where(SaleContract.id == uuid.UUID(active_sale))
        ).one()
        sale.status = "cancelled"
        unit = holder.scalars(select(Unit).where(Unit.id == uuid.UUID(released_unit))).one()
        unit.commercial_status = "returned"
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the handover decided without taking the project lock"
    assert isinstance(outcome[0], Exception), outcome[0]
    db.expire_all()
    unit = db.scalars(select(Unit).where(Unit.id == uuid.UUID(released_unit))).one()
    assert unit.delivery_status != "handed_over"


def test_a_reservation_cannot_be_activated_on_a_price_invalidated_before_the_lock(
    sales_ops_client: TestClient,
    sales_ops: User,
    project_id: str,
    released_unit: str,
    reservation_id: str,
    db: Session,
) -> None:
    """Given the price is withdrawn while the writer waits, then it re-reads and refuses."""
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/confirm-deposit",
        json={"evidence_reference": "BANK-REF-A"},
    )
    factory = get_session_factory()
    holder = factory()
    holder.execute(select(Unit).where(Unit.id == uuid.UUID(released_unit)).with_for_update())

    def activate(session: Session) -> str:
        service.activate_reservation(
            session,
            project=_project(session, project_id),
            reservation_id=uuid.UUID(reservation_id),
            actor=_actor(sales_ops),
        )
        return "activated"

    thread, outcome = _run(activate)
    try:
        blocked = _wait_until_a_backend_blocks()
        unit = holder.scalars(select(Unit).where(Unit.id == uuid.UUID(released_unit))).one()
        unit.pricing_approved = False
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the activation decided without taking the unit lock"
    assert isinstance(outcome[0], Exception), outcome[0]
    assert "released for sale" in str(outcome[0]) or "repricing" in str(outcome[0])
    db.expire_all()
    reservation = db.scalars(
        select(Reservation).where(Reservation.id == uuid.UUID(reservation_id))
    ).one()
    assert reservation.status != "active"


def test_two_reservations_cannot_take_the_same_number(
    sales_ops_client: TestClient, project_id: str, released_unit: str, buyer_id: str, db: Session
) -> None:
    created = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={"unit_id": released_unit, "client_id": buyer_id},
    )
    assert created.status_code == 201, created.text
    first = db.scalars(
        select(Reservation).where(Reservation.id == uuid.UUID(created.json()["reservation"]["id"]))
    ).one()
    duplicate = Reservation(
        project_id=first.project_id,
        reservation_number=first.reservation_number,
        unit_id=first.unit_id,
        client_id=first.client_id,
        unit_price_version_id=first.unit_price_version_id,
        status="draft",
        reservation_date=first.reservation_date,
        expires_on=first.expires_on,
        price_locked_until=first.price_locked_until,
        deposit_gate_status="not_required",
        currency_id=first.currency_id,
        reference_price_ex_tax=first.reference_price_ex_tax,
        paid_upgrade_amount=first.paid_upgrade_amount,
        payment_plan_adjustment_amount=first.payment_plan_adjustment_amount,
        gross_quoted_price_ex_tax=first.gross_quoted_price_ex_tax,
        cash_discount_amount=first.cash_discount_amount,
        seller_credit_amount=first.seller_credit_amount,
        net_contract_price_ex_tax=first.net_contract_price_ex_tax,
        seller_cost_total=first.seller_cost_total,
        effective_net_revenue_preview=first.effective_net_revenue_preview,
        tax_total=first.tax_total,
        buyer_fee_total=first.buyer_fee_total,
        total_buyer_payable=first.total_buyer_payable,
        exception_approval_required=False,
        exception_approval_status="not_required",
        quote_snapshot_json={},
        created_by_user_id=first.created_by_user_id,
    )
    db.add(duplicate)

    with pytest.raises(IntegrityError) as raised:
        db.flush()

    assert "uq_reservations_number" in str(raised.value)
    db.rollback()
