"""Sales delivery guide: persisted facts, authorization and retained confirmations."""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access


def url(project: str | uuid.UUID) -> str:
    return f"/api/v1/projects/{project}/construction/technical-specifications"


def payload(**changes: object) -> dict:
    return {
        "category": "finishes",
        "title": "Bathroom floor tiles",
        "scope": "units",
        "applies_to": "All unit bathrooms",
        "description": "Synthetic sample: porcelain tiles.",
        **changes,
    }


def test_create_edit_stale_delete_and_audit(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    response = admin_client.post(url(project_id), json=payload())
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["status"] == "draft" and row["inclusion"] == "undecided"
    path = f"{url(project_id)}/{row['id']}"
    updated = admin_client.put(path, json=payload(description="Revised synthetic tiles", version=1))
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert admin_client.put(path, json=payload(version=1)).status_code == 409
    assert admin_client.get(url(project_id)).json()[0]["description"] == "Revised synthetic tiles"
    assert admin_client.delete(path, params={"reason": " "}).status_code == 422
    assert admin_client.delete(path, params={"reason": "Duplicate draft"}).status_code == 204
    assert admin_client.get(url(project_id)).json() == []
    assert admin_client.delete(path, params={"reason": "Again"}).status_code == 404
    assert db.scalar(text("SELECT count(*) FROM technical_specifications")) == 0
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "technical_specification")
            .order_by(AuditEvent.occurred_at)
        )
    )
    assert len(events) == 3
    assert events[-1].before_data["description"] == "Revised synthetic tiles"
    assert events[-1].reason == "Duplicate draft"


@pytest.mark.parametrize("role", ["sales_advisor", "sales_operations"])
def test_sales_reads_specs_without_cost_access(
    admin_client: TestClient, project_id: str, db: Session, role: str
) -> None:
    actor = make_user(db, email=f"{role}@example.com", roles=(role,))
    grant_access(admin_client, project_id, actor)
    reader = client_for(actor.email)
    created = admin_client.post(url(project_id), json=payload()).json()
    assert reader.get(url(project_id)).json()[0]["id"] == created["id"]
    assert reader.get(f"/api/v1/projects/{project_id}/construction/summary").status_code == 403
    assert reader.post(url(project_id), json=payload()).status_code == 403
    assert reader.put(f"{url(project_id)}/{created['id']}", json=payload()).status_code == 403
    assert (
        reader.delete(f"{url(project_id)}/{created['id']}", params={"reason": "No"}).status_code
        == 403
    )
    assert reader.get(url(uuid.uuid4())).status_code == 404


def test_confirmed_specs_require_decided_inclusion_and_retain_deleted_history(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    assert (
        admin_client.post(
            url(project_id), json=payload(status="confirmed", source_reference="Drawing A1")
        ).status_code
        == 422
    )
    row = admin_client.post(
        url(project_id),
        json=payload(
            status="confirmed", inclusion="included", source_reference="Synthetic schedule Rev A"
        ),
    ).json()
    assert (
        admin_client.delete(
            f"{url(project_id)}/{row['id']}", params={"reason": "Superseded"}
        ).status_code
        == 204
    )
    assert admin_client.get(url(project_id)).json() == []
    assert (
        db.scalar(
            text("SELECT count(*) FROM technical_specifications WHERE removed_at IS NOT NULL")
        )
        == 1
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="retained confirmations"):
        command.downgrade(alembic_config(), "0030_unit_removal")


def test_wrong_project_and_phase_scope_are_refused(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    from app.modules.projects.models import UserProjectAccess

    actor = make_user(db, email="limited@example.com", roles=("design_engineering",))
    grant_access(admin_client, project_id, actor)
    access = db.scalar(select(UserProjectAccess).where(UserProjectAccess.user_id == actor.id))
    access.phase_scope = "selected"
    db.commit()
    limited = client_for(actor.email)
    assert limited.get(url(project_id)).status_code == 403
    assert limited.post(url(project_id), json=payload()).status_code == 403
    row = admin_client.post(url(project_id), json=payload()).json()
    assert admin_client.put(f"{url(uuid.uuid4())}/{row['id']}", json=payload()).status_code == 404
    assert (
        admin_client.delete(
            f"{url(uuid.uuid4())}/{row['id']}", params={"reason": "Wrong project"}
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"description": " "},
        {"category": "invented"},
        {"unexpected": True},
        {"description": None},
        {"buyer_benefit": None},
        {"buyer_benefit": "x" * 2001},
    ],
)
def test_invalid_specification_refused(
    admin_client: TestClient, project_id: str, changes: dict
) -> None:
    assert admin_client.post(url(project_id), json=payload(**changes)).status_code == 422


def test_specification_migration_roundtrip(db: Session) -> None:
    db.rollback()
    command.downgrade(alembic_config(), "0030_unit_removal")
    command.upgrade(alembic_config(), "head")
    assert db.scalar(text("SELECT count(*) FROM technical_specifications")) == 0


def test_buyer_benefit_is_versioned_audited_and_preserved_for_old_clients(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    created = admin_client.post(
        url(project_id), json=payload(buyer_benefit="  Easier daily maintenance.  ")
    ).json()
    assert created["buyer_benefit"] == "Easier daily maintenance."
    path = f"{url(project_id)}/{created['id']}"
    legacy = admin_client.put(path, json=payload(version=1))
    assert legacy.status_code == 200
    assert legacy.json()["buyer_benefit"] == "Easier daily maintenance."
    updated = admin_client.put(
        path, json=payload(version=2, buyer_benefit="A revised explanation.")
    )
    assert updated.status_code == 200
    assert updated.json()["buyer_benefit"] == "A revised explanation."
    assert admin_client.put(path, json=payload(version=1, buyer_benefit="Stale")).status_code == 409
    event = db.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.entity_id == uuid.UUID(created["id"]),
            AuditEvent.action == "technical_specification.updated",
        )
        .order_by(AuditEvent.occurred_at.desc())
    )
    assert event.before_data["buyer_benefit"] == "Easier daily maintenance."
    assert event.after_data["buyer_benefit"] == "A revised explanation."
    assert admin_client.delete(path, params={"reason": "Duplicate"}).status_code == 204
    db.expire_all()
    removed = db.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_id == uuid.UUID(created["id"]),
            AuditEvent.action == "technical_specification.deleted",
        )
    )
    assert removed.before_data["buyer_benefit"] == "A revised explanation."


