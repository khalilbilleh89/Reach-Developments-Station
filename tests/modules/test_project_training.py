"""Training lifecycle, project authorization, files and migration retention."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session, undefer

from app.modules.audit.models import AuditEvent
from app.modules.projects import training_service
from app.modules.projects.models import UserProjectAccess
from app.modules.projects.training_models import ProjectTraining
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access

FIELDS = {
    "title": "Safety induction",
    "category": "Safety",
    "description": "Site induction\nEmergency procedures",
    "execution_date": "2026-11-05",
    "kind": "document",
}
PDF = b"%PDF-1.4\ntraining\n%%EOF\n"


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/training"


def upload(client: TestClient, project_id: str, **changes: str) -> Response:
    return client.post(
        root(project_id) + "/upload",
        params={**FIELDS, "filename": "training.pdf", **changes},
        content=PDF,
    )


def test_training_lifecycle(admin_client: TestClient, project_id: str, db: Session) -> None:
    response = upload(admin_client, project_id)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["execution_date"] == "2026-11-05"
    url = f"{root(project_id)}/{row['id']}"
    assert admin_client.get(url + "/file").content == PDF
    fields = {k: v for k, v in FIELDS.items() if k != "kind"}
    fields.update(title="Updated induction", expected_version=1)
    assert admin_client.put(url, json=fields).json()["version"] == 2
    assert admin_client.put(url, json=fields).status_code == 409
    assert (
        admin_client.post(
            url + "/delete", json={"expected_version": 1, "reason": "Old"}
        ).status_code
        == 409
    )
    assert (
        admin_client.post(
            url + "/delete", json={"expected_version": 2, "reason": "Superseded"}
        ).status_code
        == 204
    )
    assert admin_client.get(root(project_id)).json()["total"] == 0
    assert admin_client.get(url + "/file").status_code == 404
    assert (
        admin_client.post(
            url + "/delete", json={"expected_version": 2, "reason": "Again"}
        ).status_code
        == 404
    )
    row = db.scalar(select(ProjectTraining).options(undefer(ProjectTraining.data)))
    assert row.is_deleted and row.data == PDF
    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_type == "project_training", AuditEvent.action == "delete"
        )
    )
    assert event.reason == "Superseded" and event.before_data["execution_date"] == "2026-11-05"
    assert event.before_data["sha256"] == row.sha256 and "data" not in event.before_data


def test_training_links_search_order_and_scope(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    base = root(project_id)
    for title, date in [("Old", "2025-01-01"), ("New", "2026-12-01")]:
        response = admin_client.post(
            base + "/links",
            json={
                **FIELDS,
                "title": title,
                "execution_date": date,
                "external_url": "https://drive.google.com/file/d/example/view",
            },
        )
        assert response.status_code == 201, response.text
    result = admin_client.get(base).json()
    assert [r["title"] for r in result["items"]] == ["New", "Old"]
    assert result["categories"] == ["Safety"]
    assert (
        admin_client.get(
            base, params={"search": "Emergency", "category": "Safety", "limit": 1, "offset": 1}
        ).json()["total"]
        == 2
    )
    assert admin_client.get(base, params={"search": "%"}).json()["total"] == 0
    row = result["items"][0]
    wrong = f"{root(str(uuid.uuid4()))}/{row['id']}"
    assert admin_client.get(wrong + "/file").status_code == 404
    assert (
        admin_client.post(
            wrong + "/delete", json={"expected_version": 1, "reason": "No"}
        ).status_code
        == 404
    )
    user = make_user(db, email="training-reader@test.test", roles=("sales_advisor",))
    client = client_for(user.email)
    grant_access(admin_client, project_id, user)
    assert client.get(base).status_code == 200
    assert upload(client, project_id).status_code == 403
    fields = {k: v for k, v in FIELDS.items() if k != "kind"}
    assert (
        client.put(f"{base}/{row['id']}", json={**fields, "expected_version": 1}).status_code == 403
    )
    assert (
        client.post(
            f"{base}/{row['id']}/delete", json={"expected_version": 1, "reason": "No"}
        ).status_code
        == 403
    )
    access = db.scalar(select(UserProjectAccess).where(UserProjectAccess.user_id == user.id))
    access.phase_scope = "selected"
    db.commit()
    assert client.get(base).status_code == 404
    assert upload(client, project_id).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"category": " "},
        {"description": " "},
        {"execution_date": "2026-02-30"},
        {"external_url": "javascript:alert(1)"},
        {"external_url": "https://user:pass@example.com/x"},
        {"external_url": "http://example.com/x"},
        {"external_url": "https://example.com:bad/x"},
        {"kind": "image"},
        {"execution_date": None},
    ],
)
def test_invalid_training(
    admin_client: TestClient, project_id: str, changes: dict[str, str | None]
) -> None:
    result = admin_client.post(
        root(project_id) + "/links",
        json={**FIELDS, "external_url": "https://example.com/training", **changes},
    )
    assert result.status_code == 422, result.text


def test_training_file_validation_limits_and_video_ranges(
    admin_client: TestClient, project_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = root(project_id)
    assert (
        admin_client.post(
            base + "/upload", params={**FIELDS, "filename": "fake.pdf"}, content=b"not pdf"
        ).status_code
        == 422
    )
    assert admin_client.post(base + "/links", json=FIELDS).status_code == 422
    monkeypatch.setattr(training_service, "MAX_PDF_BYTES", 10)
    assert upload(admin_client, project_id).status_code == 413

    def box(kind: bytes, payload: bytes) -> bytes:
        return (8 + len(payload)).to_bytes(4, "big") + kind + payload

    video = box(b"ftyp", b"isom\x00\x00\x00\x00") + box(b"moov", b"test") + box(b"mdat", b"sample")
    result = admin_client.post(
        base + "/upload",
        params={**FIELDS, "kind": "video", "filename": "lesson.mp4"},
        content=video,
    )
    assert result.status_code == 201, result.text
    url = f"{base}/{result.json()['id']}/file"
    assert admin_client.get(url).content == video
    part = admin_client.get(url, headers={"Range": "bytes=2-7"})
    assert part.status_code == 206 and part.content == video[2:8]
    assert admin_client.get(url, headers={"Range": "bytes=-3"}).content == video[-3:]
    assert admin_client.get(url, headers={"Range": "bytes=9999-"}).status_code == 416
    assert "no-store" in part.headers["cache-control"]


def test_training_migration_retention(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0060_plan_categories")
    command.upgrade(config, "head")
    command.check(config)
    result = upload(admin_client, project_id)
    assert result.status_code == 201, result.text
    row = result.json()
    assert (
        admin_client.post(
            f"{root(project_id)}/{row['id']}/delete",
            json={"expected_version": 1, "reason": "Retain"},
        ).status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="history must be retained"):
        command.downgrade(config, "0060_plan_categories")
    assert db.scalar(text("SELECT count(*) FROM project_training")) == 1
