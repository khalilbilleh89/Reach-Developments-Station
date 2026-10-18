"""Links and PDFs share the project evidence register and its security boundary."""

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
from app.modules.projects.models import DocumentReference, ProjectDocumentType
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, project_payload

PDF = b"%PDF-1.4 synthetic evidence\n%%EOF"


def upload(client: TestClient, base: str, code: str = "TITLE_DEED", **params: str) -> Response:
    return client.post(
        base + "/documents/upload",
        params={"title": "Site deed", "document_type_code": code, "filename": "deed.pdf", **params},
        content=PDF,
        headers={"Content-Type": "application/octet-stream"},
    )


def test_empty_types_add_select_upload_download_delete(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    base = f"{PROJECTS}/{project_id}"
    for configured in admin_client.get(base + "/document-types").json():
        assert (
            admin_client.patch(
                f"/api/v1/settings/reference-values/{configured['id']}",
                json={"is_active": False},
            ).status_code
            == 200
        )
    assert not any(row["is_active"] for row in admin_client.get(base + "/document-types").json())
    response = admin_client.post(base + "/document-types", json={"label": "  Survey  "})
    assert response.status_code == 201, response.text
    kind = response.json()
    assert kind["label"] == "Survey"
    assert kind in admin_client.get(base + "/document-types").json()
    assert admin_client.post(base + "/document-types", json={"label": "survey"}).status_code == 409
    response = upload(admin_client, base, kind["code"])
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["external_url"] is None and row["filename"] == "deed.pdf" and row["sha256"]
    assert "document" not in row
    url = base + f"/documents/{row['id']}"
    received = admin_client.get(url + "/file")
    assert received.content == PDF
    assert received.headers["cache-control"] == "private, no-store"
    assert received.headers["x-content-type-options"] == "nosniff"
    assert admin_client.patch(url, json={"external_url": "https://example.com"}).status_code == 422
    assert (
        admin_client.post(
            base + f"/document-types/{kind['id']}/delete", json={"reason": "Used"}
        ).status_code
        == 409
    )
    assert admin_client.post(url + "/delete", json={"reason": " "}).status_code == 422
    assert (
        admin_client.post(url + "/delete", json={"reason": "Superseded evidence"}).status_code
        == 204
    )
    assert admin_client.get(url + "/file").status_code == 404
    assert admin_client.get(base + "/documents").json() == []
    assert admin_client.post(url + "/delete", json={"reason": "Again"}).status_code == 404
    assert (
        admin_client.post(
            base + f"/document-types/{kind['id']}/delete", json={"reason": "Retained"}
        ).status_code
        == 409
    )
    db.rollback()
    retained = db.get(DocumentReference, uuid.UUID(row["id"]))
    assert retained.is_deleted and retained.document == PDF
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "document_reference.deleted"))
    assert event.reason == "Superseded evidence" and event.actor_user_id
    assert "document" not in event.after_data


def test_type_unused_deletion_is_scoped_and_audited(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    base = f"{PROJECTS}/{project_id}"
    kind = admin_client.post(base + "/document-types", json={"label": "Unused"}).json()
    url = base + f"/document-types/{kind['id']}/delete"
    assert admin_client.post(url, json={"reason": "Unused choice"}).status_code == 204
    assert admin_client.post(url, json={"reason": "Again"}).status_code == 404
    db.rollback()
    assert db.get(ProjectDocumentType, uuid.UUID(kind["id"])) is None
    assert (
        db.scalar(select(AuditEvent).where(AuditEvent.action == "document_type.deleted")).reason
        == "Unused choice"
    )


@pytest.mark.parametrize(
    "content,filename",
    [
        (b"", "a.pdf"),
        (b"fake", "a.pdf"),
        (PDF, "a.doc"),
        (PDF, "../a.pdf"),
        (PDF * 400000, "a.pdf"),
    ],
    ids=["empty", "signature", "extension", "path", "oversized"],
)
def test_invalid_upload_is_atomic(
    admin_client: TestClient, project_id: str, content: bytes, filename: str
) -> None:
    base = f"{PROJECTS}/{project_id}"
    response = admin_client.post(
        base + "/documents/upload",
        params={"title": "Invalid", "document_type_code": "TITLE_DEED", "filename": filename},
        content=content,
    )
    assert response.status_code in {413, 422}, response.text
    assert admin_client.get(base + "/documents").json() == []


def test_roles_and_cross_project_scope(
    admin_client: TestClient, project_id: str, db: Session, country_pack_id: str, currency_id: str
) -> None:
    base = f"{PROJECTS}/{project_id}"
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    other_base = f"{PROJECTS}/{other}"
    row = upload(admin_client, base).json()
    kind = admin_client.post(base + "/document-types", json={"label": "Local"}).json()
    advisor = make_user(db, email="docs-advisor@example.com", roles=("sales_advisor",))
    grant_access(admin_client, project_id, advisor)
    client = client_for(advisor.email)
    assert client.get(base + "/document-types").status_code == 200
    assert client.get(base + f"/documents/{row['id']}/file").content == PDF
    assert upload(client, base).status_code == 403
    assert client.post(base + "/document-types", json={"label": "Denied"}).status_code == 403
    assert (
        client.post(base + f"/documents/{row['id']}/delete", json={"reason": "Denied"}).status_code
        == 403
    )
    assert (
        client.post(
            base + f"/document-types/{kind['id']}/delete", json={"reason": "Denied"}
        ).status_code
        == 403
    )
    assert client.get(other_base + "/document-types").status_code == 404
    assert admin_client.get(other_base + f"/documents/{row['id']}/file").status_code == 404
    assert (
        admin_client.post(
            other_base + f"/documents/{row['id']}/delete", json={"reason": "Wrong project"}
        ).status_code
        == 404
    )
    assert (
        admin_client.post(
            other_base + f"/document-types/{kind['id']}/delete", json={"reason": "Wrong project"}
        ).status_code
        == 404
    )
    assert upload(admin_client, other_base, kind["code"]).status_code == 422
    engineer = make_user(db, email="docs-engineer@example.com", roles=("design_engineering",))
    grant_access(admin_client, project_id, engineer)
    client = client_for(engineer.email)
    assert (
        client.post(
            "/api/v1/settings/reference-values",
            json={"category": "document_type", "code": "NO_GLOBAL", "label": "Not allowed"},
        ).status_code
        == 403
    )
    assert client.get(base + "/document-types").status_code == 200
    assert client.post(base + "/document-types", json={"label": "Engineer type"}).status_code == 201


def test_document_migration_retains_history(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0045_inventory_masterplans")
    command.upgrade(config, "head")
    command.check(config)
    assert upload(admin_client, f"{PROJECTS}/{project_id}").status_code == 201
    with pytest.raises(RuntimeError, match="Retained document history"):
        command.downgrade(config, "0045_inventory_masterplans")
    command.upgrade(config, "head")