def test_buyer_benefit_migration_preserves_records_and_blocks_loss(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    created = admin_client.post(url(project_id), json=payload()).json()
    db.rollback()
    command.downgrade(alembic_config(), "0050_project_matrices")
    command.upgrade(alembic_config(), "head")
    row = admin_client.get(url(project_id)).json()[0]
    assert row["id"] == created["id"] and row["description"] == created["description"]
    assert row["buyer_benefit"] == ""
    result = admin_client.put(
        f"{url(project_id)}/{row['id']}",
        json=payload(
            version=1,
            buyer_benefit="Retain this explanation.",
            status="confirmed",
            inclusion="included",
            source_reference="Synthetic schedule A",
        ),
    )
    assert result.status_code == 200
    assert (
        admin_client.delete(
            f"{url(project_id)}/{row['id']}", params={"reason": "Replaced"}
        ).status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="Buyer benefits exist"):
        command.downgrade(alembic_config(), "0050_project_matrices")


def image_bytes() -> bytes:
    import io

    from PIL import Image

    output = io.BytesIO()
    Image.new("RGB", (3, 2), "blue").save(output, format="PNG")
    return output.getvalue()


def test_optional_images_roundtrip_access_removal_and_parent_retention(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    from app.modules.construction.models import SpecificationImage, TechnicalSpecification

    created = admin_client.post(url(project_id), json=payload()).json()
    assert created["images"] == []
    path = f"{url(project_id)}/{created['id']}"
    uploaded = admin_client.post(
        path + "/images", params={"filename": "folder/tile.png"}, content=image_bytes()
    )
    assert uploaded.status_code == 201, uploaded.text
    image = uploaded.json()
    assert image["filename"] == "tile.png"
    assert "image_data" not in image
    assert admin_client.get(url(project_id)).json()[0]["images"][0]["id"] == image["id"]
    file_path = path + "/images/" + image["id"] + "/file"
    reader_user = make_user(db, email="image-sales@example.test", roles=("sales_advisor",))
    grant_access(admin_client, project_id, reader_user)
    reader = client_for(reader_user.email)
    response = reader.get(file_path)
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert (
        reader.post(
            path + "/images", params={"filename": "no.png"}, content=image_bytes()
        ).status_code
        == 403
    )
    assert (
        reader.delete(path + "/images/" + image["id"], params={"reason": "No"}).status_code == 403
    )
    assert (
        admin_client.delete(path + "/images/" + image["id"], params={"reason": " "}).status_code
        == 422
    )
    assert (
        admin_client.delete(
            path + "/images/" + image["id"], params={"reason": "Replaced sample"}
        ).status_code
        == 204
    )
    assert admin_client.get(file_path).status_code == 404
    assert admin_client.get(url(project_id)).json()[0]["images"] == []
    assert (
        admin_client.delete(path + "/images/" + image["id"], params={"reason": "Again"}).status_code
        == 404
    )
    assert (
        admin_client.delete(path, params={"reason": "Remove draft with image history"}).status_code
        == 204
    )
    assert admin_client.get(url(project_id)).json() == []
    stored = db.get(SpecificationImage, uuid.UUID(image["id"]))
    assert stored.removed_at and stored.image_data
    assert db.get(TechnicalSpecification, uuid.UUID(created["id"])).removed_at
    assert (
        db.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_type == "specification_image",
                AuditEvent.action == "specification_image.deleted",
            )
        ).reason
        == "Replaced sample"
    )


