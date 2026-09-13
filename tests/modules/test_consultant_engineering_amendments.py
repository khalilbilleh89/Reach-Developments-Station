"""Active agreement corrections retain identity, programme and audited history."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from tests.modules.test_consultant_engineering_review import engagement, root


@pytest.mark.parametrize("terminal", ["complete", "terminate"])
def test_active_agreement_edit_preserves_programme_and_rejects_stale_or_historical_writes(
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
    assert client.post(url + "/" + terminal).status_code == 200
    assert (
        client.put(
            url, json={**body, "expected_updated_at": changed.json()["updated_at"]}
        ).status_code
        == 409
    )
