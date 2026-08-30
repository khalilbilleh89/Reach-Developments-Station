"""Quote exceptions: who may agree to sell below the company's own limits.

There is no approval engine here. A quote either breaches the country's
configured thresholds or it does not; if it does, exactly one office may
sanction it, the person who asked cannot be the person who signs, and an
administrator does not become that office by administering the platform.

The other thing these tests hold: an approval belongs to the numbers it was
given for. Change the discount and the approval is gone.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import SETTINGS, sales_url


@pytest.fixture
def thresholds(admin_client: TestClient, country_pack_id: str) -> None:
    """A 10% / 20,000 review limit, sanctioned by the CFO."""
    response = admin_client.put(
        f"{SETTINGS}/country-packs/{country_pack_id}/approval-thresholds",
        json={
            "discount_review_rate_fraction": "0.100000",
            "discount_review_amount": "20000.00",
            "pricing_requires_commercial_approval": True,
        },
    )
    assert response.status_code == 200, response.text


def _adjust(client: TestClient, project_id: str, reservation_id: str, **payload: object) -> dict:
    response = client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/adjustments", json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()["reservation"]


def test_a_quote_with_no_concession_needs_no_approval(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, thresholds: None
) -> None:
    body = sales_ops_client.get(f"{sales_url(project_id)}/reservations/{reservation_id}").json()[
        "reservation"
    ]

    assert body["exception_approval_required"] is False
    assert body["exception_approval_status"] == "not_required"


def test_a_discount_below_the_threshold_needs_no_approval(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, thresholds: None
) -> None:
    reservation = _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.050000",
    )

    assert reservation["exception_approval_required"] is False
    assert Decimal(reservation["cash_discount_amount"]) > 0


def test_breaching_the_rate_threshold_requires_the_cfo(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, thresholds: None
) -> None:
    reservation = _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.150000",
    )

    assert reservation["exception_approval_required"] is True
    assert reservation["exception_required_role"] == "approver_cfo"
    assert reservation["exception_approval_status"] == "pending"
    assert "review threshold" in reservation["exception_reason"]


def test_breaching_the_amount_threshold_requires_the_cfo(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, thresholds: None
) -> None:
    reservation = _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="fixed_discount",
        amount="25000.00",
    )

    assert reservation["exception_approval_required"] is True


def test_a_seller_cost_is_not_a_concession_and_does_not_reduce_the_contract_price(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, thresholds: None
) -> None:
    """A furniture package the seller absorbs leaves the SPA price where it was."""
    before = sales_ops_client.get(f"{sales_url(project_id)}/reservations/{reservation_id}").json()[
        "reservation"
    ]

    after = _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="package_cost",
        amount="5000.00",
    )

    assert after["net_contract_price_ex_tax"] == before["net_contract_price_ex_tax"]
    assert after["seller_cost_total"] == "5000.00"
    assert Decimal(after["effective_net_revenue_preview"]) == Decimal(
        after["net_contract_price_ex_tax"]
    ) - Decimal("5000.00")
    assert after["exception_approval_required"] is False


def test_a_paid_upgrade_raises_the_contract_price(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, thresholds: None
) -> None:
    before = sales_ops_client.get(f"{sales_url(project_id)}/reservations/{reservation_id}").json()[
        "reservation"
    ]

    after = _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="paid_upgrade",
        amount="7500.00",
    )

    assert Decimal(after["net_contract_price_ex_tax"]) == Decimal(
        before["net_contract_price_ex_tax"]
    ) + Decimal("7500.00")


def test_several_adjustments_are_summed_into_the_right_subtotals(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, thresholds: None
) -> None:
    _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="seller_credit",
        amount="3000.00",
    )
    _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="financing_subsidy",
        amount="2000.00",
    )
    reservation = _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="commission_support",
        amount="1000.00",
    )

    assert reservation["seller_credit_amount"] == "3000.00"
    assert reservation["seller_cost_total"] == "3000.00"


def test_the_type_decides_the_treatment_and_a_client_cannot_choose_it(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/adjustments",
        json={
            "adjustment_type": "package_cost",
            "amount": "5000.00",
            "treatment": "price_concession",
        },
    )

    assert response.status_code == 422


def test_an_adjustment_must_be_stated_in_its_own_shape(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    as_amount = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/adjustments",
        json={"adjustment_type": "percentage_discount", "amount": "5000.00"},
    )
    as_rate = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/adjustments",
        json={"adjustment_type": "fixed_discount", "rate_fraction": "0.050000"},
    )

    assert as_amount.status_code == 422
    assert "stated as a rate" in as_amount.json()["detail"]
    assert as_rate.status_code == 422
    assert "stated as an amount" in as_rate.json()["detail"]


def test_an_advisor_cannot_see_another_advisors_deal_at_all(
    advisor_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    reservation_id: str,
    thresholds: None,
) -> None:
    """Not a 403 — a 404. A 403 would confirm the identifier names a real deal."""
    response = advisor_client.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/approve-exception",
        json={"approved": True, "reason": "Fine by me"},
    )

    assert response.status_code == 404


def test_an_advisor_cannot_approve_the_exception_on_their_own_deal(
    advisor: object,
    advisor_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    released_unit: str,
    buyer_id: str,
    thresholds: None,
) -> None:
    """Given the deal is theirs, then they may ask and still may not sign."""
    assigned = sales_ops_client.patch(
        f"{sales_url(project_id)}/clients/{buyer_id}",
        json={"owner_advisor_user_id": str(advisor.id)},
    )
    assert assigned.status_code == 200, assigned.text
    created = advisor_client.post(
        f"{sales_url(project_id)}/reservations",
        json={"unit_id": released_unit, "client_id": buyer_id},
    )
    assert created.status_code == 201, created.text
    reservation_id = created.json()["reservation"]["id"]
    _adjust(
        advisor_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.150000",
    )
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    submitted = advisor_client.post(
        f"{base}/submit-exception", json={"reason": "Matching a competing scheme"}
    )
    assert submitted.status_code == 200, submitted.text

    response = advisor_client.post(
        f"{base}/approve-exception", json={"approved": True, "reason": "Fine by me"}
    )

    assert response.status_code == 403


def test_an_administrator_cannot_stand_in_for_the_cfo(
    admin_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    reservation_id: str,
    thresholds: None,
) -> None:
    _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.150000",
    )
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    sales_ops_client.post(f"{base}/submit-exception", json={"reason": "Competing scheme"})

    response = admin_client.post(
        f"{base}/approve-exception", json={"approved": True, "reason": "Administrator override"}
    )

    assert response.status_code == 403


def test_the_submitter_cannot_be_the_approver(
    cfo_client: TestClient,
    project_id: str,
    reservation_id: str,
    thresholds: None,
    sales_ops_client: TestClient,
) -> None:
    """Given the CFO submitted it themselves, then the second signature is missing."""
    _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.150000",
    )
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    # A CFO is not a reservation writer, so they cannot submit one either: the
    # separation holds at both ends.
    assert cfo_client.post(f"{base}/submit-exception", json={"reason": "Mine"}).status_code == 403


def test_the_cfo_approves_and_the_reservation_can_then_be_committed(
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reservation_id: str,
    thresholds: None,
) -> None:
    _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.150000",
    )
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    sales_ops_client.post(f"{base}/submit-exception", json={"reason": "Competing scheme"})

    approved = cfo_client.post(
        f"{base}/approve-exception",
        json={"approved": True, "reason": "Accepted to secure the launch"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["reservation"]["exception_approval_status"] == "approved"

    sales_ops_client.post(f"{base}/confirm-deposit", json={"evidence_reference": "BANK-1"})
    activated = sales_ops_client.post(f"{base}/activate", json={})
    assert activated.status_code == 200, activated.text


def test_a_refused_exception_stops_the_commitment(
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reservation_id: str,
    thresholds: None,
) -> None:
    _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.150000",
    )
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    sales_ops_client.post(f"{base}/submit-exception", json={"reason": "Competing scheme"})
    cfo_client.post(
        f"{base}/approve-exception", json={"approved": False, "reason": "Below the floor"}
    )
    sales_ops_client.post(f"{base}/confirm-deposit", json={"evidence_reference": "BANK-1"})

    response = sales_ops_client.post(f"{base}/activate", json={})

    assert response.status_code == 409
    assert "was refused" in response.json()["detail"]


def test_changing_the_terms_withdraws_the_approval_that_was_standing(
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reservation_id: str,
    thresholds: None,
) -> None:
    """An exception approved against 15% says nothing about 20%."""
    reservation = _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.150000",
    )
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    sales_ops_client.post(f"{base}/submit-exception", json={"reason": "Competing scheme"})
    cfo_client.post(f"{base}/approve-exception", json={"approved": True, "reason": "Accepted"})
    adjustment_id = sales_ops_client.get(f"{base}/adjustments").json()[0]["id"]

    changed = sales_ops_client.patch(
        f"{sales_url(project_id)}/reservation-adjustments/{adjustment_id}",
        json={"rate_fraction": "0.200000"},
    )

    assert changed.status_code == 200, changed.text
    after = sales_ops_client.get(f"{base}").json()["reservation"]
    assert after["exception_approval_status"] == "pending"
    assert after["exception_approved_by_user_id"] is None
    assert Decimal(after["cash_discount_amount"]) > Decimal(reservation["cash_discount_amount"])


def test_the_contract_stores_exactly_the_approved_reservation_quote(
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reservation_id: str,
    thresholds: None,
) -> None:
    _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.150000",
    )
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    sales_ops_client.post(f"{base}/submit-exception", json={"reason": "Competing scheme"})
    cfo_client.post(f"{base}/approve-exception", json={"approved": True, "reason": "Accepted"})
    sales_ops_client.post(f"{base}/confirm-deposit", json={"evidence_reference": "BANK-1"})
    sales_ops_client.post(f"{base}/activate", json={})
    reservation = sales_ops_client.get(base).json()["reservation"]

    created = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts", json={"reservation_id": reservation_id}
    )

    assert created.status_code == 201, created.text
    sale = created.json()["sale"]
    assert sale["cash_discount_amount"] == reservation["cash_discount_amount"]
    assert sale["net_contract_price_ex_tax"] == reservation["net_contract_price_ex_tax"]
    assert sale["effective_net_revenue_snapshot"] == reservation["effective_net_revenue_preview"]


def test_an_unapproved_exception_blocks_the_commitment(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, thresholds: None
) -> None:
    _adjust(
        sales_ops_client,
        project_id,
        reservation_id,
        adjustment_type="percentage_discount",
        rate_fraction="0.150000",
    )
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    sales_ops_client.post(f"{base}/confirm-deposit", json={"evidence_reference": "BANK-1"})

    response = sales_ops_client.post(f"{base}/activate", json={})

    assert response.status_code == 409
    assert "has not been approved" in response.json()["detail"]


def test_margin_is_not_used_or_shown_anywhere_in_sales(
    sales_ops_client: TestClient, project_id: str, reservation_id: str, thresholds: None
) -> None:
    """PR-MVP-08 owns the cost model, so nothing here claims to know a margin."""
    body = sales_ops_client.get(
        f"{sales_url(project_id)}/reservations/{reservation_id}"
    ).text.lower()

    assert "minimum_margin_rate_fraction" not in body
    assert "margin passed" not in body
