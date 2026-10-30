"""Active agreement corrections retain identity, programme and audited history."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access, project_payload
from tests.modules.test_consultant_engineering_payments import (
    PDF,
    completed_stage,
    expected,
    record,
)
from tests.modules.test_consultant_engineering_review import engagement, root


@pytest.mark.parametrize("terminal", ["complete", "terminate"])
def test_active_and_completed_agreement_corrections_keep_identity_and_history(
    manager_member_client: TestClient,
    executive_client: TestClient,
    project_id: str,
    db: Session,
    terminal: str,
) -> None:
    client = manager_member_client
    created = engagement(client, project_id)
    url = f"{root(project_id)}/engagements/{created['id']}"
    active = client.post(url + "/activate").json()
    stage = client.post(url + "/stages", json={"name": "Concept"}).json()
    body = {
        "consultant_name": "Updated consultant",
        "agreement_reference": "CE-REV-2",
        "agreement_date": "2026-08-01",
        "planned_start_date": "2026-09-01",
        "planned_completion_date": "2027-01-01",
        "scope_summary": "Updated scope",
        "notes": "Owner correction",
        "expected_updated_at": active["updated_at"],
    }
    assert executive_client.put(url, json=body).status_code == 403
    invalid = client.put(url, json={**body, "planned_completion_date": "2026-01-01"})
    assert invalid.status_code == 422
    changed = client.put(url, json=body)
    assert changed.status_code == 200, changed.text
    assert changed.json()["id"] == created["id"] and changed.json()["status"] == "active"
    assert client.put(url, json=body).status_code == 409
    workspace = client.get(root(project_id)).json()
    assert workspace["stages"][0]["id"] == stage["id"]
    assert workspace["active_engagement"]["scope_summary"] == "Updated scope"
    audit = db.scalar(
        select(AuditEvent).where(AuditEvent.action == "consultant.engagement_updated")
    )
    assert audit.before_data["consultant_name"] == "Main"
    assert audit.after_data["consultant_name"] == "Updated consultant"
    terminal_row = client.post(url + "/" + terminal)
    assert terminal_row.status_code == 200
    assert client.put(url, json=body).status_code == 409
    corrected = client.put(
        url, json={**body, "expected_updated_at": terminal_row.json()["updated_at"]}
    )
    assert corrected.status_code == (200 if terminal == "complete" else 409)
    if terminal == "complete":
        assert corrected.json()["status"] == "completed"
        assert corrected.json()["id"] == created["id"]


@pytest.mark.parametrize("kind", ["main", "subconsultant"])
def test_boss_corrects_completed_details_and_reopens_without_resetting_evidence(
    manager_member_client: TestClient,
    second_finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
    kind: str,
) -> None:
    client = manager_member_client
    agreement_row, stage = completed_stage(client, project_id, kind)
    payment = record(client, project_id, stage, currency_id)
    payment_url = root(project_id) + f"/payments/{payment['id']}"
    confirmed = second_finance_client.post(
        payment_url + "/confirm", json={"expected": expected(payment)}
    )
    assert confirmed.status_code == 200, confirmed.text
    proof = client.post(payment_url + "/proofs?filename=proof.pdf", content=PDF)
    assert proof.status_code == 201, proof.text
    url = root(project_id) + f"/engagements/{agreement_row['id']}"
    completed = client.post(url + "/complete").json()
    boss = make_user(db, email="boss-design@example.com", roles=("master_admin",))
    boss_client = client_for(boss.email)
    edited = boss_client.put(
        url,
        json={
            "consultant_name": "Corrected Studio",
            "agreement_reference": completed["agreement_reference"],
            "scope_summary": "Corrected after testing",
            "expected_updated_at": completed["updated_at"],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "completed"
    assert edited.json()["engagement_type"] == kind
    body = {
        "expected_updated_at": edited.json()["updated_at"],
        "reason": "Completed by mistake during testing",
    }
    reopened = boss_client.post(url + "/reopen", json=body)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["id"] == agreement_row["id"]
    assert reopened.json()["status"] == "active"
    workspace = boss_client.get(root(project_id)).json()
    assert workspace["stages"][0]["id"] == stage["id"]
    assert workspace["stages"][0]["status"] == "completed"
    assert workspace["stages"][0]["actual_completion_date"] == "2026-01-01"
    payments = boss_client.get(root(project_id) + "/payments").json()
    assert payments["payments"][0]["expense"]["id"] == payment["expense"]["id"]
    assert payments["payments"][0]["expense"]["status"] == "confirmed"
    assert payments["stages"][0]["confirmed_paid_amount"] == "1050.00"
    file_url = payment_url + f"/proofs/{proof.json()['id']}/file"
    assert boss_client.get(file_url).content == PDF
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "consultant.engagement_reopened")
    ).all()
    assert len(events) == 1
    assert events[0].reason == body["reason"]
    assert events[0].actor_user_id == boss.id
    assert events[0].before_data["status"] == "completed"
    assert events[0].after_data["status"] == "active"
    assert (
        db.scalar(
            select(AuditEvent.id).where(AuditEvent.action == "consultant.engagement_completed")
        )
        is not None
    )


def test_reopen_requires_completed_version_reason_editor_and_correct_project(
    manager_member_client: TestClient,
    executive_client: TestClient,
    admin_client: TestClient,
    manager: User,
    project_id: str,
    currency_id: str,
    country_pack_id: str,
) -> None:
    client = manager_member_client
    created = engagement(client, project_id)
    url = root(project_id) + f"/engagements/{created['id']}"
    request = {"expected_updated_at": created["updated_at"], "reason": "Testing correction"}
    assert client.post(url + "/reopen", json=request).status_code == 409
    assert client.post(url + "/activate").status_code == 200
    completed = client.post(url + "/complete").json()
    assert client.post(url + "/reopen", json=request).status_code == 409
    request["expected_updated_at"] = completed["updated_at"]
    assert executive_client.post(url + "/reopen", json=request).status_code == 403
    assert client.post(url + "/reopen", json={**request, "reason": " "}).status_code == 422
    assert client.post(url + "/reopen", json={}).status_code == 422
    other = admin_client.post(
        "/api/v1/projects", json=project_payload(country_pack_id, currency_id, code="REOPEN-OTHER")
    ).json()["id"]
    grant_access(admin_client, other, manager)
    assert (
        client.post(root(other) + f"/engagements/{created['id']}/reopen", json=request).status_code
        == 404
    )
    assert (
        client.post(
            root(project_id) + f"/engagements/{uuid.uuid4()}/reopen", json=request
        ).status_code
        == 404
    )
    assert client.post(url + "/reopen", json=request).status_code == 200
    assert client.post(url + "/reopen", json=request).status_code == 409
    assert client.post(url + "/terminate").status_code == 200
    assert client.post(url + "/reopen", json=request).status_code == 409


def test_reopen_preserves_one_active_main_and_independent_subconsultants(
    manager_member_client: TestClient, project_id: str
) -> None:
    client = manager_member_client
    old = engagement(client, project_id, "Old main")
    old_url = root(project_id) + f"/engagements/{old['id']}"
    assert client.post(old_url + "/activate").status_code == 200
    old = client.post(old_url + "/complete").json()
    replacement = engagement(client, project_id, "Current main")
    assert (
        client.post(root(project_id) + f"/engagements/{replacement['id']}/activate").status_code
        == 200
    )
    request = {"expected_updated_at": old["updated_at"], "reason": "Testing correction"}
    assert client.post(old_url + "/reopen", json=request).status_code == 409
    sub = client.post(
        root(project_id) + "/engagements",
        json={
            "consultant_name": "Landscape",
            "agreement_reference": "SUB-1",
            "engagement_type": "subconsultant",
        },
    ).json()
    sub_url = root(project_id) + f"/engagements/{sub['id']}"
    assert client.post(sub_url + "/activate").status_code == 200
    sub = client.post(sub_url + "/complete").json()
    assert (
        client.post(
            sub_url + "/reopen", json={**request, "expected_updated_at": sub["updated_at"]}
        ).status_code
        == 200
    )
    workspace = client.get(root(project_id)).json()
    assert workspace["active_engagement"]["id"] == replacement["id"]
    assert (
        next(item for item in workspace["engagements"] if item["id"] == old["id"])["status"]
        == "completed"
    )
