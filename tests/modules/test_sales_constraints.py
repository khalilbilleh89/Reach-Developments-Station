"""What the database refuses, whatever the service does.

Application validation gives a caller a message worth reading. It is not the
final integrity layer, and a rule that exists only in Python is one careless
refactor away from being gone. Everything here bypasses the service and writes
straight to PostgreSQL.

Every guard the service owns has a counterpart here where a column, a check or a
partial index can carry it. Cross-table business transitions — "may this
reservation become active" — remain the service's, because a database cannot
express them without becoming a second implementation of the domain.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.sales.models import (
    Client,
    ClientParty,
    HandoverClearance,
    Reservation,
    ReservationAdjustment,
    SaleContract,
    SaleLegalEvent,
)
from tests.modules.conftest import sales_url


def _reservation(db: Session, reservation_id: str) -> Reservation:
    return db.scalars(select(Reservation).where(Reservation.id == uuid.UUID(reservation_id))).one()


def _refuses(db: Session, name: str) -> None:
    """Flush, expect the named constraint to refuse, and leave the session clean.

    Composite project-safe foreign keys carry short names — ``unit``, ``client``,
    ``sale`` — the way inventory's do, because PostgreSQL truncates identifiers
    at 63 characters and a truncated name stops matching the metadata for ever
    afterwards. They are quoted in the message, which is what the assertions
    below match on.
    """
    with pytest.raises(IntegrityError) as raised:
        db.flush()
    assert name in str(raised.value)
    db.rollback()


# --------------------------------------------------------------------------- #
# Identity and project containment
# --------------------------------------------------------------------------- #


def test_a_client_number_is_unique_within_a_project(
    project_id: str, buyer_id: str, db: Session
) -> None:
    existing = db.scalars(select(Client).where(Client.id == uuid.UUID(buyer_id))).one()
    db.add(
        Client(
            project_id=existing.project_id,
            client_number=existing.client_number,
            display_name="Impostor",
            kyc_status="not_started",
            created_by_user_id=existing.created_by_user_id,
        )
    )

    _refuses(db, "uq_clients_number")


def test_a_reservation_cannot_point_at_a_unit_outside_its_project(
    project_id: str, reservation_id: str, db: Session
) -> None:
    """The composite key is what stops a unit of one project reaching another's sale.

    The reservation references ``(unit_id, project_id)`` as a pair, so a unit
    that is not this project's cannot be attached however the identifiers are
    shuffled — and neither can a real unit belonging to somebody else's project.
    """
    reservation = _reservation(db, reservation_id)

    reservation.unit_id = uuid.uuid4()

    _refuses(db, '"unit"')


def test_a_buyer_party_cannot_be_moved_to_another_projects_client(
    project_id: str, buyer_id: str, db: Session
) -> None:
    party = db.scalars(
        select(ClientParty).where(ClientParty.client_id == uuid.UUID(buyer_id))
    ).one()

    party.project_id = uuid.uuid4()

    _refuses(db, '"client"')


def test_a_legal_event_cannot_point_at_a_contract_that_does_not_exist(
    project_id: str, active_sale: str, db: Session
) -> None:
    event = db.scalars(
        select(SaleLegalEvent).where(SaleLegalEvent.sale_contract_id == uuid.UUID(active_sale))
    ).first()
    assert event is not None

    event.sale_contract_id = uuid.uuid4()

    _refuses(db, '"sale"')


# --------------------------------------------------------------------------- #
# Closed sets
# --------------------------------------------------------------------------- #


def test_a_reservation_cannot_hold_a_status_outside_the_closed_set(
    project_id: str, reservation_id: str, db: Session
) -> None:
    reservation = _reservation(db, reservation_id)

    reservation.status = "sold"

    _refuses(db, "ck_reservations_status_ok")


def test_a_contract_cannot_hold_a_status_outside_the_closed_set(
    project_id: str, sale_id: str, db: Session
) -> None:
    sale = db.scalars(select(SaleContract).where(SaleContract.id == uuid.UUID(sale_id))).one()

    sale.status = "sold"

    _refuses(db, "ck_sale_contracts_status_ok")


def test_a_clearance_cannot_invent_a_type(
    project_id: str, active_sale: str, sales_ops_client: TestClient, db: Session
) -> None:
    handover = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/handover", json={}
    )
    assert handover.status_code == 201, handover.text
    clearance = db.scalars(
        select(HandoverClearance).where(
            HandoverClearance.handover_id == uuid.UUID(handover.json()["handover"]["id"])
        )
    ).first()
    assert clearance is not None

    clearance.clearance_type = "marketing"

    _refuses(db, "ck_handover_clearances_type_ok")


def test_a_deposit_gate_cannot_be_waived_without_a_reason(
    project_id: str, reservation_id: str, db: Session
) -> None:
    reservation = _reservation(db, reservation_id)

    reservation.deposit_gate_status = "waived"

    _refuses(db, "ck_reservations_waiver_has_reason")


# --------------------------------------------------------------------------- #
# Money and shares
# --------------------------------------------------------------------------- #


def test_a_contract_price_cannot_be_negative(project_id: str, sale_id: str, db: Session) -> None:
    sale = db.scalars(select(SaleContract).where(SaleContract.id == uuid.UUID(sale_id))).one()

    sale.net_contract_price_ex_tax = Decimal("-1.00")

    _refuses(db, "ck_sale_contracts_net_nonneg")


def test_a_reservations_tax_total_cannot_be_negative(
    project_id: str, reservation_id: str, db: Session
) -> None:
    reservation = _reservation(db, reservation_id)

    reservation.tax_total = Decimal("-0.01")

    _refuses(db, "ck_reservations_tax_nonneg")


def test_a_buyer_share_cannot_be_zero_or_above_one(
    project_id: str, buyer_id: str, db: Session
) -> None:
    party = db.scalars(
        select(ClientParty).where(ClientParty.client_id == uuid.UUID(buyer_id))
    ).one()

    party.share_fraction = Decimal("0.000000")
    _refuses(db, "ck_client_parties_share_range")

    party = db.scalars(
        select(ClientParty).where(ClientParty.client_id == uuid.UUID(buyer_id))
    ).one()
    party.share_fraction = Decimal("1.500000")
    _refuses(db, "ck_client_parties_share_range")


def test_an_expiry_cannot_fall_before_the_reservation_date(
    project_id: str, reservation_id: str, db: Session
) -> None:
    from datetime import timedelta

    reservation = _reservation(db, reservation_id)

    reservation.expires_on = reservation.reservation_date - timedelta(days=1)

    _refuses(db, "ck_reservations_expiry_after_start")


# --------------------------------------------------------------------------- #
# Adjustment shape
# --------------------------------------------------------------------------- #


def test_a_percentage_discount_cannot_be_stored_as_an_amount(
    project_id: str, reservation_id: str, db: Session
) -> None:
    reservation = _reservation(db, reservation_id)
    db.add(
        ReservationAdjustment(
            project_id=reservation.project_id,
            reservation_id=reservation.id,
            adjustment_type="percentage_discount",
            treatment="price_concession",
            amount=Decimal("5000.00"),
            requested_by_user_id=reservation.created_by_user_id,
        )
    )

    _refuses(db, "ck_reservation_adjustments_shape_ok")


def test_an_adjustment_cannot_be_given_a_treatment_its_type_does_not_have(
    project_id: str, reservation_id: str, db: Session
) -> None:
    """A package cost recorded as a concession would move the contract price."""
    reservation = _reservation(db, reservation_id)
    db.add(
        ReservationAdjustment(
            project_id=reservation.project_id,
            reservation_id=reservation.id,
            adjustment_type="package_cost",
            treatment="price_concession",
            amount=Decimal("5000.00"),
            requested_by_user_id=reservation.created_by_user_id,
        )
    )

    _refuses(db, "ck_reservation_adjustments_treatment_matches_type")


def test_one_adjustment_of_each_type_per_reservation(
    project_id: str, reservation_id: str, db: Session
) -> None:
    reservation = _reservation(db, reservation_id)
    for _ in range(2):
        db.add(
            ReservationAdjustment(
                project_id=reservation.project_id,
                reservation_id=reservation.id,
                adjustment_type="fixed_discount",
                treatment="price_concession",
                amount=Decimal("1000.00"),
                requested_by_user_id=reservation.created_by_user_id,
            )
        )

    _refuses(db, "uq_reservation_adjustments_type")


# --------------------------------------------------------------------------- #
# Legal events
# --------------------------------------------------------------------------- #


def test_a_reversal_must_say_why(project_id: str, active_sale: str, db: Session) -> None:
    events = db.scalars(
        select(SaleLegalEvent).where(SaleLegalEvent.sale_contract_id == uuid.UUID(active_sale))
    ).all()
    original = events[0]
    db.add(
        SaleLegalEvent(
            project_id=original.project_id,
            sale_contract_id=original.sale_contract_id,
            event_type=original.event_type,
            event_date=original.event_date,
            reverses_event_id=original.id,
            entered_by_user_id=original.entered_by_user_id,
        )
    )

    _refuses(db, "ck_sale_legal_events_reversal_has_reason")


def test_one_event_cannot_be_reversed_twice(project_id: str, active_sale: str, db: Session) -> None:
    events = db.scalars(
        select(SaleLegalEvent).where(SaleLegalEvent.sale_contract_id == uuid.UUID(active_sale))
    ).all()
    original = events[-1]
    for _ in range(2):
        db.add(
            SaleLegalEvent(
                project_id=original.project_id,
                sale_contract_id=original.sale_contract_id,
                event_type=original.event_type,
                event_date=original.event_date,
                reverses_event_id=original.id,
                reversal_reason="Entered against the wrong contract",
                entered_by_user_id=original.entered_by_user_id,
            )
        )

    _refuses(db, "uq_sale_legal_events_reverses")


def _draft_copy(db: Session, sale: SaleContract, *, number: str) -> SaleContract:
    """A second contract on the same unit, in draft so it holds nothing.

    Draft is outside the committed-status partial index, so the database allows
    it — which is exactly what makes it a useful second target to point a
    reversal at.
    """
    copy = SaleContract(
        project_id=sale.project_id,
        sale_number=number,
        reservation_id=sale.reservation_id,
        unit_id=sale.unit_id,
        client_id=sale.client_id,
        unit_price_version_id=sale.unit_price_version_id,
        currency_id=sale.currency_id,
        contract_date=sale.contract_date,
        status="draft",
        reference_price_ex_tax=sale.reference_price_ex_tax,
        gross_quoted_price_ex_tax=sale.gross_quoted_price_ex_tax,
        cash_discount_amount=sale.cash_discount_amount,
        seller_credit_amount=sale.seller_credit_amount,
        net_contract_price_ex_tax=sale.net_contract_price_ex_tax,
        seller_cost_total=sale.seller_cost_total,
        effective_net_revenue_snapshot=sale.effective_net_revenue_snapshot,
        tax_total=sale.tax_total,
        buyer_fee_total=sale.buyer_fee_total,
        total_contract_price=sale.total_contract_price,
        reservation_quote_snapshot_json={},
        first_payment_gate_status="not_required",
        created_by_user_id=sale.created_by_user_id,
    )
    db.add(copy)
    db.flush()
    return copy


def test_a_reversal_cannot_withdraw_another_contracts_event(
    project_id: str, active_sale: str, db: Session
) -> None:
    """The reversal key carries the sale and the project, not just the identifier.

    Pointing at an identifier alone proves that some event exists somewhere. A
    legal record should not depend on the service alone for something PostgreSQL
    can express, so a correction that reaches across contracts is refused at the
    database — however the identifiers are shuffled.
    """
    sale = db.scalars(select(SaleContract).where(SaleContract.id == uuid.UUID(active_sale))).one()
    original = db.scalars(
        select(SaleLegalEvent).where(SaleLegalEvent.sale_contract_id == sale.id)
    ).first()
    assert original is not None
    other = _draft_copy(db, sale, number="SALE-900001")

    db.add(
        SaleLegalEvent(
            project_id=other.project_id,
            sale_contract_id=other.id,
            event_type=original.event_type,
            event_date=original.event_date,
            reverses_event_id=original.id,
            reversal_reason="Entered against the wrong contract",
            entered_by_user_id=original.entered_by_user_id,
        )
    )

    _refuses(db, '"reverses"')


def test_a_reversal_on_the_same_contract_is_accepted(
    legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    """The same key that refuses a cross-contract correction admits a real one."""
    timeline = legal_client.get(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events"
    ).json()
    latest = timeline["events"][-1]

    response = legal_client.post(
        f"{sales_url(project_id)}/legal-events/{latest['id']}/reverse",
        json={"reason": "Signature page was unsigned"},
    )

    assert response.status_code == 200, response.text
    assert latest["id"] not in response.json()["effective_event_ids"]
    # Both rows survive: the original and the correction that withdraws it.
    assert len(response.json()["events"]) == len(timeline["events"]) + 1


def test_a_recorded_fee_cannot_lose_its_currency(
    project_id: str, active_sale: str, db: Session
) -> None:
    event = db.scalars(
        select(SaleLegalEvent).where(SaleLegalEvent.sale_contract_id == uuid.UUID(active_sale))
    ).first()
    assert event is not None

    event.fee_amount = Decimal("100.00")

    _refuses(db, "ck_sale_legal_events_fee_has_currency")


# --------------------------------------------------------------------------- #
# Contract identity
# --------------------------------------------------------------------------- #


def test_a_sale_number_is_unique_within_a_project(
    project_id: str, sale_id: str, db: Session
) -> None:
    existing = db.scalars(select(SaleContract).where(SaleContract.id == uuid.UUID(sale_id))).one()
    db.add(
        SaleContract(
            project_id=existing.project_id,
            sale_number=existing.sale_number,
            reservation_id=existing.reservation_id,
            unit_id=existing.unit_id,
            client_id=existing.client_id,
            unit_price_version_id=existing.unit_price_version_id,
            currency_id=existing.currency_id,
            contract_date=existing.contract_date,
            status="draft",
            reference_price_ex_tax=existing.reference_price_ex_tax,
            gross_quoted_price_ex_tax=existing.gross_quoted_price_ex_tax,
            cash_discount_amount=existing.cash_discount_amount,
            seller_credit_amount=existing.seller_credit_amount,
            net_contract_price_ex_tax=existing.net_contract_price_ex_tax,
            seller_cost_total=existing.seller_cost_total,
            effective_net_revenue_snapshot=existing.effective_net_revenue_snapshot,
            tax_total=existing.tax_total,
            buyer_fee_total=existing.buyer_fee_total,
            total_contract_price=existing.total_contract_price,
            reservation_quote_snapshot_json={},
            first_payment_gate_status="not_required",
            created_by_user_id=existing.created_by_user_id,
        )
    )

    _refuses(db, "uq_sale_contracts_number")


def test_an_spa_number_is_unique_within_a_project_where_it_is_present(
    project_id: str, sale_id: str, db: Session
) -> None:
    existing = db.scalars(select(SaleContract).where(SaleContract.id == uuid.UUID(sale_id))).one()
    assert existing.spa_number == "SPA-0001"
    db.add(
        SaleContract(
            project_id=existing.project_id,
            sale_number="SALE-999998",
            spa_number=existing.spa_number,
            reservation_id=existing.reservation_id,
            unit_id=existing.unit_id,
            client_id=existing.client_id,
            unit_price_version_id=existing.unit_price_version_id,
            currency_id=existing.currency_id,
            contract_date=existing.contract_date,
            status="draft",
            reference_price_ex_tax=existing.reference_price_ex_tax,
            gross_quoted_price_ex_tax=existing.gross_quoted_price_ex_tax,
            cash_discount_amount=existing.cash_discount_amount,
            seller_credit_amount=existing.seller_credit_amount,
            net_contract_price_ex_tax=existing.net_contract_price_ex_tax,
            seller_cost_total=existing.seller_cost_total,
            effective_net_revenue_snapshot=existing.effective_net_revenue_snapshot,
            tax_total=existing.tax_total,
            buyer_fee_total=existing.buyer_fee_total,
            total_contract_price=existing.total_contract_price,
            reservation_quote_snapshot_json={},
            first_payment_gate_status="not_required",
            created_by_user_id=existing.created_by_user_id,
        )
    )

    _refuses(db, "uq_sale_contracts_spa_number")
