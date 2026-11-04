"""Marketing upload/link lifecycle, byte access and retained evidence."""

import io
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx2 import Response
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.orm import Session, undefer

from app.modules.audit.models import AuditEvent
from app.modules.marketing import assets
from app.modules.marketing.models import MarketingAsset
from app.modules.projects.models import UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/marketing/assets"


def image_bytes(format: str = "PNG") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(stream, format=format)
    return stream.getvalue()


def upload(client: TestClient, project_id: str, **changes: str) -> Response:
    fields = {
        "placement": "logo",
        "kind": "image",
        "title": "Primary logo",
        "category": "Brand",
        "filename": "logo.png",
        **changes,
    }
    return client.post(root(project_id) + "/upload", params=fields, content=image_bytes())


def test_logo_upload_edit_delete_retains_bytes_and_audit(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    response = upload(admin_client, project_id)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["media_type"] == "image/png"
    assert "data" not in row and "sha256" not in row
    url = f"{root(project_id)}/{row['id']}"
    read = admin_client.get(url + "/file")
    assert read.content == image_bytes()
    assert read.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in read.headers["cache-control"]
    assert admin_client.get(root(project_id), params={"placement": "logo"}).json()["total"] == 1
    assert admin_client.get(root(project_id)).json()["total"] == 0
    update = {
        "expected_version": 1,
        "title": "Light logo",
        "category": "Website",
        "notes": "Use on dark backgrounds",
    }
    assert admin_client.put(url, json=update).json()["version"] == 2
    assert admin_client.put(url, json=update).status_code == 409
    assert (
        admin_client.post(
            url + "/delete", json={"expected_version": 1, "reason": "Old revision"}
        ).status_code
        == 409
    )
    assert (
        admin_client.post(
            url + "/delete", json={"expected_version": 2, "reason": "Replaced"}
        ).status_code
        == 204
    )
    assert admin_client.get(url + "/file").status_code == 404
    assert (
        admin_client.post(
            url + "/delete", json={"expected_version": 2, "reason": "Again"}
        ).status_code
        == 404
    )
    kept = db.scalar(select(MarketingAsset).options(undefer(MarketingAsset.data)))
    assert kept.is_deleted and kept.data == read.content
    audit = db.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_type == "marketing_asset", AuditEvent.action == "delete"
        )
    )
    assert audit.reason == "Replaced" and audit.before_data["sha256"] == kept.sha256
    assert "data" not in audit.before_data


