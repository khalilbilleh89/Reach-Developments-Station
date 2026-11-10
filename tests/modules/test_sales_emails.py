"""Reusable email templates persist, isolate projects and retain deleted evidence."""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access, project_payload


def url(project: str) -> str:
    return f"/api/v1/projects/{project}/emails"


BODY = {
    "category": "internal",
    "subject": "Visit request",
    "title": "Can I arrange a visit?",
    "body": "Contact our team.\nنرحب بكم",
}


def test_email_lifecycle_and_audit(
    sales_ops_client: TestClient, project_id: str, db: Session
) -> None:
    client = sales_ops_client
    assert client.get(url(project_id)).json() == {"items": [], "can_edit": True}
    result = client.post(url(project_id), json=BODY)
    assert result.status_code == 201, result.text
    row = result.json()
    path = f"{url(project_id)}/{row['id']}"
    assert row["body"] == BODY["body"]
    update = {
        **BODY,
        "category": "clients",
        "subject": "Updated subject",
        "body": "Updated\nAnswer",
        "expected_version": 1,
    }
    assert client.put(path, json=update).status_code == 200
    assert client.put(path, json=update).status_code == 409
    assert client.delete(path, params={"version": 1, "reason": "Old"}).status_code == 409
    assert client.delete(path, params={"version": 2, "reason": " "}).status_code == 422
    assert client.get(url(project_id)).json()["items"][0]["body"] == "Updated\nAnswer"
    assert client.delete(path, params={"version": 2, "reason": "Outdated"}).status_code == 204
    assert client.delete(path, params={"version": 2, "reason": "Outdated"}).status_code == 404
    assert client.get(url(project_id)).json()["items"] == []
    events = db.execute(
        text(
            "SELECT action, before_data, reason FROM audit_events "
            "WHERE entity_type = 'commercial_email' ORDER BY occurred_at"
        )
    ).all()
    assert [event[0] for event in events] == ["email.created", "email.updated", "email.deleted"]
    assert events[-1][1]["body"] == "Updated\nAnswer"
    assert events[-1][2] == "Outdated"
    assert events[-1][1]["category"] == "clients"
    assert events[-1][1]["subject"] == "Updated subject"


@pytest.mark.parametrize(
    "field,value",
    [
        ("category", "unknown"),
        ("subject", " "),
        ("subject", "x" * 501),
        ("title", " \n"),
        ("body", "\t"),
        ("title", "x" * 501),
        ("body", "x" * 20001),
        ("body", None),
    ],
)
def test_email_validation(
    sales_ops_client: TestClient, project_id: str, field: str, value: str | None
) -> None:
    assert sales_ops_client.post(url(project_id), json={**BODY, field: value}).status_code == 422
    assert sales_ops_client.get(url(project_id)).json()["items"] == []


def test_email_permissions(
    sales_ops_client: TestClient,
    advisor_client: TestClient,
    engineer_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    db: Session,
) -> None:
    row = sales_ops_client.post(url(project_id), json=BODY).json()
    path = f"{url(project_id)}/{row['id']}"
    assert advisor_client.get(url(project_id)).json()["can_edit"] is False
    assert advisor_client.get(url(project_id)).json()["items"][0]["body"] == BODY["body"]
    for client in [advisor_client, engineer_client]:
        assert client.post(url(project_id), json=BODY).status_code == 403
        assert client.put(path, json={**BODY, "expected_version": 1}).status_code == 403
        assert client.delete(path, params={"version": 1, "reason": "Denied"}).status_code == 403
    assert engineer_client.get(url(project_id)).status_code == 403
    user = make_user(db, email="email-phase@example.com", roles=("sales_operations",))
    grant_access(admin_client, project_id, user)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{user.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    with client_for(user.email) as restricted:
        assert restricted.get(url(project_id)).json()["can_edit"] is False
        assert restricted.post(url(project_id), json=BODY).status_code == 403
        assert restricted.delete(path, params={"version": 1, "reason": "Denied"}).status_code == 403
    outsider = make_user(db, email="email-outsider@example.com", roles=("sales_operations",))
    with client_for(outsider.email) as hidden:
        assert hidden.get(url(project_id)).status_code == 404


def test_email_project_isolation(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    row = admin_client.post(url(project_id), json=BODY).json()
    other = admin_client.post(
        "/api/v1/projects",
        json=project_payload(
            country_pack_id,
            currency_id,
            code="EMAIL-OTHER",
            name="Other email template project",
        ),
    ).json()["id"]
    assert admin_client.get(url(other)).json()["items"] == []
    path = f"{url(other)}/{row['id']}"
    assert admin_client.put(path, json={**BODY, "expected_version": 1}).status_code == 404
    assert (
        admin_client.delete(path, params={"version": 1, "reason": "Wrong project"}).status_code
        == 404
    )
    assert admin_client.get(url(str(uuid.uuid4()))).status_code == 404
    assert len(admin_client.get(url(project_id)).json()["items"]) == 1


def test_email_migration_roundtrip(postgres: None) -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "0054_specification_images")
    command.upgrade(config, "head")
    command.check(config)


def test_email_migration_preserves_templates(admin_client: TestClient, project_id: str) -> None:
    assert admin_client.post(url(project_id), json=BODY).status_code == 201
    with pytest.raises(RuntimeError, match="Retained email templates"):
        command.downgrade(Config("alembic.ini"), "0054_specification_images")
    assert admin_client.get(url(project_id)).json()["items"][0]["body"] == BODY["body"]


@pytest.mark.parametrize("category", ["internal", "clients", "external"])
def test_email_categories(sales_ops_client: TestClient, project_id: str, category: str) -> None:
    result = sales_ops_client.post(url(project_id), json={**BODY, "category": category})
    assert result.status_code == 201
    assert result.json()["category"] == category
    assert sales_ops_client.get(url(project_id)).json()["items"][0]["category"] == category


def test_rich_email_migration(postgres: None) -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "0066_client_links")
    command.upgrade(config, "head")
    command.check(config)


