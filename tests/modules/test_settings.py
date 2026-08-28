"""Country configuration: currencies, packs, tax rules, lookups and thresholds."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory
from app.core.errors import ConflictError
from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.settings import service
from app.modules.settings.models import (
    CountryApprovalThreshold,
    CountryPack,
    Currency,
    ReferenceValue,
    TaxRule,
)
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


def test_an_unused_currency_can_be_deactivated(client: TestClient, currency_id: str) -> None:
    """Given a currency no country pack depends on, then it can be retired."""
    response = client.patch(f"{CURRENCIES}/{currency_id}", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_the_default_currency_of_an_active_pack_cannot_be_deactivated(
    client: TestClient, currency_id: str, pack_id: str, db: Session
) -> None:
    """Given an active pack defaulting to it, then deactivating the currency is refused."""
    response = client.patch(f"{CURRENCIES}/{currency_id}", json={"is_active": False})

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Currency cannot be deactivated while it is the default currency "
            "of an active country pack."
        )
    }
    # The refusal is total: neither the row nor the audit trail moved.
    listed = client.get(CURRENCIES).json()
    assert [item["is_active"] for item in listed] == [True]
    assert db.scalars(select(Currency).where(Currency.id == uuid.UUID(currency_id))).one().is_active
    updates = db.scalars(select(AuditEvent).where(AuditEvent.action == "currency.updated")).all()
    assert updates == []


def test_a_currency_used_only_by_an_inactive_pack_can_be_deactivated(
    client: TestClient, currency_id: str, pack_id: str
) -> None:
    """Given the only pack using it is retired, then the currency may be retired too."""
    assert client.patch(f"{PACKS}/{pack_id}", json={"is_active": False}).status_code == 200

    response = client.patch(f"{CURRENCIES}/{currency_id}", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_unrelated_currency_edits_still_apply_while_a_pack_depends_on_it(
    client: TestClient, currency_id: str, pack_id: str
) -> None:
    """Given a depended-on currency, then the guard blocks only deactivation."""
    response = client.patch(
        f"{CURRENCIES}/{currency_id}", json={"name": "Jordanian dinar", "symbol": "JD"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Jordanian dinar"
    assert response.json()["symbol"] == "JD"
    assert response.json()["is_active"] is True


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


def test_an_explicit_null_clears_a_tax_rule_end_date(
    client: TestClient, pack_id: str, db: Session
) -> None:
    """Given ``valid_to: null``, then the rule reopens instead of being ignored.

    An omitted key and an explicit null are different requests: the first says
    nothing about the field, the second says "there is no end date".
    """
    created = client.post(
        f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload(valid_to="2026-05-31")
    ).json()

    response = client.patch(f"/api/v1/settings/tax-rules/{created['id']}", json={"valid_to": None})

    assert response.status_code == 200
    assert response.json()["valid_to"] is None
    assert db.scalars(select(TaxRule)).one().valid_to is None
    # The trail has to show the end date going away, not a no-op update.
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "tax_rule.updated")).one()
    assert event.before_data["valid_to"] == "2026-05-31"
    assert event.after_data["valid_to"] is None


def test_omitting_a_tax_rule_end_date_leaves_it_alone(client: TestClient, pack_id: str) -> None:
    """Given a body without ``valid_to``, then the stored end date survives."""
    created = client.post(
        f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload(valid_to="2026-05-31")
    ).json()

    response = client.patch(
        f"/api/v1/settings/tax-rules/{created['id']}", json={"label": "VAT (standard)"}
    )

    assert response.status_code == 200
    assert response.json()["valid_to"] == "2026-05-31"


def test_clearing_a_tax_rule_end_date_is_revalidated_against_its_successor(
    client: TestClient, pack_id: str, db: Session
) -> None:
    """Given a later rule, then reopening the earlier one is refused, not applied."""
    first = client.post(
        f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload(valid_to="2026-05-31")
    ).json()
    assert (
        client.post(
            f"{PACKS}/{pack_id}/tax-rules",
            json=_tax_payload(label="VAT 18", rate_fraction="0.18", valid_from="2026-06-01"),
        ).status_code
        == 201
    )

    response = client.patch(f"/api/v1/settings/tax-rules/{first['id']}", json={"valid_to": None})

    assert response.status_code == 409
    stored = db.scalars(select(TaxRule).where(TaxRule.id == uuid.UUID(first["id"]))).one()
    assert stored.valid_to is not None


def test_a_null_start_date_is_refused_rather_than_silently_dropped(
    client: TestClient, pack_id: str
) -> None:
    """Given ``valid_from: null`` on a column that cannot be null, then it is a 422."""
    created = client.post(f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload()).json()

    response = client.patch(
        f"/api/v1/settings/tax-rules/{created['id']}", json={"valid_from": None}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "valid_from cannot be null."}


def test_a_reversed_window_on_an_inactive_rule_is_a_client_error(
    client: TestClient, pack_id: str
) -> None:
    """Given an inactive rule, then a reversed window is still refused cleanly.

    Overlap is not evaluated for an inactive rule, so before this the write went
    straight to the database and surfaced as an unhandled check violation.
    """
    created = client.post(f"{PACKS}/{pack_id}/tax-rules", json=_tax_payload()).json()
    assert (
        client.patch(
            f"/api/v1/settings/tax-rules/{created['id']}", json={"is_active": False}
        ).status_code
        == 200
    )

    response = client.patch(
        f"/api/v1/settings/tax-rules/{created['id']}", json={"valid_to": "2025-01-01"}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "valid_to must not be earlier than valid_from."}


def _wait_until_a_backend_blocks(timeout: float = 15.0) -> bool:
    """Poll until some other backend in this database is waiting on a lock.

    Polling PostgreSQL's own view of who is waiting keeps the test deterministic:
    it waits *until* the condition holds rather than guessing at a sleep long
    enough to hide a race.
    """
    query = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() "
        "AND pid <> pg_backend_pid() "
        "AND wait_event_type = 'Lock'"
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with get_engine().connect() as connection:
            if connection.execute(query).scalar():
                return True
        time.sleep(0.05)
    return False


def test_a_concurrent_writer_cannot_slip_an_overlapping_tax_rule_past_the_check(
    admin: User, pack_id: str, db: Session
) -> None:
    """Given two real transactions, then only one overlapping rule survives.

    Overlap protection is a read-then-write decision, so proving it holds needs
    two genuine PostgreSQL transactions racing: a mocked session would only prove
    that the mock was called in the order the test itself chose.

    The first writer takes the country-pack lock the service takes and holds it,
    so the second writer's request is pinned mid-flight. If the service read the
    existing rules *before* locking, it would have seen an empty table, and its
    insert would land after the first writer's commit — two overlapping active
    rules, and no error for anyone to notice.
    """
    pack = uuid.UUID(pack_id)
    factory = get_session_factory()
    holder = factory()
    holder.execute(select(CountryPack).where(CountryPack.id == pack).with_for_update())

    outcome: list[object] = []

    def second_writer() -> None:
        session = factory()
        try:
            service.create_tax_rule(
                session,
                country_pack_id=pack,
                actor_user_id=admin.id,
                correlation_id=uuid.uuid4(),
                tax_code="VAT",
                label="VAT 18",
                applies_to="sale",
                calculation_basis="net_amount",
                rate_fraction=Decimal("0.180000"),
                valid_from=date(2026, 6, 1),
                valid_to=None,
            )
            outcome.append("created")
        # Deliberately broad: whatever the writer raises has to reach the
        # asserting thread, which cannot see this thread's traceback.
        except BaseException as exc:
            outcome.append(exc)
        finally:
            session.rollback()
            session.close()

    thread = threading.Thread(target=second_writer, name="second-tax-writer")
    thread.start()
    try:
        blocked = _wait_until_a_backend_blocks()
        # Only now, with the second writer still waiting, does the first commit a
        # rule that covers the period the second one asked for.
        holder.add(
            TaxRule(
                country_pack_id=pack,
                tax_code="VAT",
                label="VAT 16",
                applies_to="sale",
                calculation_basis="net_amount",
                rate_fraction=Decimal("0.160000"),
                valid_from=date(2026, 1, 1),
                valid_to=None,
                is_active=True,
            )
        )
        holder.commit()
    finally:
        holder.close()
        thread.join(timeout=30)

    assert blocked, "the second writer evaluated overlap without taking the country-pack lock"
    assert not thread.is_alive()
    assert isinstance(outcome[0], ConflictError), outcome[0]
    surviving = db.scalars(select(TaxRule)).all()
    assert [rule.label for rule in surviving] == ["VAT 16"]


def test_racing_writers_leave_exactly_one_active_tax_rule(
    admin: User, pack_id: str, db: Session
) -> None:
    """Given writers released together, then one wins and the rest conflict."""
    pack = uuid.UUID(pack_id)
    factory = get_session_factory()
    writers = 6
    start = threading.Barrier(writers)
    outcome: list[object] = []
    guard = threading.Lock()

    def writer(index: int) -> None:
        session = factory()
        start.wait(timeout=30)
        try:
            service.create_tax_rule(
                session,
                country_pack_id=pack,
                actor_user_id=admin.id,
                correlation_id=uuid.uuid4(),
                tax_code="VAT",
                label=f"VAT {index}",
                applies_to="sale",
                calculation_basis="net_amount",
                rate_fraction=Decimal("0.160000"),
                valid_from=date(2026, 1, 1),
                valid_to=None,
            )
            result: object = "created"
        # Deliberately broad: whatever the writer raises has to reach the
        # asserting thread, which cannot see this thread's traceback.
        except BaseException as exc:
            result = exc
        finally:
            session.rollback()
            session.close()
        with guard:
            outcome.append(result)

    threads = [threading.Thread(target=writer, args=(index,)) for index in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert all(not thread.is_alive() for thread in threads)
    assert outcome.count("created") == 1, outcome
    assert all(isinstance(item, ConflictError) for item in outcome if item != "created"), outcome
    assert len(db.scalars(select(TaxRule)).all()) == 1


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


def test_an_explicit_null_clears_optional_reference_fields(client: TestClient, db: Session) -> None:
    """Given nulls, then the optional description and validity window are cleared."""
    created = client.post(
        REFERENCE,
        json={
            "category": "permit_type",
            "code": "BUILD",
            "label": "Building permit",
            "description": "Issued by the municipality",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
        },
    ).json()

    response = client.patch(
        f"{REFERENCE}/{created['id']}",
        json={"description": None, "valid_from": None, "valid_to": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["description"], body["valid_from"], body["valid_to"]) == (None, None, None)
    stored = db.scalars(select(ReferenceValue)).one()
    assert (stored.description, stored.valid_from, stored.valid_to) == (None, None, None)
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "reference_value.updated")
    ).one()
    assert event.before_data["description"] == "Issued by the municipality"
    assert event.after_data["description"] is None
    assert event.after_data["valid_to"] is None


def test_omitting_reference_fields_leaves_them_alone(client: TestClient) -> None:
    """Given a body naming only the label, then the other fields survive."""
    created = client.post(
        REFERENCE,
        json={
            "category": "permit_type",
            "code": "BUILD",
            "label": "Building permit",
            "description": "Issued by the municipality",
            "valid_to": "2026-12-31",
        },
    ).json()

    response = client.patch(f"{REFERENCE}/{created['id']}", json={"label": "Building permit (new)"})

    assert response.status_code == 200
    assert response.json()["description"] == "Issued by the municipality"
    assert response.json()["valid_to"] == "2026-12-31"


def test_a_reversed_reference_window_is_still_rejected_after_a_partial_clear(
    client: TestClient,
) -> None:
    """Given a cleared start and an earlier end, then the ordering rule still applies."""
    created = client.post(
        REFERENCE,
        json={
            "category": "permit_type",
            "code": "BUILD",
            "label": "Building permit",
            "valid_from": "2026-01-01",
        },
    ).json()

    response = client.patch(f"{REFERENCE}/{created['id']}", json={"valid_to": "2025-01-01"})

    assert response.status_code == 422
    assert response.json() == {"detail": "valid_to must not be earlier than valid_from."}


def test_a_null_reference_label_is_refused_rather_than_silently_dropped(
    client: TestClient,
) -> None:
    """Given ``label: null`` on a column that cannot be null, then it is a 422."""
    created = client.post(
        REFERENCE, json={"category": "legal_stage", "code": "DRAFT", "label": "Draft"}
    ).json()

    response = client.patch(f"{REFERENCE}/{created['id']}", json={"label": None})

    assert response.status_code == 422
    assert response.json() == {"detail": "label cannot be null."}


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
