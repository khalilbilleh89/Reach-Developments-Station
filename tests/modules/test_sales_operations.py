"""Operations follows real buyers, retains evidence and isolates project scope."""

import uuid
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access, record_legal, sales_url


def url(project: str) -> str:
    return f"/api/v1/projects/{project}/operations"


def read(client: TestClient, project: str) -> dict[str, Any]:
    result = client.get(url(project))
    assert result.status_code == 200, result.text
    return result.json()


def payload(
    data: dict[str, Any],
    buyer: str,
    *,
    purpose: str = "golden_visa",
    progress: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row = next(row for row in data["buyers"] if row["id"] == buyer)
    return {
        "expected_version": row["version"],
        "pipeline_version": data["pipeline_version"],
        "purpose": purpose,
        "progress": progress or [],
        "reason": "Verified the buyer paperwork",
    }


def stage_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_version": data["pipeline_version"],
        "stages": [
            {key: stage[key] for key in ("id", "label", "section", "is_active")}
            for stage in data["stages"]
        ],
    }


def test_all_buyers_appear_without_read_side_writes(
    sales_ops_client: TestClient, project_id: str, buyer_id: str, db: Session
) -> None:
    data = read(sales_ops_client, project_id)
    assert data["buyer_count"] == 1
    assert data["buyers"][0]["id"] == buyer_id
    assert len(data["stages"]) == 9
    assert data["purpose_unknown_count"] == 1
    assert data["buyers"][0]["applicable_count"] == 7
    assert all(row["completed"] is None for row in data["buyers"][0]["milestones"])
    assert db.scalar(text("SELECT count(*) FROM operation_pipelines")) == 0


def test_dates_purpose_totals_and_stale_writes(
    sales_ops_client: TestClient, project_id: str, buyer_id: str
) -> None:
    data = read(sales_ops_client, project_id)
    stage = data["stages"][0]["id"]
    body = payload(
        data,
        buyer_id,
        progress=[{"stage_id": stage, "completed": True, "completed_date": "2026-09-21"}],
    )
    assert (
        sales_ops_client.put(f"{url(project_id)}/buyers/{buyer_id}", json=body).status_code == 204
    )
    assert (
        sales_ops_client.put(f"{url(project_id)}/buyers/{buyer_id}", json=body).status_code == 409
    )
    data = read(sales_ops_client, project_id)
    assert data["summaries"][0]["yes"] == 1
    assert data["golden_visa_count"] == 1
    assert data["buyers"][0]["completed_count"] == 1
    assert data["buyers"][0]["applicable_count"] == 9
    body = payload(data, buyer_id, purpose="investment_only")
    assert (
        sales_ops_client.put(f"{url(project_id)}/buyers/{buyer_id}", json=body).status_code == 204
    )
    data = read(sales_ops_client, project_id)
    assert data["summaries"][-1]["not_applicable"] == 1
    assert data["summaries"][-1]["applicable"] == 0
    bad = payload(
        data,
        buyer_id,
        progress=[{"stage_id": stage, "completed": False, "completed_date": "2026-09-21"}],
    )
    assert sales_ops_client.put(f"{url(project_id)}/buyers/{buyer_id}", json=bad).status_code == 422


def test_stage_reorder_rename_add_delete_and_retained_history(
    sales_ops_client: TestClient, project_id: str, buyer_id: str, db: Session
) -> None:
    data = read(sales_ops_client, project_id)
    stage = data["stages"][0]["id"]
    body = payload(
        data, buyer_id, progress=[{"stage_id": stage, "completed": True, "completed_date": None}]
    )
    assert (
        sales_ops_client.put(f"{url(project_id)}/buyers/{buyer_id}", json=body).status_code == 204
    )
    data = read(sales_ops_client, project_id)
    config = stage_payload(data)
    config["stages"].reverse()
    config["stages"][-1]["label"] = "EOI confirmed"
    config["stages"].append({"label": "Biometrics", "section": "golden_visa"})
    assert sales_ops_client.put(f"{url(project_id)}/pipeline", json=config).status_code == 204
    data = read(sales_ops_client, project_id)
    assert data["stages"][-2]["id"] == stage
    assert data["summaries"][-2]["yes"] == 1
    assert data["summaries"][-2]["missing_dates"] == 1
    added = data["stages"][-1]["id"]
    assert (
        sales_ops_client.delete(
            f"{url(project_id)}/stages/{added}",
            params={"version": data["pipeline_version"], "reason": "Unused stage"},
        ).status_code
        == 204
    )
    data = read(sales_ops_client, project_id)
    assert (
        sales_ops_client.delete(
            f"{url(project_id)}/stages/{added}",
            params={"version": data["pipeline_version"], "reason": "Repeat"},
        ).status_code
        == 404
    )
    assert (
        sales_ops_client.delete(
            f"{url(project_id)}/stages/{stage}",
            params={"version": data["pipeline_version"], "reason": "Retire with evidence"},
        ).status_code
        == 204
    )
    data = read(sales_ops_client, project_id)
    assert not next(row for row in data["stages"] if row["id"] == stage)["is_active"]
    assert db.scalar(text("SELECT count(*) FROM operation_progress")) == 1
    assert (
        db.scalar(
            text("SELECT count(*) FROM audit_events WHERE action = 'operations.stage_retired'")
        )
        == 1
    )


