"""Cancellation: ending a contract without losing the record of it.

Between "we are cancelling" and "the unit is back" there is a money decision
and, where the registry is involved, a withdrawal. The unit stays committed
until both are done, and it comes back as ``returned`` rather than
``available`` — a unit that carried a contract does not quietly rejoin the
price list at the price the failed deal was struck at.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from tests.modules.conftest import (
    cancellation_terms_payload,
    collections_url,
    confirm_receipt,
    inventory_url,
    record_legal,
    record_receipt,
    sales_url,
)


def _unit(client: TestClient, project_id: str, unit_id: str) -> dict:
    return client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()


def _open_case(client: TestClient, project_id: str, sale_id: str, **overrides: object) -> dict:
    payload: dict[str, object] = {
        "initiated_by_party": "buyer",
        "reason": "Buyer could not complete financing",
        **cancellation_terms_payload(client, project_id, sale_id),
    }
    payload.update(overrides)
    response = client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/cancellation", json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_opening_a_case_moves_the_contract_to_termination_pending(
    sales_ops_client: TestClient, project_id: str, active_sale: str, released_unit: str
) -> None:
    case = _open_case(sales_ops_client, project_id, active_sale)

    assert case["status"] == "notice"
    sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
    assert sale["sale"]["status"] == "termination_pending"
    # The unit is not back on the market while the case is running.
    assert _unit(sales_ops_client, project_id, released_unit)["commercial_status"] == "contracted"


def test_a_cancellation_needs_a_reason_and_a_named_initiator(
    sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    url = f"{sales_url(project_id)}/contracts/{active_sale}/cancellation"

    silent = sales_ops_client.post(url, json={"initiated_by_party": "buyer"})
    invented = sales_ops_client.post(
        url, json={"initiated_by_party": "the weather", "reason": "Rain"}
    )

    assert silent.status_code == 422
    assert invented.status_code == 422


def test_only_one_case_may_be_open_on_a_contract(
    sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    _open_case(sales_ops_client, project_id, active_sale)

    second = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/cancellation",
        json={
            "initiated_by_party": "seller",
            "reason": "Different story",
            **cancellation_terms_payload(sales_ops_client, project_id, active_sale),
        },
    )

    assert second.status_code == 409
    assert "already has an open cancellation" in second.json()["detail"]


def test_money_on_the_way_out_needs_the_cfos_signature(
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    db: Session,
    project_id: str,
    collecting_sale: str,
) -> None:
    receipt = record_receipt(collections_client, project_id, collecting_sale, "20000.00")
    assert receipt.status_code == 201, receipt.text
    confirmed = confirm_receipt(finance_client, project_id, receipt.json()["id"])
    assert confirmed.status_code == 200, confirmed.text
    case = _open_case(
        sales_ops_client,
        project_id,
        collecting_sale,
        **cancellation_terms_payload(
            sales_ops_client, project_id, collecting_sale, deduction_rate_fraction="0.25"
        ),
    )
    assert case["financial_approval_required"] is True
    base = f"{sales_url(project_id)}/cancellations/{case['id']}"

    sales_ops_client.post(f"{base}/advance", json={"to_status": "termination_pending_approval"})
    unapproved = sales_ops_client.post(
        f"{base}/advance", json={"to_status": "ready_for_unit_return"}
    )
    assert unapproved.status_code == 409
    assert "financial terms have not been approved" in unapproved.json()["detail"]

    refused = sales_ops_client.post(
        f"{base}/approve-financial-terms", json={"reason": "Signing my own case"}
    )
    assert refused.status_code == 403

    approved = cfo_client.post(
        f"{base}/approve-financial-terms",
        json={
            "reason": "Deposit forfeited per clause 9",
            "expected_eligible_collected_amount": case["eligible_collected_amount"],
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["financial_approved_at"] is not None
    audit = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity_id == case["id"],
            AuditEvent.action == "sale_cancellation.financial_terms_approved",
        )
    ).one()
    assert audit.after_data["eligible_collected_amount"] == "20000.00"
    assert audit.after_data["deduction_rate_fraction"] == "0.25"
    assert audit.after_data["deduction_amount"] == "5000.00"
    assert audit.after_data["refund_due_amount"] == "15000.00"


def test_the_person_who_opened_the_case_may_not_approve_its_money(
    admin_client: TestClient, cfo_client: TestClient, project_id: str, active_sale: str, db: object
) -> None:
    """A CFO who opened the case is still the maker, and still cannot be the checker."""
    opened = cfo_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/cancellation",
        json={
            "initiated_by_party": "seller",
            "reason": "Developer default process",
            "deduction_rate_fraction": "1",
            "expected_eligible_collected_amount": "0.00",
        },
    )
    # The CFO is not a cancellation writer, so they cannot open one either.
    assert opened.status_code == 403


def test_a_case_can_be_withdrawn_and_the_contract_returns_to_active(
    sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    case = _open_case(sales_ops_client, project_id, active_sale)

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/cancellations/{case['id']}/advance",
        json={"to_status": "withdrawn", "reason": "Buyer found financing after all"},
    )

    assert response.status_code == 200, response.text
    sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
    assert sale["sale"]["status"] == "active"


def test_a_registered_contract_cannot_return_the_unit_before_the_registry_is_unwound(
    sales_ops_client: TestClient, legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    for event_type, event_date in (
        ("land_registry_lodged", "2026-02-10"),
        ("registered", "2026-02-20"),
    ):
        record_legal(legal_client, project_id, active_sale, event_type, event_date)
    case = _open_case(sales_ops_client, project_id, active_sale)
    assert case["legal_withdrawal_required"] is True
    assert case["legal_withdrawal_status"] == "pending"
    base = f"{sales_url(project_id)}/cancellations/{case['id']}"

    sales_ops_client.post(f"{base}/advance", json={"to_status": "termination_pending_approval"})
    blocked = sales_ops_client.post(f"{base}/advance", json={"to_status": "ready_for_unit_return"})

    assert blocked.status_code == 409
    assert "registry withdrawal" in blocked.json()["detail"]


def test_recording_the_withdrawal_lets_the_case_proceed(
    sales_ops_client: TestClient, legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    for event_type, event_date in (
        ("land_registry_lodged", "2026-02-10"),
        ("registered", "2026-02-20"),
    ):
        record_legal(legal_client, project_id, active_sale, event_type, event_date)
    case = _open_case(sales_ops_client, project_id, active_sale)
    base = f"{sales_url(project_id)}/cancellations/{case['id']}"
    sales_ops_client.post(f"{base}/advance", json={"to_status": "termination_pending_approval"})
    sales_ops_client.post(f"{base}/advance", json={"to_status": "withdrawal_pending"})

    for event_type, event_date in (
        ("withdrawal_started", "2026-03-01"),
        ("withdrawn", "2026-03-05"),
    ):
        record_legal(legal_client, project_id, active_sale, event_type, event_date)

    response = sales_ops_client.post(f"{base}/advance", json={"to_status": "ready_for_unit_return"})

    assert response.status_code == 200, response.text
    assert response.json()["legal_withdrawal_status"] == "completed"


def test_completing_a_cancellation_returns_the_unit_and_withdraws_its_pricing(
    sales_ops_client: TestClient, project_id: str, active_sale: str, released_unit: str
) -> None:
    case = _open_case(sales_ops_client, project_id, active_sale)
    base = f"{sales_url(project_id)}/cancellations/{case['id']}"
    sales_ops_client.post(f"{base}/advance", json={"to_status": "termination_pending_approval"})
    sales_ops_client.post(f"{base}/advance", json={"to_status": "ready_for_unit_return"})

    response = sales_ops_client.post(f"{base}/complete", json={})

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
    assert sale["sale"]["status"] == "cancelled"
    unit = _unit(sales_ops_client, project_id, released_unit)
    # Returned, never available: the unit is repriced before it is remarketed.
    assert unit["commercial_status"] == "returned"
    assert unit["pricing_approved"] is False


def test_a_returned_unit_cannot_be_reserved_again_until_it_is_repriced(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    active_sale: str,
    released_unit: str,
    buyer_id: str,
) -> None:
    case = _open_case(sales_ops_client, project_id, active_sale)
    base = f"{sales_url(project_id)}/cancellations/{case['id']}"
    sales_ops_client.post(f"{base}/advance", json={"to_status": "termination_pending_approval"})
    sales_ops_client.post(f"{base}/advance", json={"to_status": "ready_for_unit_return"})
    sales_ops_client.post(f"{base}/complete", json={})

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={"unit_id": released_unit, "client_id": buyer_id},
    )

    assert response.status_code == 409
    assert "requires repricing" in response.json()["detail"]


def test_a_cancellation_records_a_refund_due_and_never_a_refund_paid(
    sales_ops_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
) -> None:
    receipt = record_receipt(collections_client, project_id, collecting_sale, "15000.00")
    assert receipt.status_code == 201, receipt.text
    confirmed = confirm_receipt(finance_client, project_id, receipt.json()["id"])
    assert confirmed.status_code == 200, confirmed.text
    case = _open_case(
        sales_ops_client,
        project_id,
        collecting_sale,
        **cancellation_terms_payload(sales_ops_client, project_id, collecting_sale),
    )

    assert case["refund_due_amount"] == "15000.00"
    assert "refund_paid_amount" not in case
    # And the API refuses to be told about one.
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation",
        json={
            "initiated_by_party": "buyer",
            "reason": "Second attempt",
            "refund_paid_amount": "15000.00",
        },
    )
    assert response.status_code == 422


def test_a_cancellation_has_no_delete_route(
    sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    case = _open_case(sales_ops_client, project_id, active_sale)

    response = sales_ops_client.delete(f"{sales_url(project_id)}/cancellations/{case['id']}")

    assert response.status_code in {404, 405}


@pytest.mark.parametrize(
    ("rate", "deduction", "refund"),
    (("0", "0.00", "20000.00"), ("0.10", "2000.00", "18000.00"), ("1", "20000.00", "0.00")),
)
def test_preview_derives_full_partial_and_forfeited_refunds_from_confirmed_cash(
    sales_ops_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
    rate: str,
    deduction: str,
    refund: str,
) -> None:
    receipt = record_receipt(collections_client, project_id, collecting_sale, "20000.00")
    assert receipt.status_code == 201, receipt.text
    assert confirm_receipt(finance_client, project_id, receipt.json()["id"]).status_code == 200

    preview = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation-preview",
        json={"deduction_rate_fraction": rate},
    )

    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["eligible_collected_amount"] == "20000.00"
    assert body["deduction_amount"] == deduction
    assert body["refund_due_amount"] == refund
    assert Decimal(body["deduction_amount"]) + Decimal(body["refund_due_amount"]) == Decimal(
        body["eligible_collected_amount"]
    )


def test_zero_or_unconfirmed_cash_never_creates_a_fake_refund(
    sales_ops_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    collecting_sale: str,
) -> None:
    recorded = record_receipt(collections_client, project_id, collecting_sale, "10000.00")
    assert recorded.status_code == 201, recorded.text

    preview = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation-preview",
        json={"deduction_rate_fraction": "0.25"},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["eligible_collected_amount"] == "0.00"
    assert preview.json()["deduction_amount"] == "0.00"
    assert preview.json()["refund_due_amount"] == "0.00"

    case = _open_case(
        sales_ops_client,
        project_id,
        collecting_sale,
        deduction_rate_fraction="0.25",
        expected_eligible_collected_amount="0.00",
    )
    assert case["financial_approval_required"] is False


def test_reversed_receipt_is_excluded_but_unapplied_confirmed_cash_is_included(
    sales_ops_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
) -> None:
    standing = record_receipt(collections_client, project_id, collecting_sale, "10000.00")
    reversed_receipt = record_receipt(collections_client, project_id, collecting_sale, "3000.00")
    for receipt in (standing, reversed_receipt):
        assert receipt.status_code == 201, receipt.text
        assert confirm_receipt(finance_client, project_id, receipt.json()["id"]).status_code == 200
    reversed_response = finance_client.post(
        f"{collections_url(project_id)}/receipts/{reversed_receipt.json()['id']}/reverse",
        json={"reason": "Bank returned the transfer"},
    )
    assert reversed_response.status_code == 200, reversed_response.text

    preview = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation-preview",
        json={"deduction_rate_fraction": "0"},
    )
    assert preview.status_code == 200, preview.text
    # No allocation was created for the standing receipt. Cash, not allocations, is the basis.
    assert preview.json()["eligible_collected_amount"] == "10000.00"


def test_cancellation_money_uses_standard_half_up_rounding(
    sales_ops_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
) -> None:
    receipt = record_receipt(collections_client, project_id, collecting_sale, "0.05")
    assert receipt.status_code == 201, receipt.text
    assert confirm_receipt(finance_client, project_id, receipt.json()["id"]).status_code == 200
    preview = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation-preview",
        json={"deduction_rate_fraction": "0.333333"},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["deduction_amount"] == "0.02"
    assert preview.json()["refund_due_amount"] == "0.03"


@pytest.mark.parametrize("rate", ("-0.000001", "1.000001", "NaN"))
def test_invalid_deduction_percentage_is_rejected(
    sales_ops_client: TestClient, project_id: str, active_sale: str, rate: str
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/cancellation-preview",
        json={"deduction_rate_fraction": rate},
    )
    assert response.status_code == 422


def test_opening_refuses_a_stale_cash_preview(
    sales_ops_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
) -> None:
    first = record_receipt(collections_client, project_id, collecting_sale, "10000.00")
    assert confirm_receipt(finance_client, project_id, first.json()["id"]).status_code == 200
    stale = cancellation_terms_payload(sales_ops_client, project_id, collecting_sale)
    second = record_receipt(collections_client, project_id, collecting_sale, "5000.00")
    assert confirm_receipt(finance_client, project_id, second.json()["id"]).status_code == 200

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation",
        json={
            "initiated_by_party": "buyer",
            "reason": "Buyer withdrew",
            **stale,
        },
    )
    assert response.status_code == 409
    assert "Confirmed cash changed" in response.json()["detail"]


def test_approval_refuses_terms_if_cash_changed_after_opening(
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
) -> None:
    first = record_receipt(collections_client, project_id, collecting_sale, "10000.00")
    pending = record_receipt(collections_client, project_id, collecting_sale, "5000.00")
    assert confirm_receipt(finance_client, project_id, first.json()["id"]).status_code == 200
    case = _open_case(sales_ops_client, project_id, collecting_sale)
    assert confirm_receipt(finance_client, project_id, pending.json()["id"]).status_code == 200

    response = cfo_client.post(
        f"{sales_url(project_id)}/cancellations/{case['id']}/approve-financial-terms",
        json={
            "reason": "Reviewed the original terms",
            "expected_eligible_collected_amount": case["eligible_collected_amount"],
        },
    )
    assert response.status_code == 409
    assert "Confirmed cash changed" in response.json()["detail"]
