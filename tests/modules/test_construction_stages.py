"""Unit checklist progress is independent of certified milestones and delivery."""

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.modules.conftest import construction_url


def test_completion_correction_and_stale_write(
    manager_member_client: TestClient,
    project_id: str,
    unit_id: str,
    second_unit: str,
) -> None:
    client = manager_member_client
    root = construction_url(project_id)
    created = client.post(
        f"{root}/stages", json={"name": "Structure", "planned_date": "2026-08-01"}
    )
    assert created.status_code == 201, created.text
    stage = created.json()["id"]
    path = f"{root}/units/{unit_id}/stages"
    before = client.get(path).json()
    assert before["completed_count"] == 0
    body = {"completed_date": "2026-08-02", "reason": "Site inspection", "expected_revision": 0}
    saved = client.post(f"{path}/{stage}/completion", json=body)
    assert saved.status_code == 204, saved.text
    current = client.get(path).json()
    assert current["completed_count"] == 1
    assert current["delivery_status"] == before["delivery_status"]
    assert client.get(f"{root}/units/{second_unit}/stages").json()["completed_count"] == 0
    assert client.post(f"{path}/{stage}/completion", json=body).status_code == 409
    reopened = client.post(
        f"{path}/{stage}/completion",
        json={
            "completed_date": None,
            "reason": "Inspection correction",
            "expected_revision": 1,
        },
    )
    assert reopened.status_code == 204, reopened.text
    current = client.get(path).json()
    assert current["completed_count"] == 0
    assert len(current["stages"][0]["history"]) == 2
    assert current["stages"][0]["history"][1]["completed_date"] == "2026-08-02"


def test_stage_validation_and_read_only_roles(
    manager_member_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    unit_id: str,
) -> None:
    root = construction_url(project_id)
    client = manager_member_client
    assert client.post(f"{root}/stages", json={"name": " "}).status_code == 422
    response = client.post(f"{root}/stages", json={"name": "Finishes"})
    assert response.status_code == 201, response.text
    assert client.post(f"{root}/stages", json={"name": " finishes "}).status_code == 409
    assert advisor_client.get(f"{root}/units/{unit_id}/stages").status_code == 200
    assert advisor_client.get(f"{root}/summary").status_code == 403
    assert advisor_client.post(f"{root}/stages", json={"name": "Roof"}).status_code == 403
    path = f"{root}/units/{unit_id}/stages/{response.json()['id']}/completion"
    body = {
        "completed_date": str(date.today() + timedelta(days=2)),
        "reason": "Future",
        "expected_revision": 0,
    }
    assert client.post(path, json=body).status_code == 422
    body["completed_date"] = "2026-08-01"
    assert advisor_client.post(path, json=body).status_code == 403
    assert client.get(f"{root}/units/{uuid.uuid4()}/stages").status_code == 404


def test_stage_requires_real_project(manager_member_client: TestClient) -> None:
    assert (
        manager_member_client.get(f"{construction_url(str(uuid.uuid4()))}/stages").status_code
        == 404
    )