def test_rich_email_roundtrip_and_audit(
    sales_ops_client: TestClient, project_id: str, db: Session
) -> None:
    client = sales_ops_client
    html = '<p onclick="bad()">Hello <b>team</b></p><ol><li>One</li><li>مرحبا</li></ol>'
    result = client.post(url(project_id), json={**BODY, "body_html": html})
    assert result.status_code == 201, result.text
    row = result.json()
    safe = "<p>Hello <b>team</b></p><ol><li>One</li><li>مرحبا</li></ol>"
    assert row["body_html"] == safe
    assert row["body"] == "Hello team\n1. One\n2. مرحبا"
    path = f"{url(project_id)}/{row['id']}"
    assert client.get(url(project_id)).json()["items"][0]["body_html"] == safe
    # An older client editing only the subject must not erase rich content.
    result = client.put(path, json={**BODY, "body": row["body"], "expected_version": 1})
    assert result.status_code == 200, result.text
    assert result.json()["body_html"] == safe
    assert client.delete(path, params={"version": 2, "reason": "Replaced"}).status_code == 204
    event = db.execute(
        text("SELECT before_data FROM audit_events WHERE action = 'email.deleted'")
    ).scalar_one()
    assert event["body_html"] == safe
    assert event["body"] == row["body"]


@pytest.mark.parametrize("explicit_null", [False, True])
def test_plain_email_update_clears_formatting(
    sales_ops_client: TestClient, project_id: str, explicit_null: bool
) -> None:
    client = sales_ops_client
    row = client.post(url(project_id), json={**BODY, "body_html": "<b>Hello</b>"}).json()
    update = {**BODY, "body": "Hello" if explicit_null else "Changed", "expected_version": 1}
    if explicit_null:
        update["body_html"] = None
    result = client.put(f"{url(project_id)}/{row['id']}", json=update)
    assert result.status_code == 200, result.text
    assert result.json()["body_html"] is None
    assert result.json()["body"] == update["body"]


def test_rich_email_downgrade_retains_content(admin_client: TestClient, project_id: str) -> None:
    assert (
        admin_client.post(url(project_id), json={**BODY, "body_html": "<b>Hello</b>"}).status_code
        == 201
    )
    with pytest.raises(RuntimeError, match="Retained email formatting"):
        command.downgrade(Config("alembic.ini"), "0066_client_links")
    assert admin_client.get(url(project_id)).json()["items"][0]["body_html"] == "<b>Hello</b>"


@pytest.mark.parametrize(
    "html",
    [
        "<p><br></p>",
        "<ul><li><br></li></ul>",
        "<script>alert(1)</script>",
        "<p>" + "x" * 20001 + "</p>",
        "<b>" * 101 + "Hello",
        "Hello\x00",
    ],
)
def test_rich_email_validation(sales_ops_client: TestClient, project_id: str, html: str) -> None:
    result = sales_ops_client.post(url(project_id), json={**BODY, "body_html": html})
    assert result.status_code == 422, result.text


def test_rich_email_sanitizer() -> None:
    from app.modules.sales.email_content import clean_email_html

    safe, plain = clean_email_html(
        '<p style="color:red">Hello <b onmouseover="bad()">team</b>'
        '<img src="https://example.invalid/pixel"><script>bad()</script>'
        '<svg><text>hidden</text></svg><a href="javascript:bad()">link</a></p>'
        "<ul><li><i>Item</i></li></ul><strike>Old</strike>"
    )
    assert safe == "<p>Hello <b>team</b>link</p><ul><li><i>Item</i></li></ul><strike>Old</strike>"
    assert plain == "Hello teamlink\n• Item\nOld"
    assert clean_email_html("<b>Keep<script>unclosed")[0] == "<b>Keep</b>"
    assert (
        clean_email_html("&lt;script&gt;literal&lt;/script&gt;")[0]
        == "&lt;script&gt;literal&lt;/script&gt;"
    )
