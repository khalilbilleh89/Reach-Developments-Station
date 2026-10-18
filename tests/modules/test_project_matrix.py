"""Strategy records, numeric boundaries, scope and retained deletion."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.matrix_models import ProjectMatrix
from app.modules.projects.matrix_schemas import CATEGORIES, MatrixFields, MatrixRemoval
from app.modules.projects.models import UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, project_payload


def url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/matrices"


def payload(framework: str = "swot") -> dict:
    return {
        "title": "Synthetic strategy",
        "framework": framework,
        "as_of": "2026-10-18",
        "effect": "Delivery delay" if framework == "fishbone" else "",
        "items": [{"label": "Example", "category": CATEGORIES[framework][0]}]
        if framework != "bcg"
        else [],
    }


def create(client: TestClient, project_id: str, framework: str = "swot") -> dict:
    response = client.post(url(project_id), json=payload(framework))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("framework", list(CATEGORIES))
def test_all_templates_persist_edit_reopen(
    admin_client: TestClient, project_id: str, framework: str
) -> None:
    row = create(admin_client, project_id, framework)
    body = {**payload(framework), "version": row["version"], "title": "Revised", "items": []}
    changed = admin_client.put(f"{url(project_id)}/{row['id']}", json=body)
    assert changed.status_code == 200, changed.text
    assert changed.json()["version"] == 2
    assert admin_client.get(url(project_id)).json()["analyses"][0]["title"] == "Revised"
    assert admin_client.put(f"{url(project_id)}/{row['id']}", json=body).status_code == 409
    assert (
        admin_client.post(
            f"{url(project_id)}/{row['id']}/delete", json={"version": 1, "reason": "Stale"}
        ).status_code
        == 409
    )


def test_bcg_classification_geometry_and_exact_decimals(
    admin_client: TestClient, project_id: str
) -> None:
    body = payload("bcg")
    body["items"] = [
        {"label": "Star", "growth_pct": "10", "relative_share": "1"},
        {"label": "Question", "growth_pct": "12.125", "relative_share": "0.5"},
        {"label": "Cash", "growth_pct": "0", "relative_share": "2"},
        {"label": "Dog", "growth_pct": "-10", "relative_share": "0"},
    ]
    response = admin_client.post(url(project_id), json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    assert [p["category"] for p in data["points"]] == [
        "Stars",
        "Question marks",
        "Cash cows",
        "Dogs",
    ]
    assert data["items"][1]["growth_pct"] == "12.125"
    assert data["points"][0]["x"] == 500 and data["points"][0]["y"] == 300
    assert all(0 <= p["x"] <= 1000 and 0 <= p["y"] <= 600 for p in data["points"])
    preview = admin_client.post(
        url(project_id) + "/preview", json={**body, "growth_threshold_pct": "20"}
    )
    assert preview.status_code == 200
    assert preview.json()[0]["category"] == "Cash cows"
    assert len(admin_client.get(url(project_id)).json()["analyses"]) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"framework": "other"},
        {"items": [{"label": "Bad category", "category": "Legal"}]},
        {"as_of": "wrong"},
        {"items": [{"label": "", "category": "Strengths"}]},
        {"context": "bad\x00text"},
    ],
)
def test_invalid_inputs_write_nothing(
    admin_client: TestClient, project_id: str, changes: dict
) -> None:
    assert admin_client.post(url(project_id), json={**payload(), **changes}).status_code == 422
    assert admin_client.get(url(project_id)).json()["analyses"] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"items": [{"label": "Missing"}]},
        {"items": [{"label": "Negative share", "growth_pct": "0", "relative_share": "-1"}]},
        {"growth_threshold_pct": "0"},
        {"items": [{"label": "Nonfinite", "growth_pct": "NaN", "relative_share": "1"}]},
    ],
)
def test_bcg_rejects_missing_or_invalid_numeric_inputs(
    admin_client: TestClient, project_id: str, changes: dict
) -> None:
    assert admin_client.post(url(project_id), json={**payload("bcg"), **changes}).status_code == 422


def test_delete_keeps_payload_audit_and_refuses_repeated_requests(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    row = create(admin_client, project_id)
    target = f"{url(project_id)}/{row['id']}/delete"
    assert admin_client.post(target, json={"version": 1, "reason": " "}).status_code == 422
    assert admin_client.post(target, json={"version": 1, "reason": "Superseded"}).status_code == 204
    assert admin_client.post(target, json={"version": 1, "reason": "Again"}).status_code == 404
    assert admin_client.get(url(project_id)).json()["analyses"] == []
    saved = db.get(ProjectMatrix, uuid.UUID(row["id"]))
    assert saved.is_deleted and saved.payload["items"][0]["label"] == "Example"
    event = db.scalar(
        select(AuditEvent).where(AuditEvent.entity_id == saved.id, AuditEvent.action == "delete")
    )
    assert event.reason == "Superseded" and event.actor_user_id
    assert event.before_data["payload"]["items"][0]["label"] == "Example"


@pytest.mark.parametrize(
    "role,expected",
    [
        ("project_manager", 201),
        ("master_admin", 201),
        ("executive_viewer", 403),
        ("sales_operations", 403),
    ],
)
def test_access_roles_and_phase_scope(
    admin_client: TestClient, project_id: str, db: Session, role: str, expected: int
) -> None:
    user = make_user(db, email=f"{role}@matrix.test", roles=(role,))
    client = client_for(user.email)
    if role != "master_admin":
        assert client.get(url(project_id)).status_code == 404
    grant_access(admin_client, project_id, user)
    assert client.get(url(project_id)).status_code == 200
    assert client.post(url(project_id), json=payload()).status_code == expected
    row = create(admin_client, project_id)
    if expected == 403:
        assert (
            client.put(
                f"{url(project_id)}/{row['id']}", json={**payload(), "version": 1}
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"{url(project_id)}/{row['id']}/delete", json={"version": 1, "reason": "Denied"}
            ).status_code
            == 403
        )
    access = db.scalar(
        select(UserProjectAccess).where(
            UserProjectAccess.user_id == user.id,
            UserProjectAccess.project_id == uuid.UUID(project_id),
        )
    )
    access.phase_scope = "selected"
    db.commit()
    if role != "master_admin":
        assert client.get(url(project_id)).status_code == 404
        assert client.post(url(project_id), json=payload()).status_code == 404
        assert client.post(url(project_id) + "/preview", json=payload()).status_code == 404


def test_wrong_project_cannot_change_or_remove(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    row = create(admin_client, project_id)
    assert (
        admin_client.put(f"{url(other)}/{row['id']}", json={**payload(), "version": 1}).status_code
        == 404
    )
    assert (
        admin_client.post(
            f"{url(other)}/{row['id']}/delete", json={"version": 1, "reason": "Wrong project"}
        ).status_code
        == 404
    )


def test_migration_roundtrip_and_retention(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0044_team_job_description")
    command.upgrade(config, "head")
    command.check(config)
    row = create(admin_client, project_id)
    admin_client.post(
        f"{url(project_id)}/{row['id']}/delete", json={"version": 1, "reason": "Retain"}
    )
    with pytest.raises(RuntimeError, match="Matrix history"):
        command.downgrade(config, "0044_team_job_description")
    command.upgrade(config, "head")


@pytest.mark.parametrize(
    "field", ["title", "context", "effect", "label", "notes", "category", "reason"]
)
def test_all_text_fields_reject_null_characters(field: str) -> None:
    body = payload()
    invalid = "bad\x00text"
    with pytest.raises(ValidationError):
        if field == "reason":
            MatrixRemoval(version=1, reason=invalid)
        else:
            if field in {"label", "notes", "category"}:
                body["items"][0][field] = invalid
            else:
                body[field] = invalid
            MatrixFields.model_validate(body)
