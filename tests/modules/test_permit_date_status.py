"""Actual date entry drives status atomically without a second user action."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from tests.modules.conftest import PROJECTS, permit_payload


@pytest.mark.parametrize("changes", [{}, {"notes": "Reviewed"}])
def test_save_reconciles_legacy_preparing_with_unchanged_dates(
    admin_client: TestClient, project_id: str, db: Session, changes: dict
) -> None:
    url = f"{PROJECTS}/{project_id}/permits"
    row = admin_client.post(url, json=permit_payload(issue_date="2025-01-10")).json()
    db.execute(text("UPDATE permits SET status='preparing' WHERE id=:id"), {"id": row["id"]})
    db.commit()
    saved = admin_client.patch(f"{url}/{row['id']}", json=changes)
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "completed"
    assert saved.json()["status_effective_date"] == "2025-01-10"
    history = admin_client.get(f"{url}/{row['id']}/status-history").json()
    assert any(
        event["from_status"] == "preparing" and event["to_status"] == "completed"
        for event in history
    )
    assert admin_client.patch(f"{url}/{row['id']}", json=changes).status_code == 200
    assert admin_client.get(f"{url}/{row['id']}/status-history").json() == history
    register = admin_client.get(url, params={"status": "completed"}).json()
    assert any(permit["id"] == row["id"] for permit in register["permits"])


def test_legacy_date_reconciliation_migration(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    url = f"{PROJECTS}/{project_id}/permits"
    rows = []
    for code, status, issue in [
        ("ISSUED", "preparing", "2025-02-01"),
        ("SUBMITTED", "not_started", None),
        ("HELD", "on_hold", "2025-02-01"),
        ("DELETED", "preparing", "2025-02-01"),
        ("UNDATED", "preparing", None),
    ]:
        fields = {"issue_date": issue}
        if code == "SUBMITTED":
            fields["actual_submission_date"] = "2025-01-01"
        row = admin_client.post(url, json=permit_payload(permit_code=code, **fields)).json()
        db.execute(
            text("UPDATE permits SET status=:status WHERE id=:id"),
            {"status": status, "id": row["id"]},
        )
        if code == "DELETED":
            db.execute(text("UPDATE permits SET deleted_at=now() WHERE id=:id"), {"id": row["id"]})
        rows.append(row)
        db.commit()
    db.commit()
    old_history = admin_client.get(f"{url}/{rows[0]['id']}/status-history").json()
    command.downgrade(config, "0063_plan_sources")
    command.upgrade(config, "head")
    command.check(config)
    db.expire_all()
    states = dict(db.execute(text("SELECT permit_code, status FROM permits")).all())
    assert states == {
        "ISSUED": "completed",
        "SUBMITTED": "submitted",
        "HELD": "on_hold",
        "DELETED": "preparing",
        "UNDATED": "preparing",
    }
    audits = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "permit.dates_reconciled")
    ).all()
    assert len(audits) == 2
    audit = next(item for item in audits if item.entity_id == uuid.UUID(rows[0]["id"]))
    assert audit.actor_user_id is None and audit.source == "migration"
    assert audit.before_data["status"] == "preparing"
    assert audit.after_data["status"] == "completed"
    assert audit.after_data["issue_date"] == "2025-02-01"
    assert admin_client.get(f"{url}/{rows[0]['id']}/status-history").json() == old_history
    db.rollback()
    command.downgrade(config, "0063_plan_sources")
    command.upgrade(config, "head")
    assert (
        len(
            db.scalars(
                select(AuditEvent).where(AuditEvent.action == "permit.dates_reconciled")
            ).all()
        )
        == 2
    )


@pytest.mark.parametrize(
    "field,status",
    [
        ("actual_submission_date", "submitted"),
        ("accepted_for_review_date", "accepted_for_review"),
        ("comments_received_date", "comments_received"),
        ("resubmission_date", "resubmission"),
        ("issue_date", "completed"),
        ("renewal_date", "renewed"),
    ],
)
@pytest.mark.parametrize("on_create", [True, False])
def test_actual_dates_drive_status(
    admin_client: TestClient, project_id: str, field: str, status: str, on_create: bool
) -> None:
    url = f"{PROJECTS}/{project_id}/permits"
    dates = {field: "2025-01-10"}
    response = admin_client.post(url, json=permit_payload(**(dates if on_create else {})))
    assert response.status_code == 201, response.text
    url += f"/{response.json()['id']}"
    if not on_create:
        response = admin_client.patch(url, json=dates)
    assert response.status_code in (200, 201), response.text
    assert response.json()["status"] == status
    assert response.json()["status_effective_date"] == "2025-01-10"
    history = admin_client.get(url + "/status-history").json()
    assert len(history) == 1
    assert history[0]["to_status"] == status
    assert admin_client.patch(url, json=dates).status_code == 200
    assert len(admin_client.get(url + "/status-history").json()) == 1


def test_corrections_keep_history_and_ignore_forecasts(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    url = f"{PROJECTS}/{project_id}/permits"
    response = admin_client.post(
        url,
        json=permit_payload(
            actual_submission_date="2025-01-01",
            issue_date="2025-01-01",
            forecast_issue_date="2030-01-01",
            expiry_date="2031-01-01",
        ),
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "completed"
    url += f"/{response.json()['id']}"
    corrected = admin_client.patch(url, json={"issue_date": "2025-02-01"})
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["status_effective_date"] == "2025-02-01"
    correction = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "permit.status_changed")
    ).one()
    assert correction.actor_user_id is not None
    assert correction.before_data["status_effective_date"] == "2025-01-01"
    assert correction.after_data["status_effective_date"] == "2025-02-01"
    cleared = admin_client.patch(url, json={"issue_date": None})
    assert cleared.json()["status"] == "submitted"
    assert len(admin_client.get(url + "/status-history").json()) == 2
    unrelated = admin_client.patch(
        url, json={"notes": "Correction", "planned_issue_date": "2032-01-01"}
    )
    assert unrelated.json()["status"] == "submitted"
    assert len(admin_client.get(url + "/status-history").json()) == 2
    invalid = admin_client.patch(url, json={"issue_date": "2025-03-01", "fee_amount": "-1"})
    assert invalid.status_code == 422
    assert admin_client.get(url).json()["status"] == "submitted"
    assert len(admin_client.get(url + "/status-history").json()) == 2
    assert (
        admin_client.patch(url, json={"actual_submission_date": None}).json()["status"]
        == "not_started"
    )
