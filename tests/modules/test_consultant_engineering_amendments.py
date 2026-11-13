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


@pytest.mark.parametrize("state", ["draft", "active", "completed"])
def test_engagement_type_correction_is_scoped_versioned_and_audited(
    manager_member_client: TestClient,
    executive_client: TestClient,
    project_id: str,
    db: Session,
    state: str,
) -> None:
    client = manager_member_client
    target = engagement(client, project_id, "Synthetic quantity surveyor")
    untouched = engagement(client, project_id, "Synthetic other agreement")
    url = root(project_id) + f"/engagements/{target['id']}"
    stage = None
    if state != "draft":
        target = client.post(url + "/activate").json()
        stage = client.post(url + "/stages", json={"name": "Synthetic design"}).json()
    if state == "completed":
        target = client.post(url + "/complete").json()
    body = {
        "consultant_name": target["consultant_name"],
        "agreement_reference": target["agreement_reference"],
        "engagement_type": "subconsultant",
        "expected_updated_at": target["updated_at"],
    }
    assert executive_client.put(url, json=body).status_code == 403
    response = client.put(url, json=body)
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed["id"] == target["id"] and changed["status"] == state
    assert changed["engagement_type"] == "subconsultant"
    assert client.put(url, json=body).status_code == 409
    workspace = client.get(root(project_id)).json()
    assert (
        next(row for row in workspace["engagements"] if row["id"] == target["id"])[
            "engagement_type"
        ]
        == "subconsultant"
    )
    assert (
        next(row for row in workspace["engagements"] if row["id"] == untouched["id"]) == untouched
    )
    if stage:
        assert workspace["stages"][0]["id"] == stage["id"]
    audit = db.scalar(
        select(AuditEvent).where(AuditEvent.action == "consultant.engagement_updated")
    )
    assert audit.before_data["engagement_type"] == "main"
    assert audit.after_data["engagement_type"] == "subconsultant"
    assert audit.actor_user_id
    # The same editor can correct it back without creating a new agreement.
    response = client.put(
        url, json={**body, "engagement_type": "main", "expected_updated_at": changed["updated_at"]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["engagement_type"] == "main"


def test_active_subconsultant_cannot_replace_another_active_main(
    manager_member_client: TestClient, project_id: str
) -> None:
    client = manager_member_client
    main = engagement(client, project_id, "Synthetic main")
    main_url = root(project_id) + f"/engagements/{main['id']}"
    assert client.post(main_url + "/activate").status_code == 200
    sub = client.post(
        root(project_id) + "/engagements",
        json={
            "consultant_name": "Synthetic sub",
            "agreement_reference": "SUB-TEST",
            "engagement_type": "subconsultant",
        },
    ).json()
    url = root(project_id) + f"/engagements/{sub['id']}"
    sub = client.post(url + "/activate").json()
    body = {
        "consultant_name": sub["consultant_name"],
        "agreement_reference": sub["agreement_reference"],
        "engagement_type": "main",
        "expected_updated_at": sub["updated_at"],
    }
    response = client.put(url, json=body)
    assert response.status_code == 409, response.text
    workspace = client.get(root(project_id)).json()
    assert workspace["active_engagement"]["id"] == main["id"]
    assert (
        next(row for row in workspace["engagements"] if row["id"] == sub["id"])["engagement_type"]
        == "subconsultant"
    )
