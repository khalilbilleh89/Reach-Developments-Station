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
        ("a.pdf", b"%PDF-" + b"x" * (50 * 1024 * 1024), 413),
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


@pytest.mark.parametrize(
    "category", ["architecture", "electrical", "mechanical", "structure", "shop_drawing"]
)
def test_plan_disciplines_require_only_title_and_pdf(
    manager_member_client: TestClient, project_id: str, category: str
) -> None:
    response = upload(manager_member_client, project_id, category=category)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["category"] == category and row["revision"] == "" and row["location"] == ""
    assert manager_member_client.get(root(project_id)).json()[0]["id"] == row["id"]


def test_malformed_pdf_does_not_create_plan(
    manager_member_client: TestClient, project_id: str
) -> None:
    response = manager_member_client.post(
        root(project_id),
        params={"name": "Broken", "filename": "broken.pdf"},
        content=b"%PDF-1.7\ninvalid payload\n%%EOF",
    )
    assert response.status_code == 422
    assert manager_member_client.get(root(project_id)).json() == []


def test_plan_categories_migration_retains_history(
    manager_member_client: TestClient, project_id: str, db: Session
) -> None:
    db.rollback()
    config = _alembic_config()
    command.downgrade(config, "0059_marketing_assets")
    command.upgrade(config, "head")
    command.check(config)
    row = upload(manager_member_client, project_id, category="electrical").json()
    assert (
        manager_member_client.post(
            root(project_id) + f"/{row['id']}/delete",
            json={"reason": "Retain source plan", "expected_version": 1},
        ).status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="New plan categories exist"):
        command.downgrade(config, "0059_marketing_assets")
    db.rollback()
    assert db.get(ProjectDrawing, uuid.UUID(row["id"])).is_deleted


def test_upload_does_not_require_a_raster_preview(
    manager_member_client: TestClient, project_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.consultant_engineering import drawing_service

    def unavailable_preview(*args: object) -> None:
        raise AssertionError("Upload must not allocate a preview raster")

    monkeypatch.setattr(drawing_service, "preview", unavailable_preview)
    response = upload(manager_member_client, project_id)
    assert response.status_code == 201, response.text
    row = response.json()
    original = manager_member_client.get(root(project_id) + f"/{row['id']}/document")
    assert original.status_code == 200
    assert original.content.startswith(b"%PDF-")


def test_inspection_does_not_render_and_preview_keeps_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PIL import Image

    from app.modules.consultant_engineering.drawing_render import inspect, render

    data = pdf()
    with monkeypatch.context() as patch:

        def no_raster(*args: object, **kwargs: object) -> None:
            raise AssertionError("Inspection must not render")

        patch.setattr(pdfium.PdfPage, "render", no_raster)
        assert inspect(data) == 2
    count, image = render(data, 0)
    assert count == 2
    with Image.open(io.BytesIO(image)) as preview:
        assert preview.format == "PNG" and max(preview.size) == 4096


def test_empty_pdf_does_not_create_plan(manager_member_client: TestClient, project_id: str) -> None:
    output = io.BytesIO()
    with pdfium.PdfDocument.new() as document:
        document.save(output)
    response = manager_member_client.post(
        root(project_id),
        params={"name": "Empty", "filename": "empty.pdf"},
        content=output.getvalue(),
    )
    assert response.status_code == 422
    assert manager_member_client.get(root(project_id)).json() == []


DRIVE_URL = "https://drive.google.com/file/d/test-plan-id/view?resourcekey=example"


def test_drive_plan_lifecycle(
    manager_member_client: TestClient, project_id: str, db: Session
) -> None:
    client = manager_member_client
    response = client.post(
        root(project_id) + "/links", json={"name": "Linked plan", "source_url": DRIVE_URL}
    )
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["source_url"] == DRIVE_URL and row["filename"] is None
    url = root(project_id) + "/" + row["id"]
    assert client.get(root(project_id)).json()[0]["source_url"] == DRIVE_URL
    assert client.get(url + "/document").status_code == 422
    assert client.get(url + "/preview").status_code == 422
    changed = client.put(url, json={"name": "Updated link label", "expected_version": 1})
    assert changed.status_code == 200 and changed.json()["source_url"] == DRIVE_URL
    assert client.put(url, json={"name": "Stale", "expected_version": 1}).status_code == 409
    assert (
        client.post(
            url + "/delete", json={"reason": "Superseded", "expected_version": 2}
        ).status_code
        == 204
    )
    assert client.get(root(project_id)).json() == []
    assert client.get(url + "/preview").status_code == 404
    assert (
        client.post(url + "/delete", json={"reason": "Again", "expected_version": 2}).status_code
        == 404
    )
    db.rollback()
    retained = db.get(ProjectDrawing, uuid.UUID(row["id"]))
    assert retained.is_deleted and retained.source_url == DRIVE_URL and retained.document is None
    events = list(db.scalars(select(AuditEvent).where(AuditEvent.entity_id == retained.id)))
    assert {event.action for event in events} == {"create", "update", "delete"}
    assert all(event.after_data["source_url"] == DRIVE_URL for event in events)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://drive.google.com/file/d/x/view",
        "https://drive.google.com.evil.test/file",
        "https://drive.google.com@evil.test/file",
        "https://evil.test/file.pdf",
        "https://drive.google.com/",
        "https://drive.google.com/file\n/path",
    ],
)
def test_bad_drive_links(manager_member_client: TestClient, project_id: str, url: str) -> None:
    response = manager_member_client.post(
        root(project_id) + "/links", json={"name": "Plan", "source_url": url}
    )
    assert response.status_code == 422
    assert manager_member_client.get(root(project_id)).json() == []


