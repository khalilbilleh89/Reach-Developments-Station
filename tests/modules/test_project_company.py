"""Company and bank entry is optional, isolated, editable and auditable."""

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.modules.audit.models import AuditEvent
from app.modules.projects.company_models import CompanyBankAccount, CompanyDocument, ProjectCompany
from app.modules.projects.models import UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, project_payload


def url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/companies"


def create(client: TestClient, project_id: str, **fields: object) -> dict:
    result = client.post(url(project_id), json=fields)
    assert result.status_code == 201, result.text
    return result.json()


def test_optional_entries_multiple_accounts_and_patch_clear(
    admin_client: TestClient, project_id: str
) -> None:
    company = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    first = admin_client.post(f"{base}/bank-accounts", json={})
    assert first.status_code == 201, first.text
    fields = {
        "beneficiary_name": "Example Ltd",
        "beneficiary_bank": "Example Bank",
        "account_number": "0000123400",
        "iban": "GB00 EXAMPLE 001",
        "swift_code": "EXAMPLE",
        "bank_address": "Address",
        "correspondent_bank": "Correspondent",
        "correspondent_swift_code": "CORRESP",
    }
    second = admin_client.post(f"{base}/bank-accounts", json=fields)
    assert second.status_code == 201, second.text
    assert all(second.json()[key] == value for key, value in fields.items())
    assert len(admin_client.get(url(project_id)).json()[0]["bank_accounts"]) == 2
    updated = admin_client.patch(base, json={"legal_name": "Example", "country": "Cyprus"})
    assert updated.status_code == 200
    updated = admin_client.patch(base, json={"legal_name": None})
    assert updated.json()["legal_name"] is None
    assert updated.json()["country"] == "Cyprus"
    account_url = f"{base}/bank-accounts/{second.json()['id']}"
    updated = admin_client.patch(account_url, json={"iban": None})
    assert updated.json()["iban"] is None
    assert updated.json()["account_number"] == "0000123400"
    assert admin_client.patch(base, json={"unknown": "value"}).status_code == 422


def test_deletion_blocks_children_retains_audit_and_repeated_requests(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    row = create(admin_client, project_id, legal_name="Retained Company")
    base = f"{url(project_id)}/{row['id']}"
    bank = admin_client.post(f"{base}/bank-accounts", json={"account_number": "001"}).json()
    assert admin_client.post(f"{base}/delete", json={"reason": "duplicate"}).status_code == 409
    bank_url = f"{base}/bank-accounts/{bank['id']}"
    assert admin_client.post(f"{bank_url}/delete", json={"reason": " "}).status_code == 422
    assert (
        admin_client.post(f"{bank_url}/delete", json={"reason": "wrong account"}).status_code == 204
    )
    assert admin_client.post(f"{bank_url}/delete", json={"reason": "again"}).status_code == 404
    assert admin_client.patch(bank_url, json={"iban": "changed"}).status_code == 404
    assert admin_client.post(f"{base}/delete", json={"reason": "duplicate"}).status_code == 204
    assert admin_client.post(f"{base}/delete", json={"reason": "again"}).status_code == 404
    assert admin_client.post(f"{base}/bank-accounts", json={}).status_code == 404
    assert admin_client.get(url(project_id)).json() == []
    db.expire_all()
    assert db.get(ProjectCompany, uuid.UUID(row["id"])).is_deleted
    assert db.get(CompanyBankAccount, uuid.UUID(bank["id"])).account_number == "001"
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(bank["id"]))
    ).all()
    assert {event.action for event in events} == {"create", "delete"}
    removed = next(event for event in events if event.action == "delete")
    assert removed.reason == "wrong account"
    assert removed.before_data["account_number"] == "001"


