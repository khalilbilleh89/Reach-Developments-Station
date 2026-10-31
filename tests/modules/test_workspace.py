"""Saved register views and register preferences: one person's, read by that person alone."""

from __future__ import annotations

import uuid

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import create_app
from app.modules.audit.models import AuditEvent
from app.modules.workspace.models import UserPreference, UserSavedView
from app.modules.workspace.service import MAX_VIEWS_PER_SCREEN
from tests.factories import client_for, make_user
from tests.test_migrations import _alembic_config

VIEWS = "/api/v1/me/views"
PREFERENCES = "/api/v1/me/preferences"


def _person(db: Session, email: str) -> TestClient:
    make_user(db, email=email, roles=("sales_operations",))
    return client_for(email)


def _save(client: TestClient, name: str, screen: str = "collections", **extra: object) -> dict:
    payload = {
        "screen": screen,
        "name": name,
        "filters": {"status": "overdue", "bucket": "", "only": "overdue"},
        "sort": "-outstanding",
        **extra,
    }
    response = client.post(VIEWS, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_view_is_saved_listed_renamed_and_removed_by_its_owner(db: Session) -> None:
    client = _person(db, "owner@example.com")
    saved = _save(client, "Overdue accounts")
    assert saved["filters"] == {"status": "overdue", "bucket": "", "only": "overdue"}
    assert saved["sort"] == "-outstanding"
    assert saved["pinned"] is False

    other_screen = _save(client, "Phase one", screen="inventory_stock", filters={"phase_id": "x"})
    listed = client.get(VIEWS, params={"screen": "collections"}).json()
    assert [row["id"] for row in listed] == [saved["id"]]
    assert {row["id"] for row in client.get(VIEWS).json()} == {saved["id"], other_screen["id"]}

    renamed = client.patch(
        f"{VIEWS}/{saved['id']}", json={"name": "Overdue > 30 d", "pinned": True}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Overdue > 30 d"
    assert renamed.json()["pinned"] is True
    assert renamed.json()["filters"] == saved["filters"], "a rename keeps the filters"

    # Pinned views lead the list for their register.
    _save(client, "All accounts", filters={})
    names = [row["name"] for row in client.get(VIEWS, params={"screen": "collections"}).json()]
    assert names == ["Overdue > 30 d", "All accounts"]

    assert client.delete(f"{VIEWS}/{saved['id']}").status_code == 204
    assert client.get(VIEWS, params={"screen": "collections"}).json()[0]["name"] == "All accounts"
    assert client.delete(f"{VIEWS}/{saved['id']}").status_code == 404


def test_another_persons_view_is_not_found(db: Session) -> None:
    owner = _person(db, "owner@example.com")
    stranger = _person(db, "stranger@example.com")
    saved = _save(owner, "Overdue accounts")

    assert stranger.get(VIEWS).json() == []
    assert stranger.patch(f"{VIEWS}/{saved['id']}", json={"name": "Mine now"}).status_code == 404
    assert stranger.delete(f"{VIEWS}/{saved['id']}").status_code == 404
    assert owner.get(VIEWS).json()[0]["name"] == "Overdue accounts"

    # The same name on the same register is free for another person.
    assert (
        stranger.post(VIEWS, json={"screen": "collections", "name": "Overdue accounts"}).status_code
        == 201
    )


def test_duplicate_names_and_the_per_register_limit_are_refused(db: Session) -> None:
    client = _person(db, "owner@example.com")
    _save(client, "Overdue accounts")
    duplicate = client.post(VIEWS, json={"screen": "collections", "name": "Overdue accounts"})
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]

    # A rename onto an existing name is refused the same way.
    second = _save(client, "Second")
    assert (
        client.patch(f"{VIEWS}/{second['id']}", json={"name": "Overdue accounts"}).status_code
        == 409
    )

    # Blank names and unknown fields are refused before anything is written.
    assert client.post(VIEWS, json={"screen": "collections", "name": "   "}).status_code == 409
    assert (
        client.post(VIEWS, json={"screen": "collections", "name": "x", "extra": 1}).status_code
        == 422
    )
    assert client.post(VIEWS, json={"screen": "Bad Screen", "name": "x"}).status_code == 422
    assert (
        client.post(
            VIEWS, json={"screen": "collections", "name": "x", "filters": {"a": {"b": 1}}}
        ).status_code
        == 422
    )

    for index in range(MAX_VIEWS_PER_SCREEN - 2):
        _save(client, f"View {index}")
    full = client.post(VIEWS, json={"screen": "collections", "name": "One too many"})
    assert full.status_code == 409
    assert str(MAX_VIEWS_PER_SCREEN) in full.json()["detail"]
    # Another register is not full.
    assert client.post(VIEWS, json={"screen": "inventory_stock", "name": "One"}).status_code == 201


def test_a_saved_view_is_audited_including_its_removal(db: Session) -> None:
    client = _person(db, "owner@example.com")
    saved = _save(client, "Overdue accounts")
    client.patch(f"{VIEWS}/{saved['id']}", json={"pinned": True})
    client.delete(f"{VIEWS}/{saved['id']}")

    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "user_saved_view")
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        )
    )
    assert [event.action for event in events] == ["create", "update", "delete"]
    assert all(str(event.entity_id) == saved["id"] for event in events)
    assert events[0].after_data["name"] == "Overdue accounts"
    assert events[1].before_data["pinned"] is False and events[1].after_data["pinned"] is True
    assert events[2].before_data["pinned"] is True and events[2].after_data is None
    assert db.get(UserSavedView, uuid.UUID(saved["id"])) is None


def test_preferences_default_and_persist_per_person(db: Session) -> None:
    client = _person(db, "owner@example.com")
    other = _person(db, "other@example.com")

    assert client.get(PREFERENCES).json() == {"register_density": "comfortable"}
    assert db.scalar(select(UserPreference)) is None, "a read writes nothing"

    assert client.put(PREFERENCES, json={"register_density": "compact"}).status_code == 200
    assert client.get(PREFERENCES).json() == {"register_density": "compact"}
    assert other.get(PREFERENCES).json() == {"register_density": "comfortable"}

    assert client.put(PREFERENCES, json={"register_density": "cosy"}).status_code == 422
    assert client.put(PREFERENCES, json={"register_density": "comfortable"}).status_code == 200
    assert len(list(db.scalars(select(UserPreference)))) == 1


def test_an_anonymous_caller_is_refused(db: Session) -> None:
    anonymous = TestClient(create_app())
    assert anonymous.get(VIEWS).status_code == 401
    assert anonymous.post(VIEWS, json={"screen": "collections", "name": "x"}).status_code == 401
    assert anonymous.get(PREFERENCES).status_code == 401


def test_migration_roundtrip(db: Session) -> None:
    client = _person(db, "owner@example.com")
    _save(client, "Overdue accounts")
    client.put(PREFERENCES, json={"register_density": "compact"})
    db.rollback()
    config = _alembic_config()
    # Working habits are not evidence: the downgrade drops them rather than refusing.
    command.downgrade(config, "0056_project_drawings")
    command.upgrade(config, "head")
    command.check(config)
    db.rollback()
    assert client.get(VIEWS).json() == []
    assert client.get(PREFERENCES).json() == {"register_density": "comfortable"}
