"""Negotiated intent reconciles through the quote without changing list truth."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.modules.sales.price_facts import variance_amount, variance_fraction
from tests.modules.conftest import SETTINGS, pricing_url, sales_url


@pytest.mark.parametrize(
    "reference,agreed,amount,fraction",
    [
        ("100000", "100000", "0.00", "0.000000"),
        ("100000", "95000", "-5000.00", "-0.050000"),
        ("100000", "105000", "5000.00", "0.050000"),
        ("150000", "143000", "-7000.00", "-0.046667"),
        ("0", "100", "100.00", None),
    ],
)
def test_signed_golden(reference: str, agreed: str, amount: str, fraction: str | None) -> None:
    assert str(variance_amount(Decimal(reference), Decimal(agreed))) == amount
    actual = variance_fraction(Decimal(reference), Decimal(agreed))
    assert (str(actual) if actual is not None else None) == fraction


def test_sales_selection_price_intent_and_internal_adjustment_guards(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    released_unit: str,
    buyer_id: str,
    country_pack_id: str,
) -> None:
    base = sales_url(project_id)
    assert sales_ops_client.get(f"{base}/transactions").json()["total"] == 0
    options = sales_ops_client.get(f"{base}/unit-options")
    assert options.status_code == 200, options.text
    unit = next(row for row in options.json()["items"] if row["unit_id"] == released_unit)
    reference = Decimal(unit["reference_price_ex_tax"])
    for target in (reference, reference - Decimal("7000"), reference + Decimal("10000")):
        payload = {
            "unit_id": released_unit,
            "expected_price_version_id": unit["unit_price_version_id"],
            "sales_price_ex_tax": str(target),
        }
        preview = sales_ops_client.post(f"{base}/price-preview", json=payload)
        assert preview.status_code == 200, preview.text
        assert Decimal(preview.json()["sales_price_ex_tax"]) == target
        created = sales_ops_client.post(
            f"{base}/reservations", json={**payload, "client_id": buyer_id}
        )
        assert created.status_code == 201, created.text
        body = created.json()
        reservation = body["reservation"]
        assert Decimal(reservation["sales_price_ex_tax"]) == target
        assert Decimal(reservation["reference_price_ex_tax"]) == reference
        assert Decimal(reservation["price_variance_amount"]) == target - reference
        identifier = reservation["id"]
        for adjustment in body["adjustments"]:
            refused = sales_ops_client.patch(
                f"{base}/reservation-adjustments/{adjustment['id']}", json={"amount": "0"}
            )
            assert refused.status_code == 422, refused.text
        refused = sales_ops_client.post(
            f"{base}/reservations/{identifier}/adjustments",
            json={"adjustment_type": "negotiated_price_discount", "amount": "1"},
        )
        assert refused.status_code == 422, refused.text
    register = sales_ops_client.get(f"{base}/transactions").json()
    assert register["total"] == 3
    assert len({row["id"] for row in register["items"]}) == 3
    assert all(row["kind"] == "reservation" for row in register["items"])
    threshold = admin_client.put(
        f"{SETTINGS}/country-packs/{country_pack_id}/approval-thresholds",
        json={
            "discount_review_rate_fraction": "0.100000",
            "pricing_requires_commercial_approval": True,
        },
    )
    assert threshold.status_code == 200, threshold.text
    changed = sales_ops_client.put(
        f"{base}/reservations/{identifier}/sales-price",
        json={"sales_price_ex_tax": str(reference * Decimal("0.8"))},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["reservation"]["exception_approval_required"] is True
    assert changed.json()["reservation"]["exception_approval_status"] == "pending"
    activation = sales_ops_client.post(f"{base}/reservations/{identifier}/activate", json={})
    assert activation.status_code == 409, activation.text
    still = sales_ops_client.get(f"{base}/unit-options").json()["items"]
    assert Decimal(still[0]["reference_price_ex_tax"]) == reference


def test_existing_adjustments_reconcile_without_changing_target(
    sales_ops_client: TestClient,
    project_id: str,
    reservation_id: str,
) -> None:
    url = f"{sales_url(project_id)}/reservations/{reservation_id}"
    changed = sales_ops_client.put(f"{url}/sales-price", json={"sales_price_ex_tax": "143000.25"})
    assert changed.status_code == 200, changed.text
    adjustment = sales_ops_client.post(
        f"{url}/adjustments",
        json={"adjustment_type": "percentage_discount", "rate_fraction": "0.050000"},
    )
    assert adjustment.status_code == 201, adjustment.text
    assert Decimal(adjustment.json()["reservation"]["sales_price_ex_tax"]) == Decimal("143000.25")
    costs = sales_ops_client.post(
        f"{url}/adjustments", json={"adjustment_type": "package_cost", "amount": "2000"}
    )
    assert costs.status_code == 201, costs.text
    row = costs.json()["reservation"]
    assert Decimal(row["sales_price_ex_tax"]) == Decimal("143000.25")
    assert Decimal(row["effective_net_revenue_preview"]) == Decimal("141000.25")


def test_duplicate_creation_key_and_stale_unit_selection(
    sales_ops_client: TestClient,
    project_id: str,
    released_unit: str,
    buyer_id: str,
) -> None:
    base = sales_url(project_id)
    option = sales_ops_client.get(f"{base}/unit-options").json()["items"][0]
    payload = {
        "unit_id": released_unit,
        "client_id": buyer_id,
        "sales_price_ex_tax": option["reference_price_ex_tax"],
        "expected_price_version_id": option["unit_price_version_id"],
        "creation_request_id": str(uuid.uuid4()),
    }
    first = sales_ops_client.post(f"{base}/reservations", json=payload)
    assert first.status_code == 201, first.text
    retry = sales_ops_client.post(f"{base}/reservations", json=payload)
    assert retry.status_code == 201, retry.text
    assert retry.json()["reservation"]["id"] == first.json()["reservation"]["id"]
    mismatch = sales_ops_client.post(
        f"{base}/reservations", json={**payload, "sales_price_ex_tax": "1"}
    )
    assert mismatch.status_code == 409
    stale = sales_ops_client.post(
        f"{base}/reservations",
        json={
            **payload,
            "creation_request_id": str(uuid.uuid4()),
            "expected_price_version_id": str(uuid.uuid4()),
        },
    )
    assert stale.status_code == 409
    assert sales_ops_client.get(f"{base}/transactions").json()["total"] == 1


@pytest.mark.parametrize("difference", ["0", "-7000", "10000"])
def test_requote_preserves_intent_and_sale_snapshot(
    sales_ops_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    released_unit: str,
    reservation_id: str,
    difference: str,
) -> None:
    base = sales_url(project_id)
    url = f"{base}/reservations/{reservation_id}"
    original = sales_ops_client.get(url).json()["reservation"]
    reference = Decimal(original["reference_price_ex_tax"])
    target = reference + Decimal(difference)
    changed = sales_ops_client.put(f"{url}/sales-price", json={"sales_price_ex_tax": str(target)})
    assert changed.status_code == 200, changed.text
    assert (
        sales_ops_client.post(
            f"{url}/confirm-deposit", json={"evidence_reference": "BANK"}
        ).status_code
        == 200
    )
    assert sales_ops_client.post(f"{url}/activate", json={}).status_code == 200
    draft = finance_client.post(
        f"{pricing_url(project_id)}/units/{released_unit}/price-versions",
        json={"selling_price": str(reference + Decimal("25000")), "change_reason": "New list"},
    )
    assert draft.status_code == 201, draft.text
    price_url = f"{pricing_url(project_id)}/price-versions/{draft.json()['id']}"
    assert finance_client.post(f"{price_url}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{price_url}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{price_url}/activate").status_code == 200
    frozen = sales_ops_client.get(url).json()["reservation"]
    assert Decimal(frozen["reference_price_ex_tax"]) == reference
    assert Decimal(frozen["sales_price_ex_tax"]) == target
    refused = sales_ops_client.put(f"{url}/sales-price", json={"sales_price_ex_tax": "1"})
    assert refused.status_code == 409
    requote = sales_ops_client.post(
        f"{url}/requote",
        json={
            "reason": "Refresh reference",
            "price_locked_until": (date.today() + timedelta(days=30)).isoformat(),
        },
    )
    assert requote.status_code == 200, requote.text
    row = requote.json()["reservation"]
    assert Decimal(row["sales_price_ex_tax"]) == target
    assert Decimal(row["reference_price_ex_tax"]) == reference + Decimal("25000")
    sale = sales_ops_client.post(f"{base}/contracts", json={"reservation_id": reservation_id})
    assert sale.status_code == 201, sale.text
    snapshot = sale.json()["sale"]
    assert snapshot["sales_price_ex_tax"] == row["sales_price_ex_tax"]
    assert snapshot["price_variance_amount"] == row["price_variance_amount"]
    assert snapshot["reference_price_ex_tax"] == row["reference_price_ex_tax"]
    current = sales_ops_client.get(f"{base}/transactions").json()
    assert current["total"] == 1
    assert current["items"][0]["kind"] == "sale"
    assert sales_ops_client.get(f"{base}/transactions?history=true").json()["total"] == 2


def test_migration_refuses_to_discard_a_negotiated_decision(
    sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    from alembic import command

    from tests.conftest import alembic_config

    response = sales_ops_client.put(
        f"{sales_url(project_id)}/reservations/{reservation_id}/sales-price",
        json={"sales_price_ex_tax": "143000.00"},
    )
    assert response.status_code == 200, response.text
    with pytest.raises(RuntimeError, match="Negotiated sales decisions exist"):
        command.downgrade(alembic_config(), "0020_management_reporting")
    retained = sales_ops_client.get(f"{sales_url(project_id)}/reservations/{reservation_id}")
    assert retained.status_code == 200, retained.text
    assert retained.json()["reservation"]["sales_price_ex_tax"] == "143000.00"


def test_migration_round_trip_and_schema_agreement(postgres: None) -> None:
    from alembic import command

    from tests.conftest import alembic_config

    config = alembic_config()
    command.downgrade(config, "0020_management_reporting")
    command.upgrade(config, "head")
    command.check(config)