def test_material_links_search_categories_and_isolation(
    admin_client: TestClient, project_id: str
) -> None:
    base = root(project_id)
    for kind, title in [
        ("video", "Walkthrough"),
        ("document", "Market research"),
        ("image", "Exterior"),
    ]:
        response = admin_client.post(
            base + "/links",
            json={
                "kind": kind,
                "title": title,
                "category": "Sales",
                "external_url": "https://drive.google.com/file/d/example/view",
            },
        )
        assert response.status_code == 201, response.text
    result = admin_client.get(
        base, params={"kind": "document", "search": "research", "limit": 1}
    ).json()
    assert result["total"] == 1 and result["categories"] == ["Sales"]
    row = result["items"][0]
    assert admin_client.get(f"{base}/{row['id']}/file").status_code == 404
    assert admin_client.get(f"{root(str(uuid.uuid4()))}/{row['id']}/file").status_code == 404
    assert admin_client.get(base, params={"offset": 2, "limit": 1}).json()["total"] == 3
    assert admin_client.get(base, params={"category": "Absent"}).json()["items"] == []


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://drive.google.com/file",
        "https://user:pass@example.com/x",
        "https://example.com\\evil",
        "https://example.com:bad/x",
    ],
)
def test_unsafe_links_rejected(admin_client: TestClient, project_id: str, url: str) -> None:
    assert (
        admin_client.post(
            root(project_id) + "/links",
            json={
                "kind": "document",
                "title": "Research",
                "category": "Reference",
                "external_url": url,
            },
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "kind,name,data",
    [
        ("image", "fake.png", b"not an image"),
        ("image", "wrong.jpg", image_bytes()),
        ("document", "wrong.pdf", b"<html>not PDF</html>"),
        ("video", "fake.mp4", b"not a video"),
    ],
    ids=["fake-image", "mismatch", "fake-pdf", "fake-video"],
)
def test_invalid_files_rejected(
    admin_client: TestClient, project_id: str, kind: str, name: str, data: bytes
) -> None:
    response = admin_client.post(
        root(project_id) + "/upload",
        params={"kind": kind, "title": "Test", "category": "Sales", "filename": name},
        content=data,
    )
    assert response.status_code == 422, response.text


def test_pdf_video_download_and_range(admin_client: TestClient, project_id: str) -> None:
    def box(kind: bytes, payload: bytes) -> bytes:
        return (8 + len(payload)).to_bytes(4, "big") + kind + payload

    video = box(b"ftyp", b"isom\0\0\0\0") + box(b"moov", b"test") + box(b"mdat", b"sample")
    for kind, name, data in [
        ("video", "tour.mp4", video),
        ("document", "research.pdf", b"%PDF-1.4\nreference\n%%EOF\n"),
    ]:
        response = admin_client.post(
            root(project_id) + "/upload",
            params={"kind": kind, "title": "Test", "category": "Sales", "filename": name},
            content=data,
        )
        assert response.status_code == 201, response.text
        url = f"{root(project_id)}/{response.json()['id']}/file"
        result = admin_client.get(url)
        assert result.content == data
        assert ("attachment" if kind == "document" else "inline") in result.headers[
            "content-disposition"
        ]
        part = admin_client.get(url, headers={"Range": "bytes=2-7"})
        assert part.status_code == 206 and part.content == data[2:8]
        assert admin_client.get(url, headers={"Range": "bytes=-3"}).content == data[-3:]
        assert admin_client.get(url, headers={"Range": "bytes=9999-"}).status_code == 416
        assert admin_client.get(url, headers={"Range": "bytes=0-1,2-3"}).status_code == 416


def test_upload_limit_and_logo_contract(
    admin_client: TestClient, project_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(assets, "MAX_IMAGE_BYTES", 32)
    assert upload(admin_client, project_id).status_code == 413
    assert (
        admin_client.post(
            root(project_id) + "/links",
            json={
                "placement": "logo",
                "kind": "image",
                "title": "Logo",
                "category": "Brand",
                "external_url": "https://example.com/logo.png",
            },
        ).status_code
        == 422
    )


def test_reader_cannot_write_and_selected_phase_cannot_read(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    row = upload(admin_client, project_id).json()
    user = make_user(db, email="assets-reader@test.test", roles=("sales_advisor",))
    client = client_for(user.email)
    grant_access(admin_client, project_id, user)
    assert client.get(root(project_id)).status_code == 200
    assert upload(client, project_id).status_code == 403
    url = f"{root(project_id)}/{row['id']}"
    assert client.get(url + "/file").status_code == 200
    assert (
        client.put(url, json={"title": "No", "category": "No", "expected_version": 1}).status_code
        == 403
    )
    assert (
        client.post(url + "/delete", json={"expected_version": 1, "reason": "No"}).status_code
        == 403
    )
    access = db.scalar(select(UserProjectAccess).where(UserProjectAccess.user_id == user.id))
    access.phase_scope = "selected"
    db.commit()
    assert client.get(root(project_id)).status_code == 404
    assert client.get(url + "/file").status_code == 404


def test_asset_migration_retention(admin_client: TestClient, project_id: str, db: Session) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0058_sales_import_drafts")
    command.upgrade(config, "head")
    command.check(config)
    row = upload(admin_client, project_id).json()
    assert (
        admin_client.post(
            f"{root(project_id)}/{row['id']}/delete",
            json={"expected_version": 1, "reason": "Keep history"},
        ).status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="attachment history"):
        command.downgrade(config, "0058_sales_import_drafts")
    assert db.scalar(text("SELECT count(*) FROM marketing_assets")) == 1
