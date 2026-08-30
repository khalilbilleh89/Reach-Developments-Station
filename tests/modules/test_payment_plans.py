"""Opening a payment plan, and the sale states that permit it.

The boundary this file defends: a schedule is written against frozen contract
terms. A draft contract's price can still move, so it cannot be scheduled; a
cancelled one has nothing left to schedule.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.modules.conftest import plan_detail, plans_url, sales_url


def test_a_plan_opens_on_a_live_contract_with_its_first_draft_version(
    collections_client: TestClient, project_id: str, active_sale: str
) -> None:
    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": active_sale, "name": "Standard terms"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["plan"]["plan_number"] == "PLN-000001"
    assert body["current"]["version"]["version_number"] == 1
    assert body["current"]["version"]["status"] == "draft"
    # No schedule yet, so nothing reconciles and the screen must say why.
    assert body["current"]["reconciliation"]["is_reconciled"] is False
    assert body["current"]["reconciliation"]["installment_count"] == 0


def test_the_first_version_freezes_the_contracts_own_figures(
    collections_client: TestClient, project_id: str, active_sale: str, sales_ops_client: TestClient
) -> None:
    sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()["sale"]
    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": active_sale, "name": "Standard terms"},
    )
    version = created.json()["current"]["version"]
    # Copied from the contract, not recomputed from pricing or from tax rules.
    assert version["contract_value_covered"] == sale["net_contract_price_ex_tax"]
    assert version["tax_total_snapshot"] == sale["tax_total"]
    assert version["buyer_fee_total_snapshot"] == sale["buyer_fee_total"]
    assert version["total_buyer_payable_snapshot"] == sale["total_contract_price"]
    assert version["currency_id"] == sale["currency_id"]


def test_a_plan_may_be_prepared_while_the_contract_awaits_signature(
    collections_client: TestClient, project_id: str, submitted_sale: str
) -> None:
    """Preparation before commercial activation is the point of the two states."""
    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": submitted_sale, "name": "Prepared early"},
    )
    assert created.status_code == 201, created.text


def test_a_draft_contract_cannot_be_scheduled(
    collections_client: TestClient, project_id: str, sale_id: str
) -> None:
    """Its price, tax and fees can still change under whatever was scheduled."""
    refused = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": sale_id, "name": "Too early"},
    )
    assert refused.status_code == 409
    assert "awaiting signature or active" in refused.json()["detail"]


def test_a_sale_gets_at_most_one_plan(
    collections_client: TestClient, project_id: str, active_sale: str, plan_id: str
) -> None:
    second = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": active_sale, "name": "Competing"},
    )
    assert second.status_code == 409
    assert "PLN-000001" in second.json()["detail"]
    assert "new version" in second.json()["detail"]


def test_plan_numbers_run_in_project_sequence(
    collections_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    active_sale: str,
    submitted_sale: str,
) -> None:
    first = collections_client.post(
        plans_url(project_id), json={"sale_contract_id": active_sale, "name": "One"}
    )
    assert first.json()["plan"]["plan_number"] == "PLN-000001"


def test_a_plan_detail_carries_the_sale_the_unit_and_the_buyers_name(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    body = plan_detail(collections_client, project_id, plan_id)
    assert body["sale_number"]
    assert body["unit_reference"]
    assert body["client_display_name"]
    # A payment schedule never needs the buyer's identity document, so the
    # response does not carry one.
    assert "identity_document_number" not in body
    assert "email" not in body


def test_a_plan_carries_no_collected_or_outstanding_figure(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    """PR-MVP-07 owns cash truth. Nothing here may imply it exists yet."""
    plan, _version = active_plan
    body = plan_detail(collections_client, project_id, plan)
    serialised = str(body)
    for forbidden in (
        "paid_amount",
        "balance_due",
        "outstanding",
        "receipt_id",
        "days_overdue",
        "payment_status",
    ):
        assert forbidden not in serialised