@pytest.mark.parametrize(
    "role,read_status,write_status",
    [
        ("finance", 200, 201),
        ("project_manager", 200, 201),
        ("executive_viewer", 200, 403),
        ("auditor", 200, 403),
        ("sales_advisor", 403, 403),
    ],
)
def test_roles_and_membership(
    admin_client: TestClient,
    project_id: str,
    db: Session,
    role: str,
    read_status: int,
    write_status: int,
) -> None:
    user = make_user(db, email=f"{role}@company.test", roles=(role,))
    client = client_for(user.email)
    assert client.get(url(project_id)).status_code == 404
    grant_access(admin_client, project_id, user)
    assert client.get(url(project_id)).status_code == read_status
    assert client.post(url(project_id), json={}).status_code == write_status
    company = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    bank = admin_client.post(f"{base}/bank-accounts", json={}).json()
    if write_status == 403:
        assert client.patch(base, json={"legal_name": "denied"}).status_code == 403
        assert client.post(f"{base}/bank-accounts", json={}).status_code == 403
        assert client.patch(f"{base}/bank-accounts/{bank['id']}", json={}).status_code == 403
        assert (
            client.post(
                f"{base}/bank-accounts/{bank['id']}/delete", json={"reason": "no"}
            ).status_code
            == 403
        )
        assert client.post(f"{base}/delete", json={"reason": "no"}).status_code == 403
    membership = db.scalars(
        select(UserProjectAccess).where(
            UserProjectAccess.user_id == user.id,
            UserProjectAccess.project_id == uuid.UUID(project_id),
        )
    ).one()
    membership.phase_scope = "selected"
    db.commit()
    assert client.get(url(project_id)).status_code == 404
    assert client.post(url(project_id), json={}).status_code == 404