def test_delete_manual_progress_preserves_buyer_and_audit(
    sales_ops_client: TestClient, project_id: str, buyer_id: str, db: Session
) -> None:
    data = read(sales_ops_client, project_id)
    body = payload(
        data,
        buyer_id,
        progress=[
            {"stage_id": data["stages"][0]["id"], "completed": True, "completed_date": "2026-09-20"}
        ],
    )
    assert (
        sales_ops_client.put(f"{url(project_id)}/buyers/{buyer_id}", json=body).status_code == 204
    )
    data = read(sales_ops_client, project_id)
    stale = payload(data, buyer_id)
    assert (
        sales_ops_client.delete(
            f"{url(project_id)}/buyers/{buyer_id}",
            params={"version": 1, "reason": "Entered on wrong buyer"},
        ).status_code
        == 204
    )
    assert (
        sales_ops_client.delete(
            f"{url(project_id)}/buyers/{buyer_id}", params={"version": 1, "reason": "Repeat"}
        ).status_code
        == 409
    )
    assert (
        sales_ops_client.put(f"{url(project_id)}/buyers/{buyer_id}", json=stale).status_code == 409
    )
    assert read(sales_ops_client, project_id)["buyer_count"] == 1
    assert db.scalar(text("SELECT count(*) FROM operation_progress")) == 0
    audit = db.execute(
        text(
            "SELECT before_data FROM audit_events "
            "WHERE action = 'operations.buyer_progress_deleted'"
        )
    ).scalar_one()
    assert audit["progress"][0]["completed_date"] == "2026-09-20"


def test_spa_is_linked_and_reversals_are_reflected(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    project_id: str,
    submitted_sale: str,
    buyer_id: str,
) -> None:
    for kind, day in (
        ("spa_drafted", "2026-02-01"),
        ("spa_issued", "2026-02-02"),
        ("buyer_signed", "2026-02-03"),
    ):
        record_legal(legal_client, project_id, submitted_sale, kind, day)
    data = read(sales_ops_client, project_id)
    stage = next(stage for stage in data["stages"] if stage["source"] == "buyer_signed_spa")
    milestone = next(
        row for row in data["buyers"][0]["milestones"] if row["stage_id"] == stage["id"]
    )
    assert milestone["completed"] is True
    assert milestone["completed_date"] == "2026-02-03"
    assert milestone["editable"] is False
    body = payload(
        data,
        buyer_id,
        progress=[{"stage_id": stage["id"], "completed": False, "completed_date": None}],
    )
    assert (
        sales_ops_client.put(f"{url(project_id)}/buyers/{buyer_id}", json=body).status_code == 409
    )
    result = legal_client.get(f"{sales_url(project_id)}/contracts/{submitted_sale}/legal-events")
    events = result.json()
    if isinstance(events, dict):
        events = events["events"]
    event = next(row for row in events if row["event_type"] == "buyer_signed")
    reversed_event = legal_client.post(
        f"{sales_url(project_id)}/legal-events/{event['id']}/reverse",
        json={"reason": "Wrong signature", "event_date": "2026-02-04"},
    )
    assert reversed_event.status_code == 200, reversed_event.text
    data = read(sales_ops_client, project_id)
    assert (
        next(row for row in data["buyers"][0]["milestones"] if row["stage_id"] == stage["id"])[
            "completed"
        ]
        is False
    )


def test_permissions_wrong_project_and_selected_phase(
    sales_ops_client: TestClient,
    finance_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    buyer_id: str,
    db: Session,
) -> None:
    data = read(sales_ops_client, project_id)
    body = payload(data, buyer_id)
    assert finance_client.put(f"{url(project_id)}/buyers/{buyer_id}", json=body).status_code == 403
    assert (
        finance_client.put(f"{url(project_id)}/pipeline", json=stage_payload(data)).status_code
        == 403
    )
    assert (
        finance_client.delete(
            f"{url(project_id)}/buyers/{buyer_id}", params={"version": 0, "reason": "Denied"}
        ).status_code
        == 403
    )
    assert (
        sales_ops_client.put(f"{url(uuid.uuid4())}/buyers/{buyer_id}", json=body).status_code == 404
    )
    assert (
        sales_ops_client.put(f"{url(project_id)}/buyers/{uuid.uuid4()}", json=body).status_code
        == 404
    )
    user = make_user(db, email="phase-ops@example.com", roles=("sales_operations",))
    grant_access(admin_client, project_id, user)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{user.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    with client_for(user.email) as restricted:
        assert restricted.get(url(project_id)).status_code == 404
        assert restricted.put(f"{url(project_id)}/buyers/{buyer_id}", json=body).status_code == 404


def test_operations_migration_roundtrip(postgres: None) -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "0035_merge_company_current_costs")
    command.upgrade(config, "head")
    command.check(config)


def test_operations_migration_refuses_retained_evidence(
    sales_ops_client: TestClient, project_id: str, buyer_id: str
) -> None:
    data = read(sales_ops_client, project_id)
    assert (
        sales_ops_client.put(
            f"{url(project_id)}/buyers/{buyer_id}", json=payload(data, buyer_id)
        ).status_code
        == 204
    )
    with pytest.raises(RuntimeError, match="retained"):
        command.downgrade(Config("alembic.ini"), "0035_merge_company_current_costs")
