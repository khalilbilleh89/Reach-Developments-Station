"""Confirmed gross receipts against SPA payable, independent of allocations."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.collections.ledger import collected_percentage
from tests.modules.conftest import (
    add_sale_tax,
    at,
    backdate,
    collection_account,
    collections_url,
    confirm_receipt,
    record_receipt,
    refund_buyer,
    sales_url,
)


@pytest.mark.parametrize(
    ("cash", "payable", "expected"),
    [
        ("0", "0", None),
        ("0", "100", "0.00"),
        ("1", "32", "3.13"),
        ("125", "100", "125.00"),
        ("60000", "120000", "50.00"),
    ],
)
def test_percentage_rounding_zero_and_overpayment(
    cash: str, payable: str, expected: str | None
) -> None:
    result = collected_percentage(confirmed_receipts=Decimal(cash), spa_payable=Decimal(payable))
    assert result == (Decimal(expected) if expected is not None else None)


def test_confirmation_reversal_and_historical_reads_without_a_schedule(
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    active_sale: str,
    db: Session,
) -> None:
    before = collection_account(collections_client, project_id, active_sale)
    payable = Decimal(before["spa_total_payable"])
    assert before["active_payment_plan_id"] is None
    assert before["collected_percentage"] == "0.00"
    amount = str((payable / 2).quantize(Decimal("0.01")))
    recorded = record_receipt(collections_client, project_id, active_sale, amount)
    assert recorded.status_code == 201, recorded.text
    receipt_id = recorded.json()["id"]
    assert (
        collection_account(collections_client, project_id, active_sale)["collected_percentage"]
        == "0.00"
    )
    assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
    after = collection_account(collections_client, project_id, active_sale)
    assert after["collected_percentage"] == "50.00"
    assert after["unapplied_cash"] == amount
    assert after["allocated_total"] == "0.00"
    backdate(
        db,
        table="collection_receipts",
        row_id=receipt_id,
        recorded_at=at("2026-02-01"),
        confirmed_at=at("2026-02-02"),
    )
    assert (
        collection_account(collections_client, project_id, active_sale, as_of="2026-02-01")[
            "collected_percentage"
        ]
        == "0.00"
    )
    assert (
        collection_account(collections_client, project_id, active_sale, as_of="2026-02-02")[
            "collected_percentage"
        ]
        == "50.00"
    )
    reversed_row = finance_client.post(
        f"{collections_url(project_id)}/receipts/{receipt_id}/reverse",
        json={"reason": "Duplicate bank entry"},
    )
    assert reversed_row.status_code == 200, reversed_row.text
    assert (
        collection_account(collections_client, project_id, active_sale)["collected_percentage"]
        == "0.00"
    )
    assert (
        collection_account(collections_client, project_id, active_sale, as_of="2026-02-02")[
            "collected_percentage"
        ]
        == "50.00"
    )


def test_refunds_are_separate_from_gross_collection_percentage(
    collections_client: TestClient,
    finance_client: TestClient,
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    recorded = record_receipt(collections_client, project_id, active_sale, "10000.00")
    assert recorded.status_code == 201
    assert confirm_receipt(finance_client, project_id, recorded.json()["id"]).status_code == 200
    before = collection_account(collections_client, project_id, active_sale)
    refund_buyer(
        sales_ops_client,
        cfo_client,
        collections_client,
        finance_client,
        project_id,
        active_sale,
        amount="1000.00",
    )
    after = collection_account(collections_client, project_id, active_sale)
    assert after["confirmed_receipts_total"] == "10000.00"
    assert after["refund_confirmed_total"] == "1000.00"
    assert after["collected_percentage"] == before["collected_percentage"]
    sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()["sale"]
    assert after["spa_total_payable"] == sale["total_contract_price"]


def test_percentage_uses_spa_tax_and_buyer_fees(
    admin_client: TestClient,
    sales_ops_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    country_pack_id: str,
    reservation_id: str,
) -> None:
    add_sale_tax(admin_client, country_pack_id)
    reservation_url = f"{sales_url(project_id)}/reservations/{reservation_id}"
    recalculated = sales_ops_client.post(
        f"{reservation_url}/recalculate", json={"buyer_fee_total": "1200.00"}
    )
    assert recalculated.status_code == 200, recalculated.text
    reservation = recalculated.json()["reservation"]
    assert Decimal(reservation["tax_total"]) > 0
    assert reservation["buyer_fee_total"] == "1200.00"
    confirmed = sales_ops_client.post(
        f"{reservation_url}/confirm-deposit", json={"evidence_reference": "SPA-TAX-FEES"}
    )
    assert confirmed.status_code == 200, confirmed.text
    activated = sales_ops_client.post(f"{reservation_url}/activate", json={})
    assert activated.status_code == 200, activated.text
    created = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": reservation_id}
    )
    assert created.status_code == 201, created.text
    sale = created.json()["sale"]
    sale_id = sale["id"]
    submitted = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={}
    )
    assert submitted.status_code == 200, submitted.text
    payable = Decimal(sale["total_contract_price"])
    assert payable == Decimal(reservation["total_buyer_payable"])
    recorded = record_receipt(collections_client, project_id, sale_id, str(payable / 2))
    assert recorded.status_code == 201, recorded.text
    assert confirm_receipt(finance_client, project_id, recorded.json()["id"]).status_code == 200
    summary = collection_account(collections_client, project_id, sale_id)
    assert Decimal(summary["spa_total_payable"]) == payable
    assert summary["collected_percentage"] == "50.00"