def test_wrong_project_and_company_cannot_read_or_mutate(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    second = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    one = create(admin_client, project_id)
    two = create(admin_client, second)
    base = f"{url(project_id)}/{one['id']}"
    bank = admin_client.post(f"{base}/bank-accounts", json={}).json()
    wrong_project = f"{url(second)}/{one['id']}"
    assert admin_client.patch(wrong_project, json={}).status_code == 404
    assert admin_client.post(f"{wrong_project}/delete", json={"reason": "no"}).status_code == 404
    assert admin_client.post(f"{wrong_project}/bank-accounts", json={}).status_code == 404
    wrong_bank = f"{url(second)}/{two['id']}/bank-accounts/{bank['id']}"
    assert admin_client.patch(wrong_bank, json={}).status_code == 404
    assert admin_client.post(f"{wrong_bank}/delete", json={"reason": "no"}).status_code == 404
    assert admin_client.get(url(second)).json()[0]["bank_accounts"] == []


def test_company_migration_roundtrip_and_retained_history(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0032_building_units")
    command.upgrade(config, "head")
    command.check(config)
    row = create(admin_client, project_id)
    admin_client.post(f"{url(project_id)}/{row['id']}/delete", json={"reason": "retained"})
    db.rollback()
    with pytest.raises(RuntimeError, match="Company history"):
        command.downgrade(config, "0032_building_units")
    command.upgrade(config, "head")
    assert db.execute(text("SELECT count(*) FROM project_companies")).scalar() == 1


PDF = b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"


def upload_document(
    client: TestClient, base: str, label: str = "Registration", **kwargs: object
) -> Response:
    return client.post(
        f"{base}/documents",
        params={"label": label, "filename": "registration.pdf"},
        content=kwargs.get("content", PDF),
        headers={"Content-Type": "application/octet-stream"},
    )


def test_company_document_lifecycle_and_retention(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    company = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    one = upload_document(admin_client, base, " Incorporation ")
    assert one.status_code == 201, one.text
    row = one.json()
    assert row["label"] == "Incorporation"
    assert "document" not in row and "sha256" not in row
    two = upload_document(admin_client, base, "Tax registration")
    assert two.status_code == 201
    assert len(admin_client.get(f"{base}/documents").json()) == 2
    path = f"{base}/documents/{row['id']}"
    read = admin_client.get(f"{path}/file")
    assert read.content == PDF
    assert read.headers["cache-control"] == "private, no-store"
    assert read.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in read.headers["content-disposition"]
    changed = admin_client.patch(path, json={"label": "Certificate", "expected_version": 1})
    assert changed.status_code == 200
    assert changed.json()["version"] == 2
    assert (
        admin_client.patch(path, json={"label": "Stale", "expected_version": 1}).status_code == 409
    )
    assert (
        admin_client.post(
            f"{path}/delete", json={"reason": "superseded", "expected_version": 1}
        ).status_code
        == 409
    )
    assert admin_client.post(f"{base}/delete", json={"reason": "test"}).status_code == 409
    assert (
        admin_client.post(f"{path}/delete", json={"reason": " ", "expected_version": 2}).status_code
        == 422
    )
    assert (
        admin_client.post(
            f"{path}/delete", json={"reason": "superseded", "expected_version": 2}
        ).status_code
        == 204
    )
    assert admin_client.get(f"{path}/file").status_code == 404
    assert admin_client.patch(path, json={"label": "No", "expected_version": 3}).status_code == 404
    assert (
        admin_client.post(
            f"{path}/delete", json={"reason": "again", "expected_version": 3}
        ).status_code
        == 404
    )
    assert len(admin_client.get(f"{base}/documents").json()) == 1
    second_path = f"{base}/documents/{two.json()['id']}"
    assert (
        admin_client.post(
            f"{second_path}/delete", json={"reason": "test", "expected_version": 1}
        ).status_code
        == 204
    )
    assert admin_client.post(f"{base}/delete", json={"reason": "test"}).status_code == 204
    db.expire_all()
    retained = db.get(CompanyDocument, uuid.UUID(row["id"]))
    assert retained.document == PDF and retained.is_deleted
    events = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == retained.id)).all()
    assert {e.action for e in events} == {"create", "update", "delete"}
    deleted = next(e for e in events if e.action == "delete")
    assert deleted.reason == "superseded"
    assert deleted.before_data["label"] == "Certificate"
    assert len(deleted.after_data["sha256"]) == 64
    assert "document" not in deleted.after_data


@pytest.mark.parametrize(
    "filename,data,label,status",
    [
        ("file.txt", PDF, "Certificate", 422),
        ("file.pdf", b"not a PDF", "Certificate", 422),
        ("file.pdf", b"", "Certificate", 422),
        ("../file.pdf", PDF, "Certificate", 422),
        ("file.pdf", PDF, " ", 422),
        ("file.pdf", PDF, "x" * 321, 422),
        ("file.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024), "Certificate", 413),
    ],
    ids=["extension", "signature", "empty", "path", "blank-label", "long-label", "oversize"],
)
def test_company_document_validation(
    admin_client: TestClient, project_id: str, filename: str, data: bytes, label: str, status: int
) -> None:
    company = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}/documents"
    result = admin_client.post(base, params={"label": label, "filename": filename}, content=data)
    assert result.status_code == status, result.text
    assert admin_client.get(base).json() == []


@pytest.mark.parametrize(
    "role,read_status,write_status",
    [
        ("finance", 200, 201),
        ("project_manager", 200, 201),
        ("executive_viewer", 200, 403),
        ("auditor", 200, 403),
        ("sales_advisor", 403, 403),
    ],
)
def test_company_document_access(
    admin_client: TestClient,
    project_id: str,
    db: Session,
    role: str,
    read_status: int,
    write_status: int,
) -> None:
    company = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    doc = upload_document(admin_client, base).json()
    path = f"{base}/documents/{doc['id']}"
    user = make_user(db, email=f"doc-{role}@example.test", roles=[role])
    client = client_for(user.email)
    assert client.get(f"{path}/file").status_code == 404
    assert upload_document(client, base).status_code == 404
    grant_access(admin_client, project_id, user)
    assert client.get(f"{path}/file").status_code == read_status
    assert client.get(f"{base}/documents").status_code == read_status
    assert upload_document(client, base).status_code == write_status
    if write_status == 403:
        assert (
            client.patch(path, json={"label": "Denied", "expected_version": 1}).status_code == 403
        )
        assert (
            client.post(f"{path}/delete", json={"reason": "no", "expected_version": 1}).status_code
            == 403
        )
    membership = db.scalars(
        select(UserProjectAccess).where(
            UserProjectAccess.user_id == user.id,
            UserProjectAccess.project_id == uuid.UUID(project_id),
        )
    ).one()
    membership.phase_scope = "selected"
    db.commit()
    assert client.get(f"{path}/file").status_code == 404
    assert upload_document(client, base).status_code == 404


def test_document_parent_scope(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    company = create(admin_client, project_id)
    other = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    doc = upload_document(admin_client, base).json()
    second = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="DOC-OTHER")
    ).json()["id"]
    for wrong in [f"{url(project_id)}/{other['id']}", f"{url(second)}/{company['id']}"]:
        path = f"{wrong}/documents/{doc['id']}"
        assert admin_client.get(f"{path}/file").status_code == 404
        assert (
            admin_client.patch(path, json={"label": "No", "expected_version": 1}).status_code == 404
        )
        assert (
            admin_client.post(
                f"{path}/delete", json={"reason": "no", "expected_version": 1}
            ).status_code
            == 404
        )
    assert admin_client.get(f"{url(second)}/{company['id']}/documents").status_code == 404
    assert upload_document(admin_client, f"{url(second)}/{company['id']}").status_code == 404


