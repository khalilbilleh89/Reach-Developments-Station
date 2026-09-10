"""PostgreSQL capture, historical authorization and source independence."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.management_reporting.canonical import content_hash
from app.modules.management_reporting.schemas import SnapshotOut
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access

ROOT = "/api/v1/portfolio/reporting"


def capture(client: TestClient, project_id: str | None = None) -> dict[str, Any]:
    response = client.post(
        f"{ROOT}/snapshots",
        json={
            "scope": "project" if project_id else "portfolio",
            **({"project_id": project_id} if project_id else {}),
            "label": "Management review",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_capture_roundtrip_board_and_no_backdating(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    result = capture(admin_client, project_id)
    snapshot = SnapshotOut.model_validate(result)
    assert content_hash(snapshot) == result["content_hash"]
    assert result["project_count"] == 1
    assert len(result["payload"]["outlooks"]) == 3
    assert result["payload"]["projects"][0]["project_id"] == project_id
    # Missing governed sources are business unavailability, not a capture error.
    captured_project = result["payload"]["projects"][0]
    cash_coverage = next(
        row
        for row in captured_project["risk_evaluations"]
        if row["risk_code"] == "FORECAST_CASH_DEFICIT"
    )
    source_project = admin_client.get(f"/api/v1/portfolio/projects/{project_id}").json()
    source_coverage = next(
        row
        for row in source_project["risk_evaluations"]
        if row["risk_code"] == "FORECAST_CASH_DEFICIT"
    )
    assert cash_coverage["availability"] == "unavailable"
    assert cash_coverage["reason"] and cash_coverage["reason"] == source_coverage["reason"]
    assert all(
        m["amount"] is None or isinstance(m["amount"], str)
        for m in result["payload"]["overview"]["money"]
    )
    url = f"{ROOT}/snapshots/{result['id']}"
    assert admin_client.get(url).json() == result
    before = admin_client.get(url + "/board-pack").json()
    admin_client.patch(f"/api/v1/projects/{project_id}", json={"name": "Renamed after snapshot"})
    assert admin_client.get(url + "/board-pack").json() == before
    assert admin_client.patch(url, json={"label": "Rewrite"}).status_code in (404, 405)
    assert admin_client.delete(url).status_code in (404, 405)
    assert (
        admin_client.post(
            f"{ROOT}/snapshots", json={"scope": "portfolio", "as_of_date": "2020-01-01"}
        ).status_code
        == 422
    )
    assert admin_client.get(f"{ROOT}/snapshots?limit=1").json()["total"] == 1
    assert admin_client.get(f"{ROOT}/snapshots?limit=101").status_code == 422


def test_read_revocation_and_viewer_write_refusal(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    viewer = make_user(db, email="snapshot-viewer@example.com", roles=("executive_viewer",))
    grant_access(admin_client, project_id, viewer)
    result = capture(admin_client, project_id)
    url = f"{ROOT}/snapshots/{result['id']}"
    with client_for(viewer.email) as client:
        assert client.get(url).status_code == 200
        assert client.post(f"{ROOT}/snapshots", json={"scope": "portfolio"}).status_code == 403
        response = admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{viewer.id}", json={"is_active": False}
        )
        assert response.status_code in (200, 204), response.text
        assert client.get(url).status_code == 404
        assert client.get(url + "/board-pack").status_code == 404
        assert client.get(f"{ROOT}/snapshots").json()["total"] == 0
        assert (
            client.get(
                f"{ROOT}/comparisons?from_snapshot_id={result['id']}&to_snapshot_id={uuid.uuid4()}"
            ).status_code
            == 404
        )


def test_technical_failure_rolls_back_capture(
    admin_client: TestClient, project_id: str, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.management_reporting import snapshot

    def failed(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Injected owner read failure")

    monkeypatch.setattr(snapshot.outlook, "page", failed)
    with pytest.raises(RuntimeError, match="Injected owner"):
        capture(admin_client, project_id)
    assert db.scalar(text("SELECT count(*) FROM management_report_snapshots")) == 0
    assert db.scalar(text("SELECT count(*) FROM management_report_snapshot_projects")) == 0


def test_comparison_is_reproducible_and_rejects_reverse_order(
    admin_client: TestClient, project_id: str
) -> None:
    a = capture(admin_client, project_id)
    b = capture(admin_client, project_id)
    url = f"{ROOT}/comparisons?from_snapshot_id={a['id']}&to_snapshot_id={b['id']}"
    response = admin_client.get(url)
    assert response.status_code == 200, response.text
    assert response.json()["composition_changed"] is False
    assert response.json()["execution"]["completed"] == 0
    admin_client.patch(f"/api/v1/projects/{project_id}", json={"name": "Different now"})
    assert admin_client.get(url).json() == response.json()
    assert (
        admin_client.get(
            f"{ROOT}/comparisons?from_snapshot_id={b['id']}&to_snapshot_id={a['id']}"
        ).status_code
        == 409
    )
