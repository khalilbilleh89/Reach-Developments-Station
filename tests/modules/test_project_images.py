"""Project galleries enforce byte, access, isolation and retention contracts."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects import images
from app.modules.projects.models import ProjectImage, UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, project_payload

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic image content"
JPEG = b"\xff\xd8\xff" + b"synthetic jpeg" + b"\xff\xd9"
WEBP = b"RIFF" + b"\x10\x00\x00\x00" + b"WEBP" + b"synthetic webp"


def _upload(
    client: TestClient,
    project_id: str,
    *,
    category: str = "interior",
    filename: str = "lobby.png",
    content: bytes = PNG,
) -> Response:
    return client.post(
        f"{PROJECTS}/{project_id}/images",
        params={"category": category, "filename": filename},
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )


@pytest.mark.parametrize(
    ("content", "expected_media_type"),
    [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")],
)
def test_upload_accepts_supported_signatures_and_serves_private_bytes(
    admin_client: TestClient,
    project_id: str,
    content: bytes,
    expected_media_type: str,
) -> None:
    created = _upload(admin_client, project_id, content=content)
    assert created.status_code == 201, created.text
    assert created.json()["media_type"] == expected_media_type
    assert "image_data" not in created.json()

    image_id = created.json()["id"]
    response = admin_client.get(f"{PROJECTS}/{project_id}/images/{image_id}/file")
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == expected_media_type
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_metadata_list_does_not_load_or_return_binary_content(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    created = _upload(admin_client, project_id)
    assert created.status_code == 201
    db.expire_all()
    records = images.list_images(db, uuid.UUID(project_id))
    assert len(records) == 1
    assert "image_data" not in records[0].__dict__

    listed = admin_client.get(f"{PROJECTS}/{project_id}/images")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created.json()["id"]]
    assert all("image_data" not in item for item in listed.json())


@pytest.mark.parametrize(
    ("category", "filename", "content", "message"),
    [
        ("plans", "plan.png", PNG, "Choose Interior"),
        ("interior", "bad.svg", b"<svg></svg>", "JPEG, PNG or WebP"),
        ("interior", "empty.png", b"", "between 1 byte and 10 MB"),
    ],
)
def test_upload_rejects_invalid_category_content_and_empty_files(
    admin_client: TestClient,
    project_id: str,
    category: str,
    filename: str,
    content: bytes,
    message: str,
) -> None:
    response = _upload(
        admin_client, project_id, category=category, filename=filename, content=content
    )
    assert response.status_code == 422
    assert message in response.text
    assert admin_client.get(f"{PROJECTS}/{project_id}/images").json() == []


def test_upload_rejects_oversize_and_sanitizes_filename(
    admin_client: TestClient, project_id: str
) -> None:
    oversize = _upload(
        admin_client,
        project_id,
        filename="large.png",
        content=PNG + b"x" * images.MAX_IMAGE_BYTES,
    )
    assert oversize.status_code == 422

    created = _upload(
        admin_client,
        project_id,
        filename=" C:\\fakepath\\  lobby.png  ",
    )
    assert created.status_code == 201, created.text
    assert created.json()["filename"] == "lobby.png"
    truncated = _upload(admin_client, project_id, filename=f"folder/{'x' * 220}.png")
    assert truncated.status_code == 201, truncated.text
    assert len(truncated.json()["filename"]) == images.MAX_FILENAME_LENGTH
    blank = _upload(admin_client, project_id, filename="folder/   ")
    assert blank.status_code == 422


def test_reader_can_view_but_cannot_mutate_project_images(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    reader = make_user(db, email="image-reader@example.com", roles=("sales_advisor",))
    grant_access(admin_client, project_id, reader)
    reader_client = client_for(reader.email)
    created = _upload(admin_client, project_id, category="exterior", filename="front.png")
    image_id = created.json()["id"]

    assert reader_client.get(f"{PROJECTS}/{project_id}/images").status_code == 200
    assert reader_client.get(f"{PROJECTS}/{project_id}/images/{image_id}/file").content == PNG
    assert _upload(reader_client, project_id).status_code == 403
    assert reader_client.delete(f"{PROJECTS}/{project_id}/images/{image_id}").status_code == 403


def test_selected_phase_project_manager_cannot_change_the_whole_project_gallery(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    manager = make_user(db, email="phase-pm@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, manager)
    manager_client = client_for(manager.email)
    kept = _upload(admin_client, project_id, filename="kept.png").json()["id"]
    assert _upload(manager_client, project_id, filename="whole.png").status_code == 201

    access = db.scalar(
        select(UserProjectAccess).where(
            UserProjectAccess.user_id == manager.id,
            UserProjectAccess.project_id == uuid.UUID(project_id),
        )
    )
    access.phase_scope = "selected"
    db.commit()

    assert manager_client.get(f"{PROJECTS}/{project_id}/images").status_code == 200
    assert _upload(manager_client, project_id, filename="partial.png").status_code == 403
    assert manager_client.delete(f"{PROJECTS}/{project_id}/images/{kept}").status_code == 403
    names = [row["filename"] for row in admin_client.get(f"{PROJECTS}/{project_id}/images").json()]
    assert sorted(names) == ["kept.png", "whole.png"]


def test_nul_character_in_a_filename_is_refused_not_a_server_fault(
    admin_client: TestClient, project_id: str
) -> None:
    response = _upload(admin_client, project_id, filename="lobby\x00.png")
    assert response.status_code == 422
    assert response.json() == {"detail": "Text cannot contain the NUL (0x00) character."}
    assert admin_client.get(f"{PROJECTS}/{project_id}/images").json() == []


def test_inaccessible_and_cross_project_image_ids_return_not_found(
    admin_client: TestClient,
    manager_client: TestClient,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    created = _upload(admin_client, project_id)
    image_id = created.json()["id"]
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]

    assert manager_client.get(f"{PROJECTS}/{project_id}/images").status_code == 404
    assert _upload(manager_client, project_id).status_code == 404
    assert admin_client.get(f"{PROJECTS}/{other_id}/images/{image_id}/file").status_code == 404
    assert admin_client.delete(f"{PROJECTS}/{other_id}/images/{image_id}").status_code == 404


def test_remove_hides_image_and_retains_attribution_without_audit_bytes(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    created = _upload(admin_client, project_id, filename="suite.png")
    image_id = uuid.UUID(created.json()["id"])
    removed = admin_client.delete(f"{PROJECTS}/{project_id}/images/{image_id}")
    assert removed.status_code == 204
    assert admin_client.get(f"{PROJECTS}/{project_id}/images").json() == []
    assert admin_client.get(f"{PROJECTS}/{project_id}/images/{image_id}/file").status_code == 404
    assert admin_client.delete(f"{PROJECTS}/{project_id}/images/{image_id}").status_code == 404

    db.expire_all()
    row = db.scalar(select(ProjectImage).where(ProjectImage.id == image_id))
    assert row is not None and row.removed_at is not None
    assert row.removed_by_user_id == row.created_by_user_id
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "project_image", AuditEvent.entity_id == image_id)
            .order_by(AuditEvent.occurred_at)
        )
    )
    assert [event.action for event in events] == [
        "project_image.created",
        "project_image.removed",
    ]
    serialized = json.dumps(
        [{"before": event.before_data, "after": event.after_data} for event in events]
    )
    assert "image_data" not in serialized
    assert "synthetic image content" not in serialized


def test_image_migration_roundtrip_and_history_guard(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0038_commission_beneficiaries")
    command.upgrade(config, "head")
    command.check(config)

    created = _upload(admin_client, project_id)
    assert created.status_code == 201, created.text
    assert (
        admin_client.delete(f"{PROJECTS}/{project_id}/images/{created.json()['id']}").status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="Project image history"):
        command.downgrade(config, "0038_commission_beneficiaries")
    command.upgrade(config, "head")
    assert db.execute(text("SELECT count(*) FROM project_images")).scalar() == 1
