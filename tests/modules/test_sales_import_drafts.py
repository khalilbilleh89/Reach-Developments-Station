"""Real PostgreSQL contracts for unposted Sales workbook intake."""

import io
import uuid
from datetime import datetime

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.modules.inventory.models import Unit
from app.modules.sales import import_draft_workbook as workbook
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import sales_url


@pytest.fixture
def boss(db: Session) -> TestClient:
    return client_for(make_user(db, email="bulk-owner@example.com", roles=("master_admin",)).email)


@pytest.fixture
def payload(db: Session, released_unit: str, buyer_id: str) -> dict:
    unit = db.get(Unit, uuid.UUID(released_unit))
    return {
        "Sales": [{"unit_reference": unit.unit_reference, "client_id": buyer_id}],
        "EOI": [{"signed": True, "occurred_at": "2026-11-02T09:30:17+02:00", "amount": "1234.56"}],
        "Receipts": [
            {
                "amount": "50.00",
                "receipt_date": "2026-10-01",
                "notes": "Imported claim, not confirmed cash",
            }
        ],
        "Legal": [{"event_date": "2026-10-01", "document_reference": "source.pdf"}],
        "Installments": [{"sequence": 1, "label": "First payment", "principal_amount": "100.00"}],
    }


def root(project: str) -> str:
    return f"{sales_url(project)}/import-drafts"


