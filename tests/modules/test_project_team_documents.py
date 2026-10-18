"""Optional job descriptions are scoped, versioned and retained."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.team_models import TeamJobDescription
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, project_payload
from tests.modules.test_project_team import create, url

PDF = b"%PDF-1.4 synthetic job description"


def upload(
    client: TestClient,
    project_id: str,
    row: dict,
    data: bytes = PDF,
    filename: str = "Role.pdf",
    version: int | None = None,
) -> Response:
    return client.post(
        f"{url(project_id)}/{row['id']}/job-description",
        params={"filename": filename, "version": version or row["version"]},
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )


def test_optional_upload_replace_remove_and_audit(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    row = create(admin_client, project_id)
    assert row["job_description"] is None
    base = f"{url(project_id)}/{row['id']}/job-description"
    assert admin_client.get(base).status_code == 404
    response = upload(admin_client, project_id, row, filename="Engineer role.pdf")
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["version"] == 2
    assert saved["job_description"]["filename"] == "Engineer role.pdf"
    assert "document" not in str(saved)
    received = admin_client.get(base)
    assert received.content == PDF
    assert received.headers["x-content-type-options"] == "nosniff"
    assert received.headers["cache-control"] == "private, no-store"
    assert "attachment;" in received.headers["content-disposition"]
    assert upload(admin_client, project_id, row).status_code == 409
    changed = upload(admin_client, project_id, saved, data=PDF + b" revision").json()
    assert changed["version"] == 3
    assert changed["job_description"]["id"] != saved["job_description"]["id"]
    assert (
        admin_client.post(base + "/delete", json={"version": 2, "reason": "Stale"}).status_code
        == 409
    )
    assert (
        admin_client.post(base + "/delete", json={"version": 3, "reason": " "}).status_code == 422
    )
    assert (
        admin_client.post(
            base + "/delete", json={"version": 3, "reason": "No longer current"}
        ).status_code
        == 204
    )
    assert admin_client.get(base).status_code == 404
    assert (
        admin_client.post(base + "/delete", json={"version": 4, "reason": "Again"}).status_code
        == 404
    )
    person = admin_client.get(url(project_id)).json()["members"][0]
    assert person["version"] == 4 and person["job_description"] is None
    files = db.scalars(select(TeamJobDescription)).all()
    assert len(files) == 2 and all(file.is_deleted for file in files)
    assert {file.document for file in files} == {PDF, PDF + b" revision"}
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.entity_type == "team_job_description")
    ).all()
    assert {event.action for event in events} == {"create", "replace", "delete"}
    assert all(event.actor_user_id and "document" not in event.after_data for event in events)
    assert next(event for event in events if event.action == "delete").reason == "No longer current"


@pytest.mark.parametrize(
    "filename,data,status",
    [
        ("bad.exe", PDF, 422),
        ("role.pdf", b"not pdf", 422),
        ("role.pdf", b"", 422),
        ("../role.pdf", PDF, 422),
        ("bad\n.pdf", PDF, 422),
        ("role.docx", b"not zip", 422),
        ("role.pdf", b"x" * (10 * 1024 * 1024 + 1), 413),
    ],
    ids=["extension", "signature", "empty", "path", "control", "broken-docx", "oversized"],
)
def test_invalid_document_does_not_change_member(
    admin_client: TestClient, project_id: str, db: Session, filename: str, data: bytes, status: int
) -> None:
    row = create(admin_client, project_id)
    response = upload(admin_client, project_id, row, data=data, filename=filename)
    assert response.status_code == status, response.text
    assert admin_client.get(url(project_id)).json()["members"][0]["version"] == 1
    assert db.scalar(select(TeamJobDescription)) is None


def test_word_and_unicode_filename(admin_client: TestClient, project_id: str) -> None:
    import io
    import zipfile

    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("word/document.xml", "document")
    row = create(admin_client, project_id)
    response = upload(
        admin_client, project_id, row, data=content.getvalue(), filename="Role description.docx"
    )
    assert response.status_code == 201, response.text


def test_reader_scope_and_removed_member(
    admin_client: TestClient, project_id: str, db: Session, country_pack_id: str, currency_id: str
) -> None:
    row = create(admin_client, project_id)
    row = upload(admin_client, project_id, row).json()
    base = f"{url(project_id)}/{row['id']}/job-description"
    reader = make_user(db, email="reader@job.test", roles=("design_engineering",))
    client = client_for(reader.email)
    assert client.get(base).status_code == 404
    grant_access(admin_client, project_id, reader)
    assert client.get(base).content == PDF
    assert upload(client, project_id, row).status_code == 403
    assert client.post(base + "/delete", json={"version": 2, "reason": "Denied"}).status_code == 403
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    assert admin_client.get(f"{url(other)}/{row['id']}/job-description").status_code == 404
    assert upload(admin_client, other, row).status_code == 404
    assert (
        admin_client.post(
            f"{url(other)}/{row['id']}/job-description/delete",
            json={"version": 2, "reason": "Wrong"},
        ).status_code
        == 404
    )
    assert (
        admin_client.post(
            f"{url(project_id)}/{row['id']}/delete", json={"version": 2, "reason": "Left project"}
        ).status_code
        == 204
    )
    assert admin_client.get(base).status_code == 404
    assert upload(admin_client, project_id, {**row, "version": 3}).status_code == 404
    db.rollback()
    assert db.get(TeamJobDescription, uuid.UUID(row["job_description"]["id"])).document == PDF


def test_document_migration_retains_history(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0043_commercial_faqs")
    command.upgrade(config, "head")
    command.check(config)
    row = create(admin_client, project_id)
    assert upload(admin_client, project_id, row).status_code == 201
    assert (
        admin_client.post(
            f"{url(project_id)}/{row['id']}/job-description/delete",
            json={"version": 2, "reason": "Retain"},
        ).status_code
        == 204
    )
    with pytest.raises(RuntimeError, match="Job description history"):
        command.downgrade(config, "0043_commercial_faqs")
    command.upgrade(config, "head")