def test_images_enforce_parent_project_and_phase_scope(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    from app.modules.projects.models import UserProjectAccess

    created = admin_client.post(url(project_id), json=payload()).json()
    other = admin_client.post(url(project_id), json=payload(title="Other item")).json()
    path = f"{url(project_id)}/{created['id']}"
    image = admin_client.post(
        path + "/images", params={"filename": "image.png"}, content=image_bytes()
    ).json()
    wrong_parent = f"{url(project_id)}/{other['id']}/images/{image['id']}"
    assert admin_client.get(wrong_parent + "/file").status_code == 404
    assert admin_client.delete(wrong_parent, params={"reason": "Wrong parent"}).status_code == 404
    wrong_project = f"{url(uuid.uuid4())}/{created['id']}/images/{image['id']}"
    assert admin_client.get(wrong_project + "/file").status_code == 404
    actor = make_user(db, email="phase-images@example.test", roles=("design_engineering",))
    grant_access(admin_client, project_id, actor)
    access = db.scalar(select(UserProjectAccess).where(UserProjectAccess.user_id == actor.id))
    access.phase_scope = "selected"
    db.commit()
    limited = client_for(actor.email)
    assert limited.get(path + "/images/" + image["id"] + "/file").status_code == 403
    assert (
        limited.post(
            path + "/images", params={"filename": "image.png"}, content=image_bytes()
        ).status_code
        == 403
    )
    assert admin_client.delete(path, params={"reason": "Remove parent"}).status_code == 204
    assert admin_client.get(path + "/images/" + image["id"] + "/file").status_code == 404
    assert (
        admin_client.post(
            path + "/images", params={"filename": "image.png"}, content=image_bytes()
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "data",
    [
        b"not an image",
        b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        b"\x89PNG\r\n\x1a\n",
        b"x" * (10 * 1024 * 1024 + 1),
    ],
    ids=["invalid", "svg", "truncated", "too-large"],
)
def test_invalid_images_never_create_a_record(
    admin_client: TestClient, project_id: str, db: Session, data: bytes
) -> None:
    created = admin_client.post(url(project_id), json=payload()).json()
    response = admin_client.post(
        f"{url(project_id)}/{created['id']}/images", params={"filename": "image.png"}, content=data
    )
    assert response.status_code == 422, response.text
    assert db.scalar(text("SELECT count(*) FROM specification_images")) == 0


def test_image_processing_discards_metadata_and_enforces_limit(
    admin_client: TestClient, project_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    from PIL import Image, PngImagePlugin

    from app.modules.construction import specification_images

    created = admin_client.post(url(project_id), json=payload()).json()
    path = f"{url(project_id)}/{created['id']}/images"
    source = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private-note", "Remove this metadata")
    Image.new("RGB", (2, 2), "red").save(source, format="PNG", pnginfo=metadata)
    monkeypatch.setattr(specification_images, "MAX_IMAGES", 1)
    first = admin_client.post(path, params={"filename": "sample.png"}, content=source.getvalue())
    assert first.status_code == 201
    body = admin_client.get(path + "/" + first.json()["id"] + "/file").content
    assert b"Remove this metadata" not in body
    assert (
        admin_client.post(
            path, params={"filename": "second.png"}, content=image_bytes()
        ).status_code
        == 422
    )


def test_image_migration_roundtrip_and_retention(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    db.rollback()
    command.downgrade(alembic_config(), "0053_marketing_economics")
    command.upgrade(alembic_config(), "head")
    created = admin_client.post(url(project_id), json=payload()).json()
    response = admin_client.post(
        f"{url(project_id)}/{created['id']}/images",
        params={"filename": "image.png"},
        content=image_bytes(),
    )
    assert response.status_code == 201
    db.rollback()
    with pytest.raises(RuntimeError, match="retained evidence"):
        command.downgrade(alembic_config(), "0053_marketing_economics")


def test_optional_fields_and_buildable_area_persist_without_source(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    values = payload(scope="buildable", status="confirmed", inclusion="included")
    values.pop("applies_to")
    response = admin_client.post(url(project_id), json=values)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["scope"] == "buildable" and row["applies_to"] == "" and row["source_reference"] == ""
    assert row["images"] == []
    saved = admin_client.get(url(project_id)).json()[0]
    assert saved["id"] == row["id"] and saved["source_reference"] == ""
    db.rollback()
    with pytest.raises(RuntimeError, match="cannot be represented"):
        command.downgrade(alembic_config(), "0053_marketing_economics")
