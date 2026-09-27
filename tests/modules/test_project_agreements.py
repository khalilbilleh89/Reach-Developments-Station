"""Final drafts round-trip as files without changing sales or legal state."""

import io
import uuid
import zipfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.agreement_models import ProjectAgreement
from app.modules.projects.models import UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, project_payload

PDF = b"%PDF-1.4\nSynthetic agreement fixture\n%%EOF"
FIELDS = {
    "name": "Sale agreement",
    "signing_company": "Example Ltd",
    "draft_created_on": "2026-09-27",
}


def url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/agreements"


def upload(
    client: TestClient,
    project_id: str,
    filename: str = "agreement.pdf",
    document: bytes = PDF,
    **fields: str,
) -> Response:
    return client.post(
        url(project_id),
        params={**FIELDS, "filename": filename, **fields},
        content=document,
        headers={"Content-Type": "application/octet-stream"},
    )


def test_upload_download_edit_delete_and_retained_audit(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    result = upload(admin_client, project_id, filename="اتفاقية.pdf")
    assert result.status_code == 201, result.text
    row = result.json()
    base = f"{url(project_id)}/{row['id']}"
    assert admin_client.get(url(project_id)).json() == [row]
    assert "document" not in row and "sha256" not in row
    downloaded = admin_client.get(f"{base}/document")
    assert downloaded.content == PDF
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert downloaded.headers["cache-control"] == "private, no-store"
    updated = admin_client.put(base, json={**FIELDS, "name": "Final SPA", "expected_version": 1})
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert admin_client.put(base, json={**FIELDS, "expected_version": 1}).status_code == 409
    assert (
        admin_client.post(
            f"{base}/delete", json={"reason": "superseded", "expected_version": 1}
        ).status_code
        == 409
    )
    assert (
        admin_client.post(f"{base}/delete", json={"reason": " ", "expected_version": 2}).status_code
        == 422
    )
    assert (
        admin_client.post(
            f"{base}/delete", json={"reason": "superseded", "expected_version": 2}
        ).status_code
        == 204
    )
    assert admin_client.get(url(project_id)).json() == []
    assert admin_client.get(f"{base}/document").status_code == 404
    assert admin_client.put(base, json={**FIELDS, "expected_version": 3}).status_code == 404
    assert (
        admin_client.post(
            f"{base}/delete", json={"reason": "again", "expected_version": 3}
        ).status_code
        == 404
    )
    retained = db.get(ProjectAgreement, uuid.UUID(row["id"]))
    assert retained.document == PDF and retained.is_deleted
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "project_agreement")
        .order_by(AuditEvent.occurred_at)
    ).all()
    assert [event.action for event in events] == ["create", "update", "delete"]
    assert events[-1].reason == "superseded"
    assert db.execute(text("SELECT count(*) FROM sale_contracts")).scalar() == 0


@pytest.mark.parametrize(
    "role,read,write",
    [
        ("master_admin", 200, 201),
        ("project_manager", 200, 201),
        ("sales_operations", 200, 201),
        ("legal", 200, 201),
        ("sales_advisor", 200, 403),
        ("finance", 200, 403),
        ("auditor", 200, 403),
        ("design_engineering", 403, 403),
    ],
)
def test_role_and_project_scope(
    admin_client: TestClient, project_id: str, db: Session, role: str, read: int, write: int
) -> None:
    row = upload(admin_client, project_id).json()
    base = f"{url(project_id)}/{row['id']}"
    user = make_user(db, email=f"{role}@agreements.test", roles=(role,))
    client = client_for(user.email)
    if role != "master_admin":
        assert client.get(url(project_id)).status_code == 404
        assert client.get(f"{base}/document").status_code == 404
    grant_access(admin_client, project_id, user)
    assert client.get(url(project_id)).status_code == read
    assert client.get(f"{base}/document").status_code == read
    assert upload(client, project_id).status_code == write
    if write == 403:
        assert client.put(base, json={**FIELDS, "expected_version": 1}).status_code == 403
        assert (
            client.post(f"{base}/delete", json={"reason": "no", "expected_version": 1}).status_code
            == 403
        )
    if role != "master_admin":
        membership = db.scalars(
            select(UserProjectAccess).where(
                UserProjectAccess.user_id == user.id,
                UserProjectAccess.project_id == uuid.UUID(project_id),
            )
        ).one()
        membership.phase_scope = "selected"
        db.commit()
        assert client.get(url(project_id)).status_code == 404
        assert client.get(f"{base}/document").status_code == 404
        assert upload(client, project_id).status_code == 404
        assert client.put(base, json={**FIELDS, "expected_version": 1}).status_code == 404
        assert (
            client.post(f"{base}/delete", json={"reason": "no", "expected_version": 1}).status_code
            == 404
        )


def test_wrong_project_id_cannot_download_or_change(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    second = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    row = upload(admin_client, project_id).json()
    wrong = f"{url(second)}/{row['id']}"
    assert admin_client.get(f"{wrong}/document").status_code == 404
    assert admin_client.put(wrong, json={**FIELDS, "expected_version": 1}).status_code == 404
    assert (
        admin_client.post(
            f"{wrong}/delete", json={"reason": "no", "expected_version": 1}
        ).status_code
        == 404
    )
    assert admin_client.get(url(second)).json() == []


@pytest.mark.parametrize(
    "filename,document",
    [
        ("a.pdf", b""),
        ("a.exe", PDF),
        ("../a.pdf", PDF),
        ("a\r\n.pdf", PDF),
        ("a.pdf", b"not pdf"),
        ("a.docx", PDF),
    ],
)
def test_invalid_upload_is_atomic(
    admin_client: TestClient, project_id: str, filename: str, document: bytes
) -> None:
    assert upload(admin_client, project_id, filename, document).status_code == 422
    assert admin_client.get(url(project_id)).json() == []


def test_size_fields_word_and_multiple_agreements(
    admin_client: TestClient, project_id: str
) -> None:
    assert (
        upload(admin_client, project_id, document=PDF + b"x" * (10 * 1024 * 1024)).status_code
        == 413
    )
    assert upload(admin_client, project_id, name=" ").status_code == 422
    assert upload(admin_client, project_id, draft_created_on="not a date").status_code == 422
    assert upload(admin_client, project_id).status_code == 201
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    assert (
        upload(
            admin_client, project_id, "terms.docx", buffer.getvalue(), name="Additional terms"
        ).status_code
        == 201
    )
    assert (
        upload(
            admin_client,
            project_id,
            "legacy.doc",
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1fixture",
            name="Legacy draft",
        ).status_code
        == 201
    )
    assert [r["name"] for r in admin_client.get(url(project_id)).json()] == [
        "Sale agreement",
        "Additional terms",
        "Legacy draft",
    ]


def test_migration_roundtrip_and_retained_document_refusal(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0040_project_team")
    command.upgrade(config, "head")
    command.check(config)
    row = upload(admin_client, project_id).json()
    admin_client.post(
        f"{url(project_id)}/{row['id']}/delete", json={"reason": "retained", "expected_version": 1}
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="Agreement documents exist"):
        command.downgrade(config, "0040_project_team")
    command.upgrade(config, "head")
    assert db.get(ProjectAgreement, uuid.UUID(row["id"])).document == PDF
