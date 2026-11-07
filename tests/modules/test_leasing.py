"""Leasing is linked to real sources, independently scoped and retained."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit
from app.modules.leasing.models import LeasingInstruction
from app.modules.projects.models import UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/leasing"


def create(client: TestClient, project: str, unit: str, **values: object) -> dict:
    response = client.post(root(project), json={"unit_id": unit, **values})
    assert response.status_code == 201, response.text
    return response.json()


def terms(row: dict, **changes: object) -> dict:
    from app.modules.leasing.schemas import Terms

    return {
        **{key: row[key] for key in Terms.model_fields},
        "expected_version": row["version"],
        "reason": "Owner instruction updated",
        **changes,
    }


def test_instruction_lifecycle(
    admin_client: TestClient, project_id: str, unit_id: str, buyer_id: str, db: Session
) -> None:
    unit = db.get(Unit, uuid.UUID(unit_id))
    original = (unit.commercial_status, unit.legal_status, unit.collection_status)
    row = create(admin_client, project_id, unit_id, owner_client_id=buyer_id)
    assert row["owner_name"] == "Rana Haddad"
    assert row["source"]["unit"]["id"] == unit_id
    assert row["currency_code"] == "JOD"
    url = root(project_id) + "/" + row["id"]
    result = admin_client.put(
        url,
        json=terms(
            row,
            status="marketing",
            mandate_date="2026-11-06",
            mandate_reference="Owner instruction 1",
            asking_rent_monthly="1250.25",
        ),
    )
    assert result.status_code == 200, result.text
    marketed = result.json()
    assert marketed["asking_rent_monthly"] == "1250.25"
    assert admin_client.put(url, json=terms(row)).status_code == 409
    assert admin_client.post(root(project_id), json={"unit_id": unit_id}).status_code == 409
    result = admin_client.put(
        url,
        json=terms(
            marketed,
            status="leased",
            tenant_name="Synthetic tenant",
            lease_start="2026-11-06",
            lease_end="2027-11-05",
            agreed_rent_monthly="1200.10",
            security_deposit="1200.10",
            agreement_reference="Lease 1",
            next_action="Renewal call",
            follow_up_date="2027-09-01",
        ),
    )
    assert result.status_code == 200, result.text
    leased = result.json()
    register = admin_client.get("/api/v1/leasing", params={"as_at": "2027-10-01"}).json()
    assert register["counts"]["expiring"] == 1
    assert register["counts"]["follow_up"] == 1
    assert "Expires within 60 days" in register["items"][0]["attention"]
    assert (
        admin_client.get(
            "/api/v1/leasing", params={"focus": "expiring", "as_at": "2027-11-06"}
        ).json()["total"]
        == 0
    )
    closed = admin_client.put(url, json=terms(leased, status="closed")).json()
    assert admin_client.put(url, json=terms(closed, status="draft")).status_code == 422
    # The next cycle can start without overwriting the prior agreement.
    replacement = create(admin_client, project_id, unit_id)
    assert replacement["id"] != row["id"]
    assert (
        admin_client.post(
            url + "/delete",
            json={"expected_version": closed["version"], "reason": "Archive closed cycle"},
        ).status_code
        == 204
    )
    assert admin_client.get(url).status_code == 404
    assert (
        admin_client.post(
            url + "/delete", json={"expected_version": closed["version"], "reason": "Again"}
        ).status_code
        == 404
    )
    db.expire_all()
    retained = db.get(LeasingInstruction, uuid.UUID(row["id"]))
    assert retained.is_deleted and retained.agreement_reference == "Lease 1"
    event = db.scalar(
        select(AuditEvent).where(AuditEvent.entity_id == retained.id, AuditEvent.action == "delete")
    )
    assert event.reason == "Archive closed cycle"
    assert event.before_data["agreement_reference"] == "Lease 1"
    unit = db.get(Unit, uuid.UUID(unit_id))
    assert (unit.commercial_status, unit.legal_status, unit.collection_status) == original


def test_leasing_access(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    row = create(admin_client, project_id, unit_id)
    url = root(project_id) + "/" + row["id"]
    user = make_user(db, email="leasing-reader@test.test", roles=("finance",))
    client = client_for(user.email)
    assert client.get("/api/v1/leasing").json()["total"] == 0
    assert client.get(url).status_code == 404
    grant_access(admin_client, project_id, user)
    assert client.get(url).status_code == 200
    assert client.post(root(project_id), json={"unit_id": unit_id}).status_code == 403
    assert client.put(url, json=terms(row)).status_code == 403
    assert (
        client.post(url + "/delete", json={"expected_version": 1, "reason": "No"}).status_code
        == 403
    )
    access = db.scalar(select(UserProjectAccess).where(UserProjectAccess.user_id == user.id))
    access.phase_scope = "selected"
    db.commit()
    assert client.get("/api/v1/leasing/projects").json() == []
    assert client.get("/api/v1/leasing").json()["total"] == 0
    assert client.get(url).status_code == 404
    assert client.get(root(project_id) + "/units").status_code == 404
    advisor = make_user(db, email="leasing-advisor@test.test", roles=("sales_advisor",))
    grant_access(admin_client, project_id, advisor)
    assert client_for(advisor.email).get("/api/v1/leasing").status_code == 403


def test_source_prefill_and_live_inventory(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    active_sale: str,
    buyer_id: str,
    db: Session,
) -> None:
    source = admin_client.get(root(project_id) + "/units/" + unit_id)
    assert source.status_code == 200, source.text
    assert source.json()["sale_client"]["id"] == buyer_id
    assert "email" not in source.text and "phone" not in source.text
    row = create(admin_client, project_id, unit_id)
    assert row["owner_client_id"] == buyer_id
    unit = db.get(Unit, uuid.UUID(unit_id))
    unit.unit_reference = "CORRECTED-UNIT"
    db.commit()
    detail = admin_client.get(root(project_id) + "/" + row["id"]).json()
    assert detail["unit_reference"] == "CORRECTED-UNIT"
    assert detail["owner_matches_sale"] is True


@pytest.mark.parametrize(
    "values",
    [
        {"status": "marketing"},
        {"asking_rent_monthly": "-1"},
        {"asking_rent_monthly": "1.234"},
        {"asking_rent_monthly": "NaN"},
        {"lease_start": "2027-01-01", "lease_end": "2026-01-01"},
        {"follow_up_date": "2027-01-01"},
        {"status": "leased"},
        {"owner_client_id": str(uuid.uuid4())},
        {"project_id": str(uuid.uuid4())},
    ],
)
def test_invalid_terms(
    admin_client: TestClient, project_id: str, unit_id: str, values: dict
) -> None:
    response = admin_client.post(root(project_id), json={"unit_id": unit_id, **values})
    assert response.status_code == 422, response.text
    assert admin_client.get("/api/v1/leasing").json()["total"] == 0


def test_wrong_scope_and_draft_removal(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    assert admin_client.post(root(str(uuid.uuid4())), json={"unit_id": unit_id}).status_code == 404
    assert (
        admin_client.post(root(project_id), json={"unit_id": str(uuid.uuid4())}).status_code == 404
    )
    row = create(admin_client, project_id, unit_id)
    assert admin_client.get(root(str(uuid.uuid4())) + "/" + row["id"]).status_code == 404
    url = root(project_id) + "/" + row["id"] + "/delete"
    assert (
        admin_client.post(url, json={"expected_version": 2, "reason": "Stale"}).status_code == 409
    )
    assert admin_client.post(url, json={"expected_version": 1, "reason": " "}).status_code == 422
    assert (
        admin_client.post(
            url, json={"expected_version": 1, "reason": "Draft entered in error"}
        ).status_code
        == 204
    )
    assert admin_client.get("/api/v1/leasing").json()["total"] == 0
    create(admin_client, project_id, unit_id)


def test_filters_and_missing_sources(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    row = create(admin_client, project_id, unit_id)
    assert row["owner_name"] is None and row["source"]["sale_client"] is None
    assert row["source"]["internal_area"] is None
    assert admin_client.get(root(project_id) + "/units").json()["total"] == 1
    assert (
        admin_client.get(root(project_id) + "/units", params={"search": "%"}).json()["total"] == 0
    )
    assert admin_client.get("/api/v1/leasing", params={"search": "%"}).json()["total"] == 0
    assert admin_client.get("/api/v1/leasing", params={"stage": "leased"}).json()["total"] == 0
    paged = admin_client.get("/api/v1/leasing", params={"offset": 1}).json()
    assert paged["items"] == [] and paged["total"] == 1


def test_leasing_migration_retention(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0064_permit_date_reconcile")
    command.upgrade(config, "head")
    command.check(config)
    row = create(admin_client, project_id, unit_id)
    admin_client.post(
        root(project_id) + "/" + row["id"] + "/delete",
        json={"expected_version": 1, "reason": "Retain"},
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="history must be retained"):
        command.downgrade(config, "0064_permit_date_reconcile")
    # A refused downgrade leaves the database where it was: at the script head,
    # whichever later revision that is.
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == (
        ScriptDirectory.from_config(config).get_current_head()
    )
