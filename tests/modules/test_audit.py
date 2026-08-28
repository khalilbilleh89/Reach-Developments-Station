"""Audit history: what is recorded, what is never recorded, and transactionality."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.modules.access.models import User
from app.modules.access.service import create_user
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import REDACTED
from tests.factories import DEFAULT_PASSWORD, client_for, make_user

AUDIT_URL = "/api/v1/audit-events"


@pytest.fixture
def admin(db: Session) -> User:
    return make_user(db, email="admin@example.com", roles=("system_admin",))


@pytest.fixture
def client(admin: User) -> TestClient:
    return client_for(admin.email)


def _actions(db: Session) -> list[str]:
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at))
    return [event.action for event in events]


def test_creating_a_user_is_audited(client: TestClient, admin: User, db: Session) -> None:
    """Given a new user, then the event records actor, entity and outcome."""
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": "new@example.com",
            "display_name": "New Person",
            "initial_password": "a-temporary-password",
            "role_keys": ["finance"],
        },
    )
    assert response.status_code == 201

    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "user.created")).one()
    assert event.actor_user_id == admin.id
    assert event.entity_type == "user"
    assert str(event.entity_id) == response.json()["id"]
    assert event.correlation_id is not None
    assert event.before_data is None
    assert event.after_data["email"] == "new@example.com"
    assert event.after_data["role_keys"] == ["finance"]


def test_role_assignment_records_before_and_after(client: TestClient, db: Session) -> None:
    """Given a role change, then both states are captured."""
    created = client.post(
        "/api/v1/admin/users",
        json={
            "email": "new@example.com",
            "display_name": "New",
            "initial_password": "a-temporary-password",
            "role_keys": ["finance"],
        },
    ).json()

    client.patch(f"/api/v1/admin/users/{created['id']}", json={"role_keys": ["legal", "finance"]})

    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "user.updated")).one()
    assert event.before_data["role_keys"] == ["finance"]
    assert event.after_data["role_keys"] == ["finance", "legal"]


def test_deactivation_is_audited_with_a_reason(client: TestClient, db: Session) -> None:
    """Given a deactivation, then the recorded reason survives."""
    created = client.post(
        "/api/v1/admin/users",
        json={
            "email": "new@example.com",
            "display_name": "New",
            "initial_password": "a-temporary-password",
            "role_keys": [],
        },
    ).json()

    client.patch(
        f"/api/v1/admin/users/{created['id']}",
        json={"is_active": False, "reason": "Left the company"},
    )

    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "user.updated")).one()
    assert event.reason == "Left the company"
    assert event.before_data["is_active"] is True
    assert event.after_data["is_active"] is False


def test_configuration_changes_are_audited(client: TestClient, db: Session) -> None:
    """Given currency, pack, tax and threshold writes, then each is recorded."""
    currency = client.post(
        "/api/v1/settings/currencies", json={"code": "JOD", "name": "Dinar"}
    ).json()
    pack = client.post(
        "/api/v1/settings/country-packs",
        json={
            "country_code": "JO",
            "name": "Jordan",
            "locale": "en-JO",
            "timezone": "Asia/Amman",
            "default_currency_id": currency["id"],
        },
    ).json()
    client.post(
        f"/api/v1/settings/country-packs/{pack['id']}/tax-rules",
        json={
            "tax_code": "VAT",
            "label": "VAT",
            "applies_to": "sale",
            "calculation_basis": "net_amount",
            "rate_fraction": "0.160000",
            "valid_from": "2026-01-01",
        },
    )
    client.put(
        f"/api/v1/settings/country-packs/{pack['id']}/approval-thresholds",
        json={"discount_review_rate_fraction": "0.050000"},
    )

    assert set(_actions(db)) >= {
        "currency.created",
        "country_pack.created",
        "tax_rule.created",
        "approval_threshold.created",
    }


def test_a_recorded_rate_keeps_full_precision(client: TestClient, db: Session) -> None:
    """Given a decimal rate, then the audit trail stores it as an exact string."""
    currency = client.post(
        "/api/v1/settings/currencies", json={"code": "JOD", "name": "Dinar"}
    ).json()
    pack = client.post(
        "/api/v1/settings/country-packs",
        json={
            "country_code": "JO",
            "name": "Jordan",
            "locale": "en-JO",
            "timezone": "Asia/Amman",
            "default_currency_id": currency["id"],
        },
    ).json()
    client.put(
        f"/api/v1/settings/country-packs/{pack['id']}/approval-thresholds",
        json={"discount_review_amount": "25000.00", "discount_review_rate_fraction": "0.050000"},
    )

    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "approval_threshold.created")
    ).one()
    assert event.after_data["discount_review_amount"] == "25000.00"
    assert event.after_data["discount_review_rate_fraction"] == "0.050000"


def test_passwords_and_tokens_never_reach_the_audit_trail(client: TestClient, db: Session) -> None:
    """Given every governance write, then no secret appears anywhere in audit."""
    created = client.post(
        "/api/v1/admin/users",
        json={
            "email": "new@example.com",
            "display_name": "New",
            "initial_password": "a-temporary-password",
            "role_keys": [],
        },
    ).json()
    client.post(
        f"/api/v1/admin/users/{created['id']}/reset-password",
        json={"new_password": "another-temporary-password"},
    )

    dumped = " ".join(
        str(event.before_data) + str(event.after_data) for event in db.scalars(select(AuditEvent))
    )
    assert "a-temporary-password" not in dumped
    assert "another-temporary-password" not in dumped
    assert DEFAULT_PASSWORD not in dumped
    assert "argon2" not in dumped
    assert REDACTED not in dumped or "password_hash" not in dumped
    # The non-secret flag is still recorded, because an auditor needs it.
    reset = db.scalars(select(AuditEvent).where(AuditEvent.action == "user.password_reset")).one()
    assert reset.after_data["must_change_password"] is True


def test_an_audit_event_rolls_back_with_its_transaction(db: Session, admin: User) -> None:
    """Given a refused change, then no audit row survives.

    The event is written in the same transaction as the change it describes, so
    a rejected mutation cannot leave a misleading trace behind.
    """
    before = len(db.scalars(select(AuditEvent)).all())

    with pytest.raises(ConflictError):
        create_user(
            db,
            email=admin.email,  # duplicate — conflicts after the audit call site
            display_name="Clash",
            password="a-temporary-password",
            role_keys=[],
            actor_user_id=admin.id,
            correlation_id=admin.id,
        )
    db.rollback()

    assert len(db.scalars(select(AuditEvent)).all()) == before


def test_audit_history_is_read_only(client: TestClient) -> None:
    """Given the audit API, then no write route exists."""
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = client.request(method, AUDIT_URL, json={})
        assert response.status_code == 404, method
        assert response.json() == {"detail": "Not Found."}


def test_audit_can_be_filtered_and_paged(client: TestClient, admin: User) -> None:
    """Given filters, then only matching events are returned."""
    client.post("/api/v1/settings/currencies", json={"code": "JOD", "name": "Dinar"})
    client.post("/api/v1/settings/currencies", json={"code": "AED", "name": "Dirham"})

    by_action = client.get(f"{AUDIT_URL}?action=currency.created").json()
    by_actor = client.get(f"{AUDIT_URL}?actor_user_id={admin.id}").json()
    paged = client.get(f"{AUDIT_URL}?limit=1").json()

    assert by_action["total"] == 2
    assert all(item["action"] == "currency.created" for item in by_action["items"])
    assert by_actor["total"] >= 2
    assert len(paged["items"]) == 1
    assert paged["limit"] == 1


def test_audit_names_the_actor(client: TestClient, admin: User) -> None:
    """Given a recorded change, then the reader sees who made it."""
    client.post("/api/v1/settings/currencies", json={"code": "JOD", "name": "Dinar"})

    item = client.get(f"{AUDIT_URL}?action=currency.created").json()["items"][0]

    assert item["actor_user_id"] == str(admin.id)
    assert item["actor_display_name"] == admin.display_name
    assert item["correlation_id"]
    assert item["source"] == "api"