def test_document_migration_preserves_retained_pdf(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0046_project_documents")
    command.upgrade(config, "head")
    command.check(config)
    company = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    row = upload_document(admin_client, base).json()
    admin_client.post(
        f"{base}/documents/{row['id']}/delete", json={"reason": "retained", "expected_version": 1}
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="Company documents exist"):
        command.downgrade(config, "0046_project_documents")
    command.upgrade(config, "head")
    assert db.get(CompanyDocument, uuid.UUID(row["id"])).document == PDF


def test_document_stream_does_not_lock_project_and_rechecks_parent(
    admin_client: TestClient, project_id: str
) -> None:
    company = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    lock_attempts: list[bool] = []

    def body() -> Iterator[bytes]:
        yield PDF[:8]
        with get_engine().connect() as connection:
            try:
                connection.execute(
                    text("SELECT id FROM projects WHERE id = :id FOR UPDATE NOWAIT"),
                    {"id": project_id},
                )
                lock_attempts.append(True)
            except OperationalError:
                lock_attempts.append(False)
            finally:
                connection.rollback()
        # The parent can be removed while streaming. Upload must recheck it
        # after taking the project lock and leave no orphan document.
        with get_engine().begin() as connection:
            connection.execute(
                text("SELECT id FROM projects WHERE id = :id FOR UPDATE"), {"id": project_id}
            )
            connection.execute(
                text("UPDATE project_companies SET is_deleted = true WHERE id = :id"),
                {"id": company["id"]},
            )
        yield PDF[8:]

    result = admin_client.post(
        f"{base}/documents",
        params={"label": "Registration", "filename": "registration.pdf"},
        content=body(),
    )
    assert lock_attempts == [True]
    assert result.status_code == 404


def test_profile_fields_relationships_and_bank_privacy(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    parent = create(admin_client, project_id, legal_name="Parent")
    child = create(
        admin_client,
        project_id,
        project_role="project_company_spv",
        relationship="subsidiary",
        related_company_id=parent["id"],
        ownership_percentage="25.1250",
        incorporation_date="2020-02-29",
        status="under_review",
    )
    base = f"{url(project_id)}/{child['id']}"
    assert child["ownership_percentage"] == "25.1250"
    for payload in (
        {"project_role": "bad"},
        {"ownership_percentage": "100.0001"},
        {"incorporation_date": "2020-02-30"},
        {"related_company_id": child["id"]},
    ):
        assert admin_client.patch(base, json=payload).status_code == 422
    assert (
        admin_client.patch(
            f"{url(project_id)}/{parent['id']}", json={"related_company_id": child["id"]}
        ).status_code
        == 422
    )
    assert (
        admin_client.post(
            f"{url(project_id)}/{parent['id']}/delete", json={"reason": "linked"}
        ).status_code
        == 409
    )
    account = admin_client.post(
        f"{base}/bank-accounts",
        json={
            "default_for_payments": True,
            "currency_code": "JOD",
            "status": "active",
            "account_purpose": "escrow",
            "last_verified_date": "2026-01-01",
            "bank_country": "Example",
        },
    )
    assert account.status_code == 201, account.text
    assert (
        admin_client.post(f"{base}/bank-accounts", json={"default_for_payments": True}).status_code
        == 409
    )
    account_url = f"{base}/bank-accounts/{account.json()['id']}"
    assert admin_client.patch(account_url, json={"status": "inactive"}).status_code == 422
    assert (
        admin_client.patch(
            account_url, json={"default_for_payments": False, "status": "inactive"}
        ).status_code
        == 200
    )
    user = make_user(db, email="company-pm@example.test", roles=("project_manager",))
    grant_access(admin_client, project_id, user)
    client = client_for(user.email)
    assert all(row["bank_accounts"] == [] for row in client.get(url(project_id)).json())
    assert client.post(f"{base}/bank-accounts", json={}).status_code == 403
    assert client.patch(account_url, json={}).status_code == 403
    assert client.post(f"{account_url}/delete", json={"reason": "denied"}).status_code == 403
    assert (
        admin_client.patch(
            base, json={"related_company_id": None, "ownership_percentage": None}
        ).status_code
        == 200
    )
    assert (
        admin_client.post(
            f"{url(project_id)}/{parent['id']}/delete", json={"reason": "unlinked"}
        ).status_code
        == 204
    )


def test_document_drive_metadata_and_retention(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    company = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    payload = {
        "label": "Certificate",
        "source_url": "https://drive.google.com/file/d/example/view",
        "category": "Registration",
        "linked_record": "Project record",
        "issue_date": "2020-01-01",
        "expiry_date": "2021-01-01",
        "reminder_date": "2020-12-01",
        "verification_status": "verified",
    }
    result = admin_client.post(f"{base}/documents/link", json=payload)
    assert result.status_code == 201, result.text
    row = result.json()
    assert row["reminder_status"] == "expired" and row["filename"] is None
    item = f"{base}/documents/{row['id']}"
    assert admin_client.get(f"{item}/file").status_code == 409
    assert (
        admin_client.patch(
            item, json={"label": "Certificate", "expected_version": 1, "expiry_date": "2019-01-01"}
        ).status_code
        == 422
    )
    updated = admin_client.patch(
        item,
        json={
            "label": "Updated",
            "expected_version": 1,
            "category": None,
            "verification_status": "needs_review",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["category"] is None and updated.json()["issue_date"] == "2020-01-01"
    assert (
        admin_client.post(
            f"{item}/delete", json={"reason": "old", "expected_version": 1}
        ).status_code
        == 409
    )
    assert (
        admin_client.post(
            f"{item}/delete", json={"reason": "old", "expected_version": 2}
        ).status_code
        == 204
    )
    retained = db.get(CompanyDocument, uuid.UUID(row["id"]))
    assert retained.is_deleted and retained.source_url == payload["source_url"]
    for link in (
        "javascript:alert(1)",
        "http://drive.google.com/file/d/one",
        "https://drive.google.com.evil.test/file",
        "https://evil@drive.google.com/file",
        "https://drive.google.com/",
    ):
        assert (
            admin_client.post(
                f"{base}/documents/link", json={"label": "Bad", "source_url": link}
            ).status_code
            == 422
        )
    uploaded = admin_client.post(
        f"{base}/documents",
        params={
            "label": "PDF",
            "filename": "certificate.pdf",
            "expiry_date": "2030-01-01",
            "verification_status": "needs_review",
        },
        content=PDF,
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["expiry_date"] == "2030-01-01"


def test_logo_scope_validation_and_retained_removal(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    import io

    from PIL import Image

    from app.modules.projects.company_models import CompanyLogo

    company = create(admin_client, project_id)
    other = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    assert admin_client.post(f"{base}/logos", content=b"<svg></svg>").status_code == 422
    image = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(image, format="PNG")
    result = admin_client.post(f"{base}/logos", content=image.getvalue())
    assert result.status_code == 201, result.text
    logo_id = result.json()["id"]
    logo = f"{base}/logos/{logo_id}"
    assert admin_client.get(logo).content.startswith(b"\x89PNG")
    assert admin_client.get(f"{url(project_id)}/{other['id']}/logos/{logo_id}").status_code == 404
    assert admin_client.post(f"{base}/logos", content=image.getvalue()).status_code == 409
    assert admin_client.post(f"{base}/delete", json={"reason": "logo"}).status_code == 409
    user = make_user(db, email="company-logo-read@example.test", roles=("auditor",))
    grant_access(admin_client, project_id, user)
    reader = client_for(user.email)
    assert reader.get(logo).status_code == 200
    assert reader.post(f"{base}/logos", content=image.getvalue()).status_code == 403
    assert reader.post(f"{logo}/delete", json={"reason": "denied"}).status_code == 403
    assert admin_client.post(f"{logo}/delete", json={"reason": "replace"}).status_code == 204
    assert admin_client.post(f"{logo}/delete", json={"reason": "again"}).status_code == 404
    assert admin_client.get(logo).status_code == 404
    assert db.get(CompanyLogo, uuid.UUID(logo_id)).image
    audit = db.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_type == "company_logo",
            AuditEvent.entity_id == uuid.UUID(logo_id),
            AuditEvent.action == "delete",
        )
    )
    assert audit.reason == "replace"
    assert admin_client.post(f"{base}/delete", json={"reason": "done"}).status_code == 204


def test_profile_migration_retains_legacy_pdf(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    company = create(admin_client, project_id)
    base = f"{url(project_id)}/{company['id']}"
    row = upload_document(admin_client, base).json()
    db.rollback()
    command.downgrade(config, "0068_site_reports")
    command.upgrade(config, "head")
    command.check(config)
    assert db.get(CompanyDocument, uuid.UUID(row["id"])).document == PDF
    db.rollback()
    assert admin_client.patch(base, json={"project_role": "developer"}).status_code == 200
    with pytest.raises(RuntimeError, match="Company profile data exists"):
        command.downgrade(config, "0068_site_reports")
    command.upgrade(config, "head")
