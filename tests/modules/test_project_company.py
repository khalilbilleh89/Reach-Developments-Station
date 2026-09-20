"""Company and bank entry is optional, isolated, editable and auditable."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.company_models import CompanyBankAccount, ProjectCompany
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
