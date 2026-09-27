"""Project images are real uploads with project access and retained removal."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.models import ProjectImage
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic image content"


def test_upload_read_and_remove_project_image(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    url = f"{PROJECTS}/{project_id}/images?category=interior&filename=lobby.png"
    created = admin_client.post(
        url, content=PNG, headers={"Content-Type": "application/octet-stream"}
    )
    assert created.status_code == 201, created.text
    image_id = created.json()["id"]
    assert created.json()["category"] == "interior"
    assert "image_data" not in created.json()

    listed = admin_client.get(f"{PROJECTS}/{project_id}/images")
    assert [row["id"] for row in listed.json()] == [image_id]
    file = admin_client.get(f"{PROJECTS}/{project_id}/images/{image_id}/file")
    assert file.status_code == 200 and file.content == PNG
    assert file.headers["content-type"] == "image/png"

    removed = admin_client.delete(f"{PROJECTS}/{project_id}/images/{image_id}")
    assert removed.status_code == 204
    assert admin_client.get(f"{PROJECTS}/{project_id}/images").json() == []
    assert admin_client.get(f"{PROJECTS}/{project_id}/images/{image_id}/file").status_code == 404
    assert admin_client.delete(f"{PROJECTS}/{project_id}/images/{image_id}").status_code == 404
    db.expire_all()
    assert db.scalar(select(ProjectImage).where(ProjectImage.id == uuid.UUID(image_id))).removed_at
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "project_image.removed"))


def test_image_rejects_invalid_content_and_cross_project_identifier(
    admin_client: TestClient,
    project_id: str,
    db: Session,
    country_pack_id: str,
    currency_id: str,
) -> None:
    invalid = admin_client.post(
        f"{PROJECTS}/{project_id}/images?category=render_3d&filename=bad.svg",
        content=b"<svg></svg>",
    )
    assert invalid.status_code == 422
    created = admin_client.post(
        f"{PROJECTS}/{project_id}/images?category=exterior&filename=facade.png", content=PNG
    )
    assert created.status_code == 201
    from tests.modules.conftest import project_payload

    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    )
    assert other.status_code == 201
    other_id = other.json()["id"]
    image_id = created.json()["id"]
    assert admin_client.get(f"{PROJECTS}/{other_id}/images/{image_id}/file").status_code == 404
    assert admin_client.delete(f"{PROJECTS}/{other_id}/images/{image_id}").status_code == 404


def test_unassigned_manager_cannot_access_project_images(
    manager_client: TestClient, project_id: str
) -> None:
    assert manager_client.get(f"{PROJECTS}/{project_id}/images").status_code == 404
    assert (
        manager_client.post(
            f"{PROJECTS}/{project_id}/images?category=interior&filename=a.png", content=PNG
        ).status_code
        == 404
    )


def test_project_reader_cannot_upload_or_remove_images(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    reader = make_user(db, email="image-reader@example.com", roles=("sales_advisor",))
    grant_access(admin_client, project_id, reader)
    client = client_for(reader.email)
    created = admin_client.post(
        f"{PROJECTS}/{project_id}/images?category=exterior&filename=front.png", content=PNG
    )
    image_id = created.json()["id"]
    assert client.get(f"{PROJECTS}/{project_id}/images").status_code == 200
    assert client.get(f"{PROJECTS}/{project_id}/images/{image_id}/file").content == PNG
    assert (
        client.post(
            f"{PROJECTS}/{project_id}/images?category=interior&filename=room.png", content=PNG
        ).status_code
        == 403
    )
    assert client.delete(f"{PROJECTS}/{project_id}/images/{image_id}").status_code == 403
    assert admin_client.get(f"{PROJECTS}/{project_id}/images/{image_id}/file").status_code == 200


def test_image_migration_roundtrip_and_retained_history(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0038_commission_beneficiaries")
    command.upgrade(config, "head")
    command.check(config)
    created = admin_client.post(
        f"{PROJECTS}/{project_id}/images?category=interior&filename=room.png", content=PNG
    )
    assert created.status_code == 201
    admin_client.delete(f"{PROJECTS}/{project_id}/images/{created.json()['id']}")
    db.rollback()
    with pytest.raises(RuntimeError, match="Project image history"):
        command.downgrade(config, "0038_commission_beneficiaries")
    command.upgrade(config, "head")
    assert db.execute(text("SELECT count(*) FROM project_images")).scalar() == 1
