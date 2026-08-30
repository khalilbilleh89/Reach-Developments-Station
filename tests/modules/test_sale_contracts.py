"""Sale contracts: the moment a commitment becomes an agreement.

The contract is where the company's word is given, so these tests are about what
must be true before that happens and what must never change afterwards: the
quote crosses over unchanged, the buyers are frozen as they signed, the unit's
commitment moves in one indivisible step, and no route can restate a price.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.modules.conftest import add_sale_tax, inventory_url, record_legal, sales_url


def _sale(client: TestClient, project_id: str, sale_id: str) -> dict:
    response = client.get(f"{sales_url(project_id)}/contracts/{sale_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _unit_status(client: TestClient, project_id: str, unit_id: str) -> str:
    return client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()["commercial_status"]


def test_a_contract_copies_the_reservations_frozen_quote_exactly(
    sales_ops_client: TestClient, project_id: str, active_reservation: str, sale_id: str
) -> None:
    reservation = sales_ops_client.get(
        f"{sales_url(project_id)}/reservations/{active_reservation}"
    ).json()["reservation"]
    sale = _sale(sales_ops_client, project_id, sale_id)["sale"]

    assert sale["net_contract_price_ex_tax"] == reservation["net_contract_price_ex_tax"]
    assert sale["total_contract_price"] == reservation["total_buyer_payable"]
    assert sale["seller_cost_total"] == reservation["seller_cost_total"]
    assert sale["unit_price_version_id"] == reservation["unit_price_version_id"]


def test_a_draft_contract_does_not_take_the_unit_from_the_reservation(
    sales_ops_client: TestClient, project_id: str, sale_id: str, released_unit: str
) -> None:
    assert _sale(sales_ops_client, project_id, sale_id)["sale"]["status"] == "draft"
    assert _unit_status(sales_ops_client, project_id, released_unit) == "reserved"


def test_a_contract_cannot_be_drawn_up_without_a_live_reservation(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    """The reservation is still in preparation, so there is nothing to convert."""
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": reservation_id}
    )

    assert response.status_code == 409
    assert "live reservation" in response.json()["detail"]


def test_submission_moves_the_commitment_in_one_step(
    sales_ops_client: TestClient,
    project_id: str,
    active_reservation: str,
    submitted_sale: str,
    released_unit: str,
) -> None:
    """The reservation converts, the contract takes over, the unit never looks free."""
    reservation = sales_ops_client.get(
        f"{sales_url(project_id)}/reservations/{active_reservation}"
    ).json()

    assert reservation["reservation"]["status"] == "converted"
    assert _sale(sales_ops_client, project_id, submitted_sale)["sale"]["status"] == (
        "signature_pending"
    )
    assert _unit_status(sales_ops_client, project_id, released_unit) == "contract_pending"
    assert "available" not in [event["to_status"] for event in reservation["events"]]


def test_submission_freezes_the_buyers_as_they_signed(
    sales_ops_client: TestClient, project_id: str, submitted_sale: str, buyer_id: str
) -> None:
    """Given the client master is corrected afterwards, then the contract does not change."""
    before = _sale(sales_ops_client, project_id, submitted_sale)["parties"]
    assert [party["name_as_identification"] for party in before] == ["Rana Haddad"]

    parties = sales_ops_client.get(f"{sales_url(project_id)}/clients/{buyer_id}/parties").json()
    corrected = sales_ops_client.patch(
        f"{sales_url(project_id)}/client-parties/{parties[0]['id']}",
        json={"name_as_identification": "Rana Y. Haddad"},
    )
    assert corrected.status_code == 200, corrected.text

    after = _sale(sales_ops_client, project_id, submitted_sale)["parties"]
    assert [party["name_as_identification"] for party in after] == ["Rana Haddad"]


def test_a_submitted_contracts_commercial_terms_cannot_be_edited(
    sales_ops_client: TestClient, project_id: str, submitted_sale: str
) -> None:
    frozen = sales_ops_client.patch(
        f"{sales_url(project_id)}/contracts/{submitted_sale}", json={"spa_number": "SPA-9999"}
    )
    invented = sales_ops_client.patch(
        f"{sales_url(project_id)}/contracts/{submitted_sale}",
        json={"net_contract_price_ex_tax": "1.00"},
    )

    assert frozen.status_code == 409
    # There is no such field on the request model at all, so the typo and the
    # deliberate attempt get the same answer.
    assert invented.status_code == 422


def test_activation_needs_both_signatures_on_the_legal_timeline(
    sales_ops_client: TestClient, legal_client: TestClient, project_id: str, submitted_sale: str
) -> None:
    refused = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/activate", json={}
    )
    assert refused.status_code == 409
    assert "signature events" in refused.json()["detail"]

    for event_type, event_date in (
        ("spa_drafted", "2026-02-01"),
        ("spa_issued", "2026-02-02"),
        ("buyer_signed", "2026-02-03"),
        ("seller_signed", "2026-02-04"),
    ):
        record_legal(legal_client, project_id, submitted_sale, event_type, event_date)

    allowed = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/activate", json={}
    )
    assert allowed.status_code == 200, allowed.text


def test_activation_contracts_the_unit(
    sales_ops_client: TestClient, project_id: str, active_sale: str, released_unit: str
) -> None:
    assert _sale(sales_ops_client, project_id, active_sale)["sale"]["status"] == "active"
    assert _unit_status(sales_ops_client, project_id, released_unit) == "contracted"


def test_the_first_payment_gate_blocks_activation_until_it_is_satisfied(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_reservation: str,
) -> None:
    created = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts",
        json={"reservation_id": active_reservation, "first_payment_required_amount": "10000.00"},
    )
    assert created.status_code == 201, created.text
    sale_id = created.json()["sale"]["id"]
    assert created.json()["sale"]["first_payment_gate_status"] == "pending"

    submitted = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={}
    )
    assert submitted.status_code == 200, submitted.text
    for event_type, event_date in (
        ("spa_drafted", "2026-02-01"),
        ("spa_issued", "2026-02-02"),
        ("buyer_signed", "2026-02-03"),
        ("seller_signed", "2026-02-04"),
    ):
        record_legal(legal_client, project_id, sale_id, event_type, event_date)

    blocked = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/activate", json={}
    )
    assert blocked.status_code == 409
    assert "first payment" in blocked.json()["detail"]

    waived = cfo_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/waive-first-payment",
        json={"reason": "Corporate buyer on quarterly terms"},
    )
    assert waived.status_code == 200, waived.text

    activated = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/activate", json={}
    )
    assert activated.status_code == 200, activated.text


def test_sales_operations_may_not_waive_a_first_payment(
    sales_ops_client: TestClient, project_id: str, submitted_sale: str, db: Session
) -> None:
    from app.modules.sales.models import SaleContract

    sale = db.scalars(select(SaleContract).where(SaleContract.id == submitted_sale)).one()
    sale.first_payment_required_amount = Decimal("1000.00")
    sale.first_payment_gate_status = "pending"
    db.commit()

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/waive-first-payment",
        json={"reason": "Trying it on"},
    )

    assert response.status_code == 403


def _commit_and_submit(client: TestClient, project_id: str, reservation_id: str) -> str:
    """Take a reservation in preparation all the way to a submitted contract."""
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    confirmed = client.post(f"{base}/confirm-deposit", json={"evidence_reference": "BANK-REF-7"})
    assert confirmed.status_code == 200, confirmed.text
    activated = client.post(f"{base}/activate", json={})
    assert activated.status_code == 200, activated.text
    created = client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": reservation_id}
    )
    assert created.status_code == 201, created.text
    sale_id = created.json()["sale"]["id"]
    submitted = client.post(f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    return sale_id


def test_the_contract_freezes_the_tax_observation_it_was_signed_under(
    admin_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    country_pack_id: str,
    reservation_id: str,
) -> None:
    """Given a sale tax exists, then its rate is copied onto the contract."""
    add_sale_tax(admin_client, country_pack_id)
    recalculated = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/recalculate", json={}
    )
    assert recalculated.status_code == 200, recalculated.text
    assert Decimal(recalculated.json()["reservation"]["tax_total"]) > 0

    sale_id = _commit_and_submit(sales_ops_client, project_id, reservation_id)

    lines = _sale(sales_ops_client, project_id, sale_id)["tax_lines"]
    assert [line["tax_code"] for line in lines] == ["VAT"]
    assert lines[0]["rate_fraction"] == "0.160000"
    assert Decimal(lines[0]["tax_amount"]) == Decimal(
        _sale(sales_ops_client, project_id, sale_id)["sale"]["tax_total"]
    )


def test_a_later_tax_change_does_not_restate_a_signed_contract(
    admin_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    country_pack_id: str,
    reservation_id: str,
) -> None:
    """The rate moves next quarter. The SPA still says what it said."""
    rule_id = add_sale_tax(admin_client, country_pack_id)
    sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/recalculate", json={}
    )
    sale_id = _commit_and_submit(sales_ops_client, project_id, reservation_id)
    before = _sale(sales_ops_client, project_id, sale_id)["sale"]["tax_total"]

    changed = admin_client.patch(
        f"/api/v1/settings/tax-rules/{rule_id}",
        json={"rate_fraction": "0.200000", "reason": "Budget change"},
    )
    assert changed.status_code == 200, changed.text

    after = _sale(sales_ops_client, project_id, sale_id)
    assert after["sale"]["tax_total"] == before
    assert after["tax_lines"][0]["rate_fraction"] == "0.160000"


def test_a_sale_contract_has_no_delete_route(
    sales_ops_client: TestClient, project_id: str, sale_id: str
) -> None:
    response = sales_ops_client.delete(f"{sales_url(project_id)}/contracts/{sale_id}")

    assert response.status_code in {404, 405}
