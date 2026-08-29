"""Quote preview and bulk pricing.

A quote preview is arithmetic on a screen. It creates no client, no reservation
and no sale — PR-MVP-05 owns the transaction that freezes any of it — and its
one job is to keep two things apart that a spreadsheet always merges: a **price
concession**, which reduces what the buyer contracts to pay, and a **seller
cost**, which does not.

Bulk pricing exists because 247 units is the reference development and pricing
them one request at a time pushes the work back into the spreadsheet this system
replaces. It is all-or-nothing: a half-approved price list is one nobody can
publish.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.inventory.models import Unit
from app.modules.pricing.models import UnitPriceVersion
from tests.modules.conftest import (
    SETTINGS,
    approve_areas,
    inventory_url,
    pricing_url,
    unit_payload,
)


def _quote(client: TestClient, project_id: str, unit_id: str, **body: object) -> dict:
    response = client.post(f"{pricing_url(project_id)}/units/{unit_id}/quote-preview", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Quote preview
# --------------------------------------------------------------------------- #


def test_a_quote_needs_a_live_price(
    finance_client: TestClient, project_id: str, unit_id: str, active_configuration: str
) -> None:
    response = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/quote-preview", json={}
    )

    assert response.status_code == 409
    assert "no active price" in response.json()["detail"]


def test_a_quote_with_no_terms_is_the_approved_price(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    quote = _quote(finance_client, project_id, unit_id)

    assert quote["approved_reference_price_ex_tax"] == "165000.00"
    assert quote["gross_quoted_price_ex_tax"] == "165000.00"
    assert quote["net_contract_price_ex_tax"] == "165000.00"
    assert quote["effective_net_revenue_preview"] == "165000.00"


def test_a_percentage_discount_reduces_the_contract_price(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    quote = _quote(finance_client, project_id, unit_id, discount_fraction="0.050000")

    assert quote["cash_discount"] == "8250.00"
    assert quote["net_contract_price_ex_tax"] == "156750.00"


def test_a_fixed_discount_and_a_seller_credit_both_reduce_the_contract(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    quote = _quote(
        finance_client,
        project_id,
        unit_id,
        discount_amount="5000.00",
        seller_credit="2000.00",
    )

    assert quote["cash_discount"] == "5000.00"
    assert quote["seller_credit"] == "2000.00"
    assert quote["net_contract_price_ex_tax"] == "158000.00"


def test_a_furniture_package_does_not_reduce_the_contract_price(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    """The distinction this whole endpoint exists to preserve.

    A 5,000 package on a 165,000 unit leaves the contract at 165,000 and the
    seller's net revenue at 160,000. Netting it off the contract price would
    produce a number nobody agreed to and a commission base that is wrong.
    """
    quote = _quote(finance_client, project_id, unit_id, package_cost="5000.00")

    assert quote["net_contract_price_ex_tax"] == "165000.00"
    assert quote["seller_package_cost"] == "5000.00"
    assert quote["seller_cost_total"] == "5000.00"
    assert quote["effective_net_revenue_preview"] == "160000.00"


def test_every_seller_cost_lands_on_the_seller_side(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    quote = _quote(
        finance_client,
        project_id,
        unit_id,
        package_cost="1000.00",
        upgrade_allowance_cost="2000.00",
        commission_support="3000.00",
        financing_subsidy="4000.00",
        extended_terms_npv_cost="5000.00",
    )

    assert quote["net_contract_price_ex_tax"] == "165000.00"
    assert quote["seller_cost_total"] == "15000.00"
    assert quote["effective_net_revenue_preview"] == "150000.00"


def test_a_paid_upgrade_raises_the_quoted_price(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    """An upgrade the buyer pays for is a price addition, not a seller cost."""
    quote = _quote(finance_client, project_id, unit_id, paid_upgrade_amount="8000.00")

    assert quote["gross_quoted_price_ex_tax"] == "173000.00"
    assert quote["effective_net_revenue_preview"] == "173000.00"


def test_a_payment_plan_adjustment_moves_the_quoted_price(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    quote = _quote(finance_client, project_id, unit_id, payment_plan_adjustment_fraction="0.030000")

    assert quote["payment_plan_price_adjustment"] == "4950.00"
    assert quote["gross_quoted_price_ex_tax"] == "169950.00"


def test_tax_is_charged_on_what_the_buyer_contracts_to_pay(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    country_pack_id: str,
    priced_unit: str,
) -> None:
    """Given a configured sale tax, then it is computed on the contract price.

    Never on the seller's net revenue: a package the seller absorbs does not
    reduce the consideration the buyer is taxed on, and computing it the other
    way would understate the tax and fold a seller cost into a buyer figure.
    """
    created = admin_client.post(
        f"{SETTINGS}/country-packs/{country_pack_id}/tax-rules",
        json={
            "tax_code": "VAT",
            "label": "Value added tax",
            "applies_to": "sale",
            "calculation_basis": "net_amount",
            "rate_fraction": "0.160000",
            "valid_from": "2020-01-01",
        },
    )
    assert created.status_code == 201, created.text

    quote = _quote(finance_client, project_id, unit_id, package_cost="5000.00")

    assert quote["tax_status"] == "configured"
    assert quote["taxes"][0]["tax_code"] == "VAT"
    assert quote["tax_total"] == "26400.00"
    assert quote["total_buyer_payable_preview"] == "191400.00"


def test_an_unconfigured_tax_is_said_rather_than_guessed(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    """An invented rate on a quote is worse than an absent one; somebody believes it."""
    quote = _quote(finance_client, project_id, unit_id)

    assert quote["tax_status"] == "not_configured"
    assert quote["taxes"] == []
    assert quote["tax_total"] == "0.00"
    assert quote["total_buyer_payable_preview"] == "165000.00"


def test_a_discount_past_the_country_threshold_is_flagged_for_approval(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    country_pack_id: str,
    priced_unit: str,
) -> None:
    """Read from the approval thresholds PR-MVP-01 already governs, and not stored.

    PR-MVP-05 owns the actual sale exception, with its recorded decision. This
    is a warning on a preview, which is all it can honestly be.
    """
    admin_client.put(
        f"{SETTINGS}/country-packs/{country_pack_id}/approval-thresholds",
        json={
            "discount_review_rate_fraction": "0.050000",
            "pricing_requires_commercial_approval": True,
        },
    )

    quote = _quote(finance_client, project_id, unit_id, discount_fraction="0.100000")

    assert quote["approval_required"] is True
    assert "above the" in quote["approval_reason"]
    assert quote["required_role"] == "approver_cfo"


def test_a_quote_writes_nothing(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str, db: Session
) -> None:
    """No client, no reservation, no sale, and not even a price version."""
    before = len(db.scalars(select(UnitPriceVersion)).all())

    _quote(finance_client, project_id, unit_id, discount_fraction="0.100000")

    db.expire_all()
    assert len(db.scalars(select(UnitPriceVersion)).all()) == before
    assert db.scalars(select(Unit)).one().pricing_approved is True


def test_concessions_may_not_exceed_the_price(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    response = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/quote-preview",
        json={"discount_amount": "200000.00"},
    )

    assert response.status_code == 422
    assert "exceed the price" in response.json()["detail"]


def test_a_negative_discount_is_refused_by_the_contract(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    """A negative discount is a price increase wearing the wrong name."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/quote-preview",
        json={"discount_amount": "-5000.00"},
    )

    assert response.status_code == 422


