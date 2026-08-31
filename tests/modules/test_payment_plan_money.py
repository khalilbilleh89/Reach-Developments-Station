"""Decimal discipline, charge allocation, and copying a schedule's shape.

Money is never a float here, the currency always comes from the sale, and a
plan copied from another re-derives every amount rather than carrying the
source contract's figures across.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    contract_basis,
    current_version_id,
    fixed_row,
    plan_detail,
    plans_url,
    write_schedule,
)


def test_the_schedule_is_denominated_by_the_sale(
    collections_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    body = plan_detail(collections_client, project_id, plan_id)
    sale = sales_ops_client.get(
        f"/api/v1/projects/{project_id}/sales/contracts/{body['sale_id']}"
    ).json()["sale"]
    assert body["current"]["version"]["currency_id"] == sale["currency_id"]
    assert body["currency_id"] == sale["currency_id"]


def test_an_installment_carries_no_currency_of_its_own(
    collections_client: TestClient, project_id: str, reconciled_plan: tuple[str, str]
) -> None:
    """One plan, one denomination. There is no mixed-currency schedule and no FX."""
    plan_id, _version = reconciled_plan
    for row in plan_detail(collections_client, project_id, plan_id)["current"]["installments"]:
        assert "currency_id" not in row


def test_money_leaves_the_api_as_a_string_not_a_json_number(
    collections_client: TestClient, project_id: str, reconciled_plan: tuple[str, str]
) -> None:
    """A JSON number is a float, and a float is not a contractual amount."""
    plan_id, _version = reconciled_plan
    body = plan_detail(collections_client, project_id, plan_id)
    for row in body["current"]["installments"]:
        for field in ("principal_amount", "tax_amount", "fee_amount", "total_scheduled_amount"):
            assert isinstance(row[field], str), field
    for field in ("scheduled_principal_total", "principal_delta", "scheduled_buyer_total"):
        assert isinstance(body["current"]["reconciliation"][field], str), field


def test_stored_amounts_keep_the_platforms_monetary_scale(
    db: Session, collections_client: TestClient, project_id: str, reconciled_plan: tuple[str, str]
) -> None:
    _plan_id, version_id = reconciled_plan
    rows = db.execute(
        text(
            "SELECT principal_amount, tax_amount, fee_amount FROM payment_plan_installments"
            " WHERE payment_plan_version_id = :v"
        ),
        {"v": version_id},
    ).all()
    assert rows
    for principal, tax, fee in rows:
        for value in (principal, tax, fee):
            assert isinstance(value, Decimal)
            assert -value.as_tuple().exponent <= 2


def test_manual_charges_must_match_the_frozen_totals_exactly(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    tax = Decimal(basis["tax"])
    fee = Decimal(basis["fee"])
    half_tax = (tax / 2).quantize(Decimal("0.01"))
    half_fee = (fee / 2).quantize(Decimal("0.01"))
    rows = [
        fixed_row(1, "0.500000", "2026-03-01", tax_amount=str(half_tax), fee_amount=str(half_fee)),
        fixed_row(
            2,
            "0.500000",
            "2026-06-01",
            tax_amount=str(tax - half_tax),
            fee_amount=str(fee - half_fee),
        ),
    ]
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        rows,
        charge_allocation_mode="manual",
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["reconciliation"]["is_reconciled"] is True


def test_manual_charges_short_by_one_unit_are_shown_not_corrected(
    admin_client: TestClient,
    collections_client: TestClient,
    country_pack_id: str,
    project_id: str,
    plan_id: str,
) -> None:
    """A manual schedule that is a penny out is shown the penny.

    Silently correcting it would overwrite a figure somebody chose on purpose.
    """
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    tax = Decimal(basis["tax"])
    fee = Decimal(basis["fee"])
    rows = [
        fixed_row(
            1,
            "1.000000",
            "2026-03-01",
            tax_amount=str(tax),
            fee_amount=str(max(fee - Decimal("0.01"), Decimal("0.00"))),
        )
    ]
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        rows,
        charge_allocation_mode="manual",
    )
    assert saved.status_code == 200, saved.text
    reconciliation = saved.json()["reconciliation"]
    if fee > 0:
        assert reconciliation["fee_delta"] == "-0.01"
        assert reconciliation["is_reconciled"] is False
        refused = collections_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/submit", json={}
        )
        assert refused.status_code == 409
        assert "Buyer fees is short by 0.01" in refused.json()["detail"]
    else:
        # No buyer fee on this contract, so the manual schedule reconciles.
        assert reconciliation["fee_delta"] == "0.00"


def test_a_manual_tax_that_is_short_blocks_submission(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    tax = Decimal(basis["tax"])
    fee = Decimal(basis["fee"])
    rows = [
        fixed_row(
            1,
            "1.000000",
            "2026-03-01",
            tax_amount=str(max(tax - Decimal("0.01"), Decimal("0.00"))),
            fee_amount=str(fee),
        )
    ]
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        rows,
        charge_allocation_mode="manual",
    )
    reconciliation = saved.json()["reconciliation"]
    if tax > 0:
        assert reconciliation["tax_delta"] == "-0.01"
        refused = collections_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/submit", json={}
        )
        assert refused.status_code == 409
        assert "Tax is short by 0.01" in refused.json()["detail"]


def test_seller_costs_never_appear_as_an_instalment_charge(
    collections_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
) -> None:
    """A seller-borne cost reduces what the sale earns, not what the buyer pays."""
    plan_id, _version = reconciled_plan
    body = plan_detail(collections_client, project_id, plan_id)
    sale = sales_ops_client.get(
        f"/api/v1/projects/{project_id}/sales/contracts/{body['sale_id']}"
    ).json()["sale"]
    scheduled = Decimal(body["current"]["reconciliation"]["scheduled_buyer_total"])
    assert scheduled == Decimal(sale["total_contract_price"])
    assert "seller_cost" not in str(body["current"]["installments"])


def test_a_copied_plan_takes_the_shape_and_re_derives_the_money(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    """The percentages travel; the amounts are recomputed against this sale."""
    plan_id, source_version = active_plan
    source = plan_detail(collections_client, project_id, plan_id)
    source_fractions = [row["principal_fraction"] for row in source["current"]["installments"]]

    revision = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={"change_reason": "Same terms, new version"},
    )
    assert revision.status_code == 201, revision.text
    copied = revision.json()
    assert copied["version"]["origin_type"] == "copied_plan"
    assert copied["version"]["source_version_id"] == source_version
    assert [row["principal_fraction"] for row in copied["installments"]] == source_fractions
    assert copied["reconciliation"]["is_reconciled"] is True
    # No trigger state came across: a copy starts from nothing having happened.
    for row in copied["installments"]:
        assert row["actual_due_date"] is None
        assert row["forecast_due_date"] is None


def test_a_source_version_without_the_copied_origin_is_refused(
    collections_client: TestClient, project_id: str, submitted_sale: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    refused = collections_client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": submitted_sale,
            "name": "Confused",
            "origin_type": "custom",
            "source_version_id": version_id,
        },
    )
    assert refused.status_code == 422
    assert "only applies when the plan is copied" in refused.json()["detail"]


def test_copying_needs_a_settled_schedule_not_a_draft(
    collections_client: TestClient, project_id: str, submitted_sale: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    refused = collections_client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": submitted_sale,
            "name": "Copy of a draft",
            "origin_type": "copied_plan",
            "source_version_id": version_id,
        },
    )
    assert refused.status_code == 409
    assert "approved, active or superseded" in refused.json()["detail"]


def test_both_reservation_treatments_schedule_the_whole_contract(
    collections_client: TestClient, project_id: str, active_sale: str
) -> None:
    """A confirmed deposit attestation is never subtracted from the plan.

    PR-MVP-05's gate says evidence exists, not that money arrived. PR-MVP-07
    decides whether a receipt settles an instalment; until then the schedule
    covers the full principal either way.
    """
    created = collections_client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": active_sale,
            "name": "Deposit shown in the schedule",
            "reservation_treatment": "included_in_schedule",
        },
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan"]["id"]
    version_id = created.json()["current"]["version"]["id"]
    basis = contract_basis(collections_client, project_id, plan_id)

    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.100000", "2026-02-01", label="Reservation amount"),
            fixed_row(2, "0.900000", "2026-08-01"),
        ],
    )
    reconciliation = saved.json()["reconciliation"]
    # The full contract principal, not the contract less a confirmed deposit.
    assert reconciliation["scheduled_principal_total"] == basis["principal"]
    assert reconciliation["is_reconciled"] is True