def upload(
    boss: TestClient, project: str, payload: dict, operation: str = "apply", key: str = "SOURCE-1"
) -> dict:
    response = boss.post(
        f"{root(project)}/workbook/{operation}",
        content=workbook.template(project, [(key, payload)]),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def draft(boss: TestClient, project: str) -> dict:
    response = boss.get(root(project))
    assert response.status_code == 200, response.text
    return response.json()[0]


def test_draft_import_is_unposted_atomic_and_idempotent(
    boss: TestClient, project_id: str, payload: dict, db: Session
) -> None:
    checked = upload(boss, project_id, payload, "validate")
    assert checked["error_count"] == 0, checked
    assert db.scalar(text("select count(*) from sales_import_drafts")) == 0
    db.rollback()
    result = upload(boss, project_id, payload)
    assert result["created_count"] == 1, result
    row = draft(boss, project_id)
    assert row["status"] == "draft"
    assert row["payload"]["Receipts"][0]["amount"] == "50.00"
    assert datetime.fromisoformat(row["payload"]["EOI"][0]["occurred_at"]).second == 17
    for table in (
        "reservations",
        "sale_contracts",
        "collection_receipts",
        "payment_plans",
        "sale_legal_events",
    ):
        assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    db.rollback()
    retry = upload(boss, project_id, payload)
    assert retry["duplicate_count"] == 1 and retry["created_count"] == 0
    payload["Sales"][0]["notes"] = "Changed"
    assert upload(boss, project_id, payload)["error_count"] == 1


def test_bad_row_rolls_back_whole_file(
    boss: TestClient, project_id: str, payload: dict, db: Session
) -> None:
    bad = {
        "Sales": [{"unit_reference": "nonexistent", "client_id": payload["Sales"][0]["client_id"]}]
    }
    response = boss.post(
        f"{root(project_id)}/workbook/apply",
        content=workbook.template(project_id, [("good", payload), ("bad", bad)]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["error_count"] == 1
    assert response.json()["created_count"] == 0
    assert db.scalar(text("SELECT count(*) FROM sales_import_drafts")) == 0


def test_review_add_and_delete_preserve_source_and_inventory(
    boss: TestClient, project_id: str, payload: dict, db: Session
) -> None:
    assert upload(boss, project_id, payload)["created_count"] == 1
    row = draft(boss, project_id)
    response = boss.post(
        f"{root(project_id)}/{row['id']}/add",
        json={"version": row["version"], "reason": "Reviewed all source sections"},
    )
    assert response.status_code == 200, response.text
    added = response.json()
    assert added["status"] == "added" and added["reservation_id"]
    assert added["payload"] == row["payload"]
    assert (
        db.scalar(select(Unit.commercial_status).where(Unit.id == uuid.UUID(row["unit_id"])))
        == "available"
    )
    assert db.scalar(text("select count(*) from collection_receipts")) == 0
    db.rollback()
    assert (
        boss.post(
            f"{root(project_id)}/{row['id']}/add",
            json={"version": row["version"], "reason": "Retry"},
        ).status_code
        == 409
    )
    assert (
        boss.delete(
            f"{root(project_id)}/{row['id']}",
            params={"version": added["version"], "reason": "Retain source"},
        ).status_code
        == 409
    )
    source = boss.get(f"{root(project_id)}/by-reservation/{added['reservation_id']}")
    assert source.status_code == 200 and source.json()["id"] == row["id"]


def test_corrections_stale_review_and_draft_deletion(
    boss: TestClient, project_id: str, payload: dict
) -> None:
    upload(boss, project_id, payload)
    row = draft(boss, project_id)
    url = f"{root(project_id)}/{row['id']}"
    payload["Sales"][0]["notes"] = "Corrected"
    result = boss.put(url, json={"version": 1, "reason": "Correction", "payload": payload})
    assert result.status_code == 200, result.text
    assert result.json()["version"] == 2
    assert boss.delete(url, params={"version": 1, "reason": "Stale"}).status_code == 409
    assert boss.delete(url, params={"version": 2, "reason": "Test draft"}).status_code == 204
    assert boss.get(url).status_code == 404
    assert boss.delete(url, params={"version": 2, "reason": "Again"}).status_code == 404


def test_authorization_and_project_scope(
    boss: TestClient,
    admin_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    payload: dict,
) -> None:
    upload(boss, project_id, payload)
    row = draft(boss, project_id)
    for actor in (admin_client, sales_ops_client):
        assert actor.get(root(project_id)).status_code == 403
        assert actor.get(f"{root(project_id)}/template").status_code == 403
        assert actor.post(f"{root(project_id)}/workbook/apply", content=b"bad").status_code == 403
        assert (
            actor.delete(
                f"{root(project_id)}/{row['id']}", params={"version": 1, "reason": "No"}
            ).status_code
            == 403
        )
    assert boss.get(f"{root(str(uuid.uuid4()))}/{row['id']}").status_code == 404


@pytest.mark.parametrize(
    "change",
    [{"amount": "1.001"}, {"amount": "-1"}, {"occurred_at": "2026-11-02T10:00:00"}],
    ids=["precision", "negative", "naive-time"],
)
def test_eoi_validation(boss: TestClient, project_id: str, payload: dict, change: dict) -> None:
    payload["EOI"][0].update(change)
    assert upload(boss, project_id, payload)["error_count"] > 0


def test_export_roundtrip_and_all_sections(
    boss: TestClient, project_id: str, payload: dict
) -> None:
    template = boss.get(f"{root(project_id)}/template")
    assert template.status_code == 200, template.text
    book = load_workbook(io.BytesIO(template.content))
    assert set(workbook.COLUMNS).issubset(book.sheetnames)
    assert "Buyer reference" in book and "Unit reference" in book and "Field guide" in book
    book.close()
    upload(boss, project_id, payload)
    row = draft(boss, project_id)
    exported = boss.get(f"{root(project_id)}/{row['id']}/workbook")
    assert exported.status_code == 200
    parsed = workbook.parse(exported.content, project_id)
    assert workbook.validate_payload(parsed[0][2]) == row["payload"]


def test_formula_wrong_project_and_orphan_rows(
    boss: TestClient, project_id: str, payload: dict
) -> None:
    body = workbook.template(str(uuid.uuid4()), [("A", payload)])
    assert boss.post(f"{root(project_id)}/workbook/validate", content=body).status_code == 422
    payload["Sales"][0]["notes"] = "=HYPERLINK(1)"
    assert (
        boss.post(
            f"{root(project_id)}/workbook/validate",
            content=workbook.template(project_id, [("A", payload)]),
        ).status_code
        == 422
    )
    payload["Sales"][0].pop("notes")
    with pytest.raises(Exception, match="absent from Sales"):
        workbook.parse(
            workbook.template(
                project_id,
                [
                    ("A", {"Buyer": [{"display_name": "Orphan"}]}),
                    ("B", {"Sales": payload["Sales"]}),
                ],
            ),
            project_id,
        )


def test_failed_add_is_atomic(
    boss: TestClient, project_id: str, payload: dict, db: Session
) -> None:
    payload["Sales"][0].pop("client_id")
    payload["Buyer"] = [{"display_name": "New review buyer"}]
    payload["Reservation"] = [{"expires_on": "2000-01-01"}]
    upload(boss, project_id, payload)
    row = draft(boss, project_id)
    before = db.scalar(text("select count(*) from clients"))
    db.rollback()
    result = boss.post(
        f"{root(project_id)}/{row['id']}/add", json={"version": 1, "reason": "Try review"}
    )
    assert result.status_code == 422, result.text
    assert db.scalar(text("select count(*) from clients")) == before
    assert db.scalar(text("select count(*) from reservations")) == 0
    db.rollback()
    assert draft(boss, project_id)["status"] == "draft"


def test_migration_roundtrip(postgres: None) -> None:
    config = alembic_config()
    command.downgrade(config, "0057_workspace_views")
    command.upgrade(config, "head")
    command.check(config)
    with get_engine().connect() as connection:
        assert (
            connection.scalar(text("select version_num from alembic_version"))
            == ScriptDirectory.from_config(config).get_current_head()
        )
        assert connection.scalar(text("select to_regclass('sales_import_drafts')")) is not None


def test_new_buyer_agent_and_unit_purge(
    boss: TestClient, project_id: str, payload: dict, db: Session
) -> None:
    from tests.modules.test_inventory_purge import payload_from, remove

    payload["Sales"][0].pop("client_id")
    payload["Buyer"] = [{"display_name": "Import purchaser"}]
    payload["Agent"] = [
        {
            "display_name": "Import agent",
            "country": "Cyprus",
            "branch": "Larnaca",
            "branch_leader": "Leader",
        }
    ]
    assert upload(boss, project_id, payload)["created_count"] == 1
    row = draft(boss, project_id)
    added = boss.post(
        f"{root(project_id)}/{row['id']}/add", json={"version": 1, "reason": "Reviewed"}
    )
    assert added.status_code == 200, added.text
    assert (
        db.scalar(text("select count(*) from clients where display_name = 'Import purchaser'")) == 1
    )
    assert (
        db.scalar(text("select count(*) from sales_agents where display_name = 'Import agent'"))
        == 1
    )
    db.rollback()
    # A preparing transaction must be closed before an explicit unit history purge.
    reservation_id = added.json()["reservation_id"]
    closed = boss.post(
        f"{sales_url(project_id)}/reservations/{reservation_id}/cancel", json={"reason": "Test"}
    )
    assert closed.status_code in {200, 204}, closed.text
    url = remove(boss, project_id, row["unit_id"])
    preview = boss.get(f"{url}/purge-preview")
    assert preview.status_code == 200, preview.text
    assert any(item["label"] == "Imported Sales source drafts" for item in preview.json()["counts"])
    erased = boss.post(f"{url}/purge", json=payload_from(preview.json()))
    assert erased.status_code == 204, erased.text
    assert boss.get(f"{root(project_id)}/{row['id']}").status_code == 404
