"""Reusable answers persist, isolate projects and retain deleted evidence."""

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
    return f"/api/v1/projects/{project}/faqs"


BODY = {"question": "Can I arrange a visit?", "answer": "Contact our team.\nنرحب بكم"}


def test_faq_lifecycle_and_audit(
    sales_ops_client: TestClient, project_id: str, db: Session
) -> None:
    client = sales_ops_client
    assert client.get(url(project_id)).json() == {"items": [], "can_edit": True}
    result = client.post(url(project_id), json=BODY)
    assert result.status_code == 201, result.text
    row = result.json()
    path = f"{url(project_id)}/{row['id']}"
    assert row["answer"] == BODY["answer"]
    update = {**BODY, "answer": "Updated\nAnswer", "expected_version": 1}
    assert client.put(path, json=update).status_code == 200
    assert client.put(path, json=update).status_code == 409
    assert client.delete(path, params={"version": 1, "reason": "Old"}).status_code == 409
    assert client.delete(path, params={"version": 2, "reason": " "}).status_code == 422
    assert client.get(url(project_id)).json()["items"][0]["answer"] == "Updated\nAnswer"
    assert client.delete(path, params={"version": 2, "reason": "Outdated"}).status_code == 204
    assert client.delete(path, params={"version": 2, "reason": "Outdated"}).status_code == 404
    assert client.get(url(project_id)).json()["items"] == []
    events = db.execute(
        text(
            "SELECT action, before_data, reason FROM audit_events "
            "WHERE entity_type = 'commercial_faq' ORDER BY occurred_at"
        )
    ).all()
    assert [event[0] for event in events] == ["faq.created", "faq.updated", "faq.deleted"]
    assert events[-1][1]["answer"] == "Updated\nAnswer"
    assert events[-1][2] == "Outdated"


@pytest.mark.parametrize(
    "field,value",
    [
        ("question", " \n"),
        ("answer", "\t"),
        ("question", "x" * 501),
        ("answer", "x" * 20001),
        ("answer", None),
    ],
)
def test_faq_validation(
    sales_ops_client: TestClient, project_id: str, field: str, value: str | None
) -> None:
    assert sales_ops_client.post(url(project_id), json={**BODY, field: value}).status_code == 422
    assert sales_ops_client.get(url(project_id)).json()["items"] == []


def test_faq_permissions(
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
    assert advisor_client.get(url(project_id)).json()["items"][0]["answer"] == BODY["answer"]
    for client in [advisor_client, engineer_client]:
        assert client.post(url(project_id), json=BODY).status_code == 403
        assert client.put(path, json={**BODY, "expected_version": 1}).status_code == 403
        assert client.delete(path, params={"version": 1, "reason": "Denied"}).status_code == 403
    assert engineer_client.get(url(project_id)).status_code == 403
    user = make_user(db, email="faq-phase@example.com", roles=("sales_operations",))
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
    outsider = make_user(db, email="faq-outsider@example.com", roles=("sales_operations",))
    with client_for(outsider.email) as hidden:
        assert hidden.get(url(project_id)).status_code == 404


def test_faq_project_isolation(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    row = admin_client.post(url(project_id), json=BODY).json()
    other = admin_client.post(
        "/api/v1/projects",
        json=project_payload(
            country_pack_id, currency_id, code="FAQ-OTHER", name="Other FAQ project"
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


def test_faq_migration_roundtrip(postgres: None) -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "0038_commission_beneficiaries")
    command.upgrade(config, "head")
    command.check(config)


def test_faq_migration_preserves_answers(admin_client: TestClient, project_id: str) -> None:
    assert admin_client.post(url(project_id), json=BODY).status_code == 201
    with pytest.raises(RuntimeError, match="Retained FAQs"):
        command.downgrade(Config("alembic.ini"), "0038_commission_beneficiaries")
    assert admin_client.get(url(project_id)).json()["items"][0]["answer"] == BODY["answer"]