def test_a_sales_advisor_may_quote_a_unit_they_can_see(
    advisor_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    quote = _quote(advisor_client, project_id, unit_id, discount_fraction="0.020000")

    assert quote["net_contract_price_ex_tax"] == "161700.00"


def test_a_sales_advisor_cannot_quote_a_unit_in_a_hidden_phase(
    admin_client: TestClient,
    advisor_client: TestClient,
    advisor: User,
    project_id: str,
    unit_id: str,
    priced_unit: str,
) -> None:
    """Nothing leaks: not the price, not the reference, not that it exists."""
    from tests.factories import client_for
    from tests.modules.conftest import PROJECTS

    admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{advisor.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    client = client_for(advisor.email)

    response = client.post(f"{pricing_url(project_id)}/units/{unit_id}/quote-preview", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "Unit not found."


# --------------------------------------------------------------------------- #
# Bulk pricing
# --------------------------------------------------------------------------- #


def _units(admin_client: TestClient, project_id: str, floor_id: str, count: int) -> list[str]:
    return [
        admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(
                floor_id, unit_number=f"2{index:02d}", unit_reference=f"B1-2{index:02d}"
            ),
        ).json()["id"]
        for index in range(count)
    ]


def test_bulk_generation_drafts_a_price_for_every_selected_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    floor_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    units = _units(admin_client, project_id, floor_id, 12)
    for unit in units:
        approve_areas(admin_client, project_id, unit, area_types)

    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/generate",
        json={"unit_ids": units},
    )

    assert response.status_code == 201, response.text
    assert len(response.json()) == 12
    db.expire_all()
    assert len(db.scalars(select(UnitPriceVersion)).all()) == 12
    assert all(row.status == "draft" for row in db.scalars(select(UnitPriceVersion)))


def test_one_unpriceable_unit_rolls_the_whole_batch_back(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    floor_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """A price list where some units were priced and others silently were not is
    worse than no price list: nothing on screen says which is which."""
    units = _units(admin_client, project_id, floor_id, 4)
    for unit in units[:3]:
        approve_areas(admin_client, project_id, unit, area_types)

    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/generate", json={"unit_ids": units}
    )

    assert response.status_code == 409
    assert "approved area schedule" in response.json()["detail"]
    db.expire_all()
    assert db.scalars(select(UnitPriceVersion)).all() == []


def test_bulk_generation_never_touches_a_live_price(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    """Generating drafts is not repricing. Only activation changes a list price."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/generate", json={"unit_ids": [unit_id]}
    )

    assert response.status_code == 201, response.text
    db.expire_all()
    rows = {row.version_number: row.status for row in db.scalars(select(UnitPriceVersion))}
    assert rows == {1: "active", 2: "draft"}
    assert db.scalars(select(Unit)).one().pricing_approved is True


def test_a_unit_in_a_hidden_phase_is_not_bulk_priced(
    admin_client: TestClient,
    finance: User,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """A filter narrows what a caller may see. An explicit identifier cannot widen it."""
    from tests.factories import client_for
    from tests.modules.conftest import PROJECTS

    approve_areas(admin_client, project_id, unit_id, area_types)
    admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{finance.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    client = client_for(finance.email)

    response = client.post(
        f"{pricing_url(project_id)}/price-versions/generate", json={"unit_ids": [unit_id]}
    )

    assert response.status_code == 422
    assert "at least one unit" in response.json()["detail"]
    db.expire_all()
    assert db.scalars(select(UnitPriceVersion)).all() == []


def test_bulk_submit_approve_and_activate_move_the_whole_selection(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    floor_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    units = _units(admin_client, project_id, floor_id, 5)
    for unit in units:
        approve_areas(admin_client, project_id, unit, area_types)
    versions = [
        item["id"]
        for item in finance_client.post(
            f"{pricing_url(project_id)}/price-versions/generate", json={"unit_ids": units}
        ).json()
    ]

    submitted = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/submit", json={"version_ids": versions}
    )
    approved = cfo_client.post(
        f"{pricing_url(project_id)}/price-versions/approve",
        json={"version_ids": versions, "reason": "Launch list"},
    )
    activated = cfo_client.post(
        f"{pricing_url(project_id)}/price-versions/activate", json={"version_ids": versions}
    )

    assert submitted.status_code == 200, submitted.text
    assert approved.status_code == 200, approved.text
    assert activated.status_code == 200, activated.text
    db.expire_all()
    assert all(row.status == "active" for row in db.scalars(select(UnitPriceVersion)))
    assert all(unit.pricing_approved for unit in db.scalars(select(Unit).where(Unit.id.in_(units))))


def test_one_failure_rolls_a_bulk_approval_back(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    floor_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Half an approved price list is a price list nobody can publish."""
    units = _units(admin_client, project_id, floor_id, 3)
    for unit in units:
        approve_areas(admin_client, project_id, unit, area_types)
    versions = [
        item["id"]
        for item in finance_client.post(
            f"{pricing_url(project_id)}/price-versions/generate", json={"unit_ids": units}
        ).json()
    ]
    finance_client.post(
        f"{pricing_url(project_id)}/price-versions/submit", json={"version_ids": versions}
    )
    # One unit is re-measured after submission, so its frozen basis is stale.
    approve_areas(
        admin_client, project_id, units[1], area_types, internal="120.0000", revision="R1"
    )

    response = cfo_client.post(
        f"{pricing_url(project_id)}/price-versions/approve",
        json={"version_ids": versions, "reason": "Launch list"},
    )

    assert response.status_code == 409
    db.expire_all()
    assert all(row.status == "submitted" for row in db.scalars(select(UnitPriceVersion)))


def test_a_bulk_action_needs_at_least_one_version(
    finance_client: TestClient, project_id: str, active_configuration: str
) -> None:
    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/submit", json={"version_ids": []}
    )

    assert response.status_code == 422
