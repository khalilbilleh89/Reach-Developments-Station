"""Drawing upload, stable-unit mapping, whole-project security and audited removal."""

import io
import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from httpx2 import Response
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit
from tests.conftest import alembic_config
from tests.factories import client_for
from tests.modules.conftest import grant_access, inventory_url, project_payload


def root(project: str) -> str:
    return f"{inventory_url(project)}/masterplans"


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buffer, "PNG")
    return buffer.getvalue()


def upload(client: TestClient, project: str, **overrides: object) -> Response:
    params = {
        "title": "Synthetic masterplan",
        "source_reference": "A-01 rev test",
        "filename": "plan.png",
        "width_m": "100",
        **overrides,
    }
    return client.post(
        root(project),
        params=params,
        content=png(),
        headers={"Content-Type": "application/octet-stream"},
    )


def footprint(unit: str, **overrides: object) -> dict:
    return {
        "unit_id": unit,
        "points": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]],
        "base_m": "0",
        "height_m": "3",
        **overrides,
    }


def test_inventory_masterplan_lifecycle_stable_identity_and_live_status(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    created = upload(admin_client, project_id)
    assert created.status_code == 201, created.text
    plan = created.json()
    path = f"{root(project_id)}/{plan['id']}"
    assert admin_client.get(path + "/preview").content.startswith(b"\x89PNG")
    preview = admin_client.get(path + "/preview")
    assert preview.headers["cache-control"] == "no-store"
    original = admin_client.get(path + "/source")
    assert original.content == png()
    assert original.headers["content-type"] == "application/octet-stream"
    assert original.headers["content-disposition"].startswith("attachment;")
    assert "source_data" not in created.text and "preview_data" not in created.text
    created_mapping = admin_client.post(path + "/mappings", json=footprint(unit_id))
    assert created_mapping.status_code == 201, created_mapping.text
    mapping = created_mapping.json()
    assert admin_client.post(path + "/mappings", json=footprint(unit_id)).status_code == 409
    # The map stores identity and geometry only. Inventory remains the status owner.
    assert "commercial_status" not in mapping
    unit = db.get(Unit, uuid.UUID(unit_id))
    unit.commercial_status = "contracted"
    unit.unit_reference = "RENAMED-101"
    db.commit()
    rows = admin_client.get(f"{inventory_url(project_id)}/units").json()["units"]
    assert rows[0]["commercial_status"] == "contracted"
    assert rows[0]["unit_reference"] == "RENAMED-101"
    assert admin_client.get(path + "/mappings").json()[0]["unit_id"] == unit_id
    updated = admin_client.put(
        path + f"/mappings/{mapping['id']}",
        json={**footprint(unit_id, height_m="3.5"), "version": 1},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert (
        admin_client.put(
            path + f"/mappings/{mapping['id']}", json={**footprint(unit_id), "version": 1}
        ).status_code
        == 409
    )
    assert (
        admin_client.delete(path, params={"version": 1, "reason": "Unused plan"}).status_code == 409
    )
    mapping_path = path + f"/mappings/{mapping['id']}"
    assert (
        admin_client.delete(mapping_path, params={"version": 1, "reason": "Correction"}).status_code
        == 409
    )
    assert (
        admin_client.delete(mapping_path, params={"version": 2, "reason": "   "}).status_code == 422
    )
    assert (
        admin_client.delete(mapping_path, params={"version": 2, "reason": "Correction"}).status_code
        == 204
    )
    assert (
        admin_client.delete(mapping_path, params={"version": 2, "reason": "Repeat"}).status_code
        == 404
    )
    changed = admin_client.put(
        path,
        json={
            "title": "Revised name",
            "source_reference": "A-01",
            "kind": "plan",
            "width_m": "120",
            "version": 1,
        },
    )
    assert changed.status_code == 200
    assert admin_client.delete(path, params={"version": 1, "reason": "Stale"}).status_code == 409
    assert (
        admin_client.delete(path, params={"version": 2, "reason": "Unused view"}).status_code == 204
    )
    assert admin_client.get(path + "/preview").status_code == 404
    db.expire_all()
    assert db.get(Unit, uuid.UUID(unit_id)).commercial_status == "contracted"
    events = list(db.scalars(select(AuditEvent).where(AuditEvent.action.like("masterplan.%"))))
    assert len(events) == 6
    assert any(
        e.action == "masterplan.mapping_deleted" and e.after_data["reason"] == "Correction"
        for e in events
    )


@pytest.mark.parametrize(
    "points",
    [
        [[0, 0], [1, 1]],
        [[0, 0], [0.5, 0.5], [1, 1]],
        [[0, 0], [1.1, 0], [1, 1]],
        [[0, 0], [1, 1], [0, 1], [1, 0]],
        [[0, 0], [1, 0], [1, 1], [0, 0]],
    ],
)
def test_inventory_masterplan_rejects_invalid_geometry(
    admin_client: TestClient, project_id: str, unit_id: str, points: list
) -> None:
    plan = upload(admin_client, project_id).json()
    result = admin_client.post(
        f"{root(project_id)}/{plan['id']}/mappings", json=footprint(unit_id, points=points)
    )
    assert result.status_code == 422, result.text


def test_inventory_masterplan_upload_validation(
    admin_client: TestClient, operational_project: str
) -> None:
    for values in ({"title": " "}, {"kind": "invalid"}, {"width_m": "0"}, {"width_m": "NaN"}):
        assert upload(admin_client, operational_project, **values).status_code == 422
    params = {"title": "Plan", "source_reference": "A-01", "filename": "bad.svg"}
    for body in (b"", b"<svg onload='alert(1)'/>", b"%PDF-broken"):
        response = admin_client.post(root(operational_project), params=params, content=body)
        assert response.status_code == 422, response.text
    response = admin_client.post(
        root(operational_project), params=params, content=b"x" * (10 * 1024 * 1024 + 1)
    )
    assert response.status_code == 422


def test_inventory_masterplan_pdf_pages(admin_client: TestClient, operational_project: str) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(buffer, "PDF")
    params = {"title": "PDF page", "source_reference": "A-02", "filename": "plan.pdf"}
    result = admin_client.post(root(operational_project), params=params, content=buffer.getvalue())
    assert result.status_code == 201, result.text
    plan = result.json()
    assert plan["pixel_width"] <= 2560 and plan["pixel_height"] <= 2560
    params["page_number"] = 1
    assert (
        admin_client.post(
            root(operational_project), params=params, content=buffer.getvalue()
        ).status_code
        == 422
    )


def test_inventory_masterplan_permissions_and_wrong_project(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    advisor: User,
    db: Session,
    country_pack_id: str,
    currency_id: str,
) -> None:
    grant_access(admin_client, project_id, advisor)
    reader = client_for(advisor.email)
    plan = upload(admin_client, project_id).json()
    path = f"{root(project_id)}/{plan['id']}"
    assert reader.get(root(project_id)).status_code == 200
    assert reader.get(path + "/preview").status_code == 200
    assert upload(reader, project_id).status_code == 403
    assert reader.post(path + "/mappings", json=footprint(unit_id)).status_code == 403
    assert (
        reader.put(
            path, json={"title": "No", "source_reference": "X", "kind": "plan", "version": 1}
        ).status_code
        == 403
    )
    assert reader.delete(path, params={"version": 1, "reason": "No"}).status_code == 403
    other = admin_client.post(
        "/api/v1/projects", json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    admin_client.patch(f"/api/v1/projects/{other}", json={"status": "predevelopment"})
    assert reader.get(root(other)).status_code == 404
    assert admin_client.get(f"{root(other)}/{plan['id']}/preview").status_code == 404
    assert (
        admin_client.post(
            f"{root(other)}/{plan['id']}/mappings", json=footprint(unit_id)
        ).status_code
        == 404
    )
    other_plan = upload(admin_client, other).json()
    assert (
        admin_client.post(
            f"{root(other)}/{other_plan['id']}/mappings", json=footprint(unit_id)
        ).status_code
        == 404
    )
    # An image is intrinsically project-wide; selected-phase access is refused.
    from app.modules.projects.models import UserProjectAccess

    access = db.scalar(
        select(UserProjectAccess).where(
            UserProjectAccess.project_id == uuid.UUID(project_id),
            UserProjectAccess.user_id == advisor.id,
        )
    )
    access.phase_scope = "selected"
    db.commit()
    for endpoint in (root(project_id), path + "/preview", path + "/mappings", path + "/source"):
        assert reader.get(endpoint).status_code == 403


def test_inventory_masterplan_migration_roundtrip_and_retained_source(
    admin_client: TestClient, operational_project: str, db: Session
) -> None:
    plan = upload(admin_client, operational_project).json()
    db.rollback()
    config = alembic_config()
    with pytest.raises(RuntimeError, match="Drawing sources prevent downgrade"):
        command.downgrade(config, "0044_team_job_description")
    assert db.scalar(text("SELECT count(*) FROM inventory_masterplans")) == 1
    assert (
        admin_client.delete(
            f"{root(operational_project)}/{plan['id']}",
            params={"version": 1, "reason": "Remove synthetic drawing"},
        ).status_code
        == 204
    )
    db.rollback()
    command.downgrade(config, "0044_team_job_description")
    command.upgrade(config, "head")
    assert db.scalar(text("SELECT count(*) FROM inventory_masterplan_mappings")) == 0
