"""Named PDFs are project evidence, independent of consultant agreement state."""

import io
import uuid

import pypdfium2 as pdfium
import pytest
from alembic import command
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.consultant_engineering.models import ProjectDrawing
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access
from tests.test_migrations import _alembic_config


def pdf() -> bytes:
    output = io.BytesIO()
    with pdfium.PdfDocument.new() as document:
        document.new_page(600, 400).close()
        document.new_page(400, 600).close()
        document.save(output)
    return output.getvalue()


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/drawings"


def upload(client: TestClient, project_id: str, **fields: str) -> Response:
    return client.post(
        root(project_id),
        params={"name": "Ground floor", "filename": "plan.pdf", **fields},
        content=pdf(),
    )


def test_upload_review_edit_delete_retains_original(
    manager_member_client: TestClient, project_id: str, db: Session
) -> None:
    client = manager_member_client
    response = upload(
        client, project_id, name="  Ground floor مخطط  ", revision="R01", location="Building A"
    )
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["name"] == "Ground floor مخطط" and row["category"] == "general"
    assert "document" not in row and "sha256" not in row
    url = root(project_id) + "/" + row["id"]
    original = client.get(url + "/document")
    assert original.content.startswith(b"%PDF-")
    assert original.headers["cache-control"] == "private, no-store"
    assert original.headers["x-content-type-options"] == "nosniff"
    for page in [1, 2]:
        preview = client.get(url + f"/preview?page={page}")
        assert preview.status_code == 200, preview.text
        assert preview.json()["page_count"] == 2
        assert preview.json()["image"].startswith("data:image/png;base64,iVBOR")
    assert client.get(url + "/preview?page=0").status_code == 422
    assert client.get(url + "/preview?page=3").status_code == 422
    fields = {
        key: row[key]
        for key in ("name", "category", "location", "revision", "drawing_number", "status", "notes")
    }
    changed = client.put(
        url, json={**fields, "name": "Ground floor revised label", "expected_version": 1}
    )
    assert changed.status_code == 200 and changed.json()["version"] == 2
    assert client.put(url, json={**fields, "expected_version": 1}).status_code == 409
    assert client.get(url + "/document").content == original.content
    assert (
        client.post(
            url + "/delete", json={"reason": "Old version", "expected_version": 1}
        ).status_code
        == 409
    )
    assert (
        client.post(url + "/delete", json={"reason": " ", "expected_version": 2}).status_code == 422
    )
    assert (
        client.post(
            url + "/delete", json={"reason": "Duplicate upload", "expected_version": 2}
        ).status_code
        == 204
    )
    assert (
        client.post(url + "/delete", json={"reason": "Again", "expected_version": 2}).status_code
        == 404
    )
    assert client.get(root(project_id)).json() == []
    assert client.get(url + "/document").status_code == 404
    assert client.get(url + "/preview").status_code == 404
    db.rollback()
    retained = db.get(ProjectDrawing, uuid.UUID(row["id"]))
    assert retained.is_deleted and retained.document == original.content
    events = list(db.scalars(select(AuditEvent).where(AuditEvent.entity_id == retained.id)))
    assert {event.action for event in events} == {"create", "update", "delete"}
    assert all("document" not in event.after_data for event in events)
    assert next(event for event in events if event.action == "delete").reason == "Duplicate upload"


@pytest.mark.parametrize(
    "role,read,write",
    [
        ("design_engineering", 200, 201),
        ("finance", 200, 403),
        ("executive_viewer", 200, 403),
        ("sales_advisor", 403, 403),
        ("system_admin", 200, 403),
    ],
)
def test_roles_and_mutation_protection(
    manager_member_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    db: Session,
    role: str,
    read: int,
    write: int,
) -> None:
    row = upload(manager_member_client, project_id).json()
    user = make_user(db, email=f"drawing-{role}@example.com", roles=(role,))
    grant_access(admin_client, project_id, user)
    client = client_for(user.email)
    assert client.get(root(project_id)).status_code == read
    assert client.get(root(project_id) + f"/{row['id']}/document").status_code == read
    assert upload(client, project_id).status_code == write
    if write == 403:
        assert (
            client.put(
                root(project_id) + f"/{row['id']}",
                json={"name": "Cannot edit", "expected_version": 1},
            ).status_code
            == 403
        )
        assert (
            client.post(
                root(project_id) + f"/{row['id']}/delete",
                json={"reason": "Cannot delete", "expected_version": 1},
            ).status_code
            == 403
        )


def test_wrong_project_and_selected_phase_are_hidden(
    manager_member_client: TestClient, admin_client: TestClient, project_id: str, db: Session
) -> None:
    from app.modules.projects.models import UserProjectAccess

    row = upload(manager_member_client, project_id).json()
    wrong = root(str(uuid.uuid4())) + f"/{row['id']}"
    assert admin_client.get(wrong + "/document").status_code == 404
    user = make_user(db, email="drawing-phase@example.com", roles=("design_engineering",))
    grant_access(admin_client, project_id, user)
    membership = db.scalar(select(UserProjectAccess).where(UserProjectAccess.user_id == user.id))
    membership.phase_scope = "selected"
    db.commit()
    client = client_for(user.email)
    assert client.get(root(project_id)).status_code == 404
    assert upload(client, project_id).status_code == 404
    assert client.get(root(project_id) + f"/{row['id']}/preview").status_code == 404


@pytest.mark.parametrize(
    "filename,data,status",
    [
        ("a.pdf", b"", 422),
        ("a.pdf", b"not PDF", 422),
        ("a.txt", b"%PDF-test", 422),
        ("../a.pdf", b"%PDF-test", 422),
        ("a.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024), 413),
    ],
    ids=["empty", "signature", "extension", "path", "oversized"],
)
def test_bad_uploads(
    manager_member_client: TestClient, project_id: str, filename: str, data: bytes, status: int
) -> None:
    response = manager_member_client.post(
        root(project_id), params={"name": "Plan", "filename": filename}, content=data
    )
    assert response.status_code == status
    assert manager_member_client.get(root(project_id)).json() == []


@pytest.mark.parametrize(
    "fields",
    [{"name": " "}, {"name": "a\x00b"}, {"category": "unknown"}, {"status": "approved"}],
    ids=["blank", "nul", "category", "approval"],
)
def test_invalid_metadata(manager_member_client: TestClient, project_id: str, fields: dict) -> None:
    assert upload(manager_member_client, project_id, **fields).status_code == 422


def test_migration_roundtrip_and_retention(
    manager_member_client: TestClient, project_id: str, db: Session
) -> None:
    db.rollback()
    config = _alembic_config()
    command.downgrade(config, "0055_commercial_emails")
    command.upgrade(config, "head")
    command.check(config)
    row = upload(manager_member_client, project_id).json()
    assert (
        manager_member_client.post(
            root(project_id) + f"/{row['id']}/delete",
            json={"reason": "Retained evidence", "expected_version": 1},
        ).status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="Project drawings exist"):
        command.downgrade(config, "0055_commercial_emails")
    db.rollback()
    assert db.get(ProjectDrawing, uuid.UUID(row["id"])).is_deleted
