"""Country configuration: currencies, packs, tax rules, lookups and thresholds."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.settings.models import CountryApprovalThreshold, TaxRule
from tests.factories import client_for, make_user

CURRENCIES = "/api/v1/settings/currencies"
PACKS = "/api/v1/settings/country-packs"
REFERENCE = "/api/v1/settings/reference-values"


@pytest.fixture
def admin(db: Session) -> User:
    return make_user(db, email="admin@example.com", roles=("system_admin",))


@pytest.fixture
def client(admin: User) -> TestClient:
    return client_for(admin.email)


@pytest.fixture
def currency_id(client: TestClient) -> str:
    response = client.post(
        CURRENCIES, json={"code": "JOD", "name": "Jordanian Dinar", "minor_units": 3}
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def pack_id(client: TestClient, currency_id: str) -> str:
    response = client.post(
        PACKS,
        json={
            "country_code": "JO",
            "name": "Jordan",
            "locale": "en-JO",
            "timezone": "Asia/Amman",
            "default_currency_id": currency_id,
            "area_unit": "sqm",
            "fiscal_year_start_month": 1,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


# --------------------------------------------------------------------------- #
# Currencies
# --------------------------------------------------------------------------- #


def test_a_currency_code_is_normalised_to_upper_case(client: TestClient) -> None:
    """Given a lower-case code, then it is stored upper-cased."""
    response = client.post(CURRENCIES, json={"code": "jod", "name": "Jordanian Dinar"})

    assert response.status_code == 201
    assert response.json()["code"] == "JOD"


def test_duplicate_currency_codes_are_rejected(client: TestClient, currency_id: str) -> None:
    """Given an existing code, then a second one conflicts."""
    response = client.post(CURRENCIES, json={"code": "jod", "name": "Duplicate"})

    assert response.status_code == 409


@pytest.mark.parametrize("code", ["J1D", "JO", "JODX", "12 "])
def test_invalid_currency_codes_are_rejected(client: TestClient, code: str) -> None:
    """Given a code that is not three letters, then creation fails."""
    response = client.post(CURRENCIES, json={"code": code, "name": "Bad"})

    assert response.status_code in (409, 422)


# --------------------------------------------------------------------------- #
# Country packs
# --------------------------------------------------------------------------- #


def test_a_country_pack_requires_an_existing_currency(client: TestClient) -> None:
    """Given an unknown default currency, then creation fails."""
    response = client.post(
        PACKS,
        json={
            "country_code": "JO",
            "name": "Jordan",
            "locale": "en-JO",
            "timezone": "Asia/Amman",
            "default_currency_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Default currency does not exist."}


def test_a_country_pack_requires_an_active_currency(client: TestClient, currency_id: str) -> None:
    """Given a deactivated currency, then it cannot be a default."""
    assert client.patch(f"{CURRENCIES}/{currency_id}", json={"is_active": False}).status_code == 200

    response = client.post(
        PACKS,
        json={
            "country_code": "JO",
            "name": "Jordan",
            "locale": "en-JO",
            "timezone": "Asia/Amman",
            "default_currency_id": currency_id,
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Default currency must be active."}


def test_duplicate_country_codes_are_rejected(
    client: TestClient, currency_id: str, pack_id: str
) -> None:
    """Given an existing country code, then a second pack conflicts."""
    response = client.post(
        PACKS,
        json={
            "country_code": "jo",
            "name": "Jordan again",
            "locale": "en-JO",
            "timezone": "Asia/Amman",
            "default_currency_id": currency_id,
        },
    )

    assert response.status_code == 409


@pytest.mark.parametrize("month", [0, 13, -1])
def test_invalid_fiscal_start_months_are_rejected(
    client: TestClient, currency_id: str, month: int
) -> None:
    """Given a month outside 1..12, then creation fails."""
    response = client.post(
        PACKS,
        json={
            "country_code": "AE",
            "name": "UAE",
            "locale": "en-AE",
            "timezone": "Asia/Dubai",
            "default_currency_id": currency_id,
            "fiscal_year_start_month": month,
        },
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Tax rules
# --------------------------------------------------------------------------- #


def _tax_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tax_code": "VAT",
        "label": "Value Added Tax",
        "applies_to": "sale",
        "calculation_basis": "net_amount",
        "rate_fraction": "0.160000",
        "valid_from": "2026-01-01",
    }
    payload.update(overrides)
    return payload


def test_a_tax_rate_keeps_decimal_precision(client: TestClient, pack_id: str, db: Session) -> None:
    """Given a rate, then it round-trips as an exact decimal, never a float."""
    response = client.post(f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload())

    assert response.status_code == 201
    # Serialised as a string so no client can reinterpret it as a float.
    assert response.json()["rate_fraction"] == "0.160000"
    stored = db.scalars(select(TaxRule)).one()
    assert stored.rate_fraction == Decimal("0.160000")
    assert isinstance(stored.rate_fraction, Decimal)


def test_overlapping_tax_versions_are_rejected(client: TestClient, pack_id: str) -> None:
    """Given an open-ended rule, then a second one covering the same period conflicts."""
    assert client.post(f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload()).status_code == 201

    response = client.post(
        f"{PACKS}/{pack_id}/tax-rules",
        json=_tax_payload(label="VAT 18", rate_fraction="0.18", valid_from="2026-06-01"),
    )

    assert response.status_code == 409
    assert "already covers part of that period" in response.json()["detail"]


def test_a_superseding_rate_is_allowed_once_the_previous_one_is_closed(
    client: TestClient, pack_id: str
) -> None:
    """Given a closed validity window, then the next rate may start after it."""
    first = client.post(f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload(valid_to="2026-05-31"))
    assert first.status_code == 201

    response = client.post(
        f"{PACKS}/{pack_id}/tax-rules",
        json=_tax_payload(label="VAT 18", rate_fraction="0.18", valid_from="2026-06-01"),
    )

    assert response.status_code == 201
    # Both remain visible: tax history is never overwritten.
    listing = client.get(f"{PACKS}/{pack_id}/tax-rules").json()
    assert len(listing) == 2


def test_a_reversed_validity_range_is_rejected(client: TestClient, pack_id: str) -> None:
    """Given valid_to before valid_from, then creation fails."""
    response = client.post(
        f"{PACKS}/{pack_id}/tax-rules",
        json=_tax_payload(valid_from="2026-05-01", valid_to="2026-01-01"),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("rate", ["1.5", "-0.1"])
def test_tax_rates_outside_zero_to_one_are_rejected(
    client: TestClient, pack_id: str, rate: str
) -> None:
    """Given a rate outside the unit interval, then creation fails."""
    response = client.post(f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload(rate_fraction=rate))

    assert response.status_code == 422


def test_tax_rules_have_no_delete_endpoint(client: TestClient, pack_id: str) -> None:
    """Given a tax rule, then it can be deactivated but never removed."""
    created = client.post(f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload()).json()

    deleted = client.delete(f"/api/v1/settings/tax-rules/{created['id']}")
    deactivated = client.patch(
        f"/api/v1/settings/tax-rules/{created['id']}", json={"is_active": False}
    )

    assert deleted.status_code == 404
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False


# --------------------------------------------------------------------------- #
# Reference values
# --------------------------------------------------------------------------- #


def test_reference_keys_are_unique_within_a_scope(client: TestClient, pack_id: str) -> None:
    """Given a scope, category and code, then a duplicate conflicts."""
    body = {"category": "permit_type", "code": "BUILD", "label": "Building permit"}
    assert client.post(REFERENCE, json=body).status_code == 201

    assert client.post(REFERENCE, json=body).status_code == 409
    scoped = {**body, "country_pack_id": pack_id}
    assert client.post(REFERENCE, json=scoped).status_code == 201
    assert client.post(REFERENCE, json=scoped).status_code == 409


def test_inactive_reference_values_remain_available(client: TestClient) -> None:
    """Given a retired value, then it is still listed for historical records."""
    created = client.post(
        REFERENCE, json={"category": "legal_stage", "code": "DRAFT", "label": "Draft"}
    ).json()
    client.patch(f"{REFERENCE}/{created['id']}", json={"is_active": False})

    everything = client.get(REFERENCE).json()
    active_only = client.get(f"{REFERENCE}?include_inactive=false").json()

    assert [value["code"] for value in everything] == ["DRAFT"]
    assert active_only == []


# --------------------------------------------------------------------------- #
# Approval thresholds
# --------------------------------------------------------------------------- #


def test_thresholds_store_decimal_money_and_explicit_rates(
    client: TestClient, pack_id: str, db: Session
) -> None:
    """Given thresholds, then money and rates keep exact decimal values."""
    response = client.put(
        f"{PACKS}/{pack_id}/approval-thresholds",
        json={
            "discount_review_rate_fraction": "0.050000",
            "discount_review_amount": "25000.00",
            "custom_plan_max_duration_months": 60,
            "receipt_reversal_requires_dual_control": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["discount_review_rate_fraction"] == "0.050000"
    assert body["discount_review_amount"] == "25000.00"
    stored = db.scalars(select(CountryApprovalThreshold)).one()
    assert stored.discount_review_amount == Decimal("25000.00")
    assert isinstance(stored.discount_review_amount, Decimal)


@pytest.mark.parametrize(
    "field,value",
    [
        ("discount_review_rate_fraction", "1.5"),
        ("minimum_margin_rate_fraction", "-0.2"),
        ("custom_plan_max_duration_months", 0),
        ("discount_review_amount", "-1.00"),
    ],
)
def test_threshold_boundaries_are_validated(
    client: TestClient, pack_id: str, field: str, value: object
) -> None:
    """Given an out-of-range control limit, then the write is refused."""
    response = client.put(f"{PACKS}/{pack_id}/approval-thresholds", json={field: value})

    assert response.status_code == 422


def test_writing_thresholds_twice_replaces_rather_than_duplicates(
    client: TestClient, pack_id: str, db: Session
) -> None:
    """Given a second write, then the country pack still has exactly one row."""
    client.put(
        f"{PACKS}/{pack_id}/approval-thresholds",
        json={"discount_review_rate_fraction": "0.050000"},
    )
    client.put(
        f"{PACKS}/{pack_id}/approval-thresholds",
        json={"discount_review_rate_fraction": "0.100000"},
    )

    rows = db.scalars(select(CountryApprovalThreshold)).all()
    assert len(rows) == 1
    assert rows[0].discount_review_rate_fraction == Decimal("0.100000")


def test_reading_unconfigured_thresholds_reports_not_found(
    client: TestClient, pack_id: str
) -> None:
    """Given a pack with no thresholds, then reading them is a 404, not an empty row."""
    response = client.get(f"{PACKS}/{pack_id}/approval-thresholds")

    assert response.status_code == 404