def test_drive_links_keep_role_and_project_scope(
    manager_member_client: TestClient, admin_client: TestClient, project_id: str, db: Session
) -> None:
    from app.modules.projects.models import UserProjectAccess

    row = manager_member_client.post(
        root(project_id) + "/links", json={"name": "Plan", "source_url": DRIVE_URL}
    ).json()
    user = make_user(db, email="link-finance@example.com", roles=("finance",))
    grant_access(admin_client, project_id, user)
    reader = client_for(user.email)
    assert reader.get(root(project_id)).json()[0]["id"] == row["id"]
    assert (
        reader.post(
            root(project_id) + "/links", json={"name": "Plan", "source_url": DRIVE_URL}
        ).status_code
        == 403
    )
    assert (
        reader.post(
            root(project_id) + f"/{row['id']}/delete", json={"reason": "No", "expected_version": 1}
        ).status_code
        == 403
    )
    assert (
        manager_member_client.post(
            root(str(uuid.uuid4())) + f"/{row['id']}/delete",
            json={"reason": "Wrong project", "expected_version": 1},
        ).status_code
        == 404
    )
    membership = db.scalar(select(UserProjectAccess).where(UserProjectAccess.user_id == user.id))
    membership.phase_scope = "selected"
    db.commit()
    assert reader.get(root(project_id)).status_code == 404
    assert (
        reader.post(
            root(project_id) + "/links", json={"name": "Plan", "source_url": DRIVE_URL}
        ).status_code
        == 404
    )


def large_pdf(size: int) -> bytes:
    # An unreferenced stream makes a valid large PDF without expensive page pixels.
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 400] >>",
    ]

    def build(padding: int) -> bytes:
        data = bytearray(b"%PDF-1.7\n")
        offsets = []
        for index, obj in enumerate(
            [
                *objects,
                b"<< /Length "
                + str(padding).encode()
                + b" >>\nstream\n"
                + b" " * padding
                + b"\nendstream",
            ],
            1,
        ):
            offsets.append(len(data))
            data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
        xref = len(data)
        data.extend(b"xref\n0 5\n0000000000 65535 f \n")
        for offset in offsets:
            data.extend(f"{offset:010d} 00000 n \n".encode())
        data.extend(f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        return bytes(data)

    padding = size - 500
    for _ in range(3):
        result = build(padding)
        padding += size - len(result)
    assert len(result) == size
    return result


def test_pdf_at_50_mb_uploads_and_previews(
    manager_member_client: TestClient, project_id: str
) -> None:
    data = large_pdf(50 * 1024 * 1024)
    response = manager_member_client.post(
        root(project_id), params={"name": "Large plan", "filename": "large.pdf"}, content=data
    )
    assert response.status_code == 201, response.text
    url = root(project_id) + "/" + response.json()["id"]
    assert manager_member_client.get(url + "/document").content == data
    assert manager_member_client.get(url + "/preview").status_code == 200
    too_large = manager_member_client.post(
        root(project_id),
        params={"name": "Over limit", "filename": "large.pdf"},
        content=data + b" ",
    )
    assert too_large.status_code == 413
    assert len(manager_member_client.get(root(project_id)).json()) == 1


@pytest.mark.parametrize("kind", ["link", "large_pdf"])
def test_plan_sources_migration_retains_history(
    manager_member_client: TestClient, project_id: str, db: Session, kind: str
) -> None:
    db.rollback()
    config = _alembic_config()
    command.downgrade(config, "0061_project_procedures")
    command.upgrade(config, "head")
    command.check(config)
    if kind == "link":
        response = manager_member_client.post(
            root(project_id) + "/links", json={"name": "Plan", "source_url": DRIVE_URL}
        )
    else:
        response = manager_member_client.post(
            root(project_id),
            params={"name": "Large", "filename": "large.pdf"},
            content=large_pdf(11 * 1024 * 1024),
        )
    assert response.status_code == 201, response.text
    row = response.json()
    assert (
        manager_member_client.post(
            root(project_id) + f"/{row['id']}/delete",
            json={"reason": "Retain history", "expected_version": 1},
        ).status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="Large PDFs or Drive links exist"):
        command.downgrade(config, "0061_project_procedures")
    db.rollback()
    assert db.get(ProjectDrawing, uuid.UUID(row["id"])).is_deleted
