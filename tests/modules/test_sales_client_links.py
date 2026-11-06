"""Client links share buyer permissions, preserve URLs and remain removable."""

import io
import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.sales import import_draft_workbook
from app.modules.sales.schemas import ClientCreateRequest
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import sales_url
from tests.modules.test_sales_import import upload, workbook

LINKS = {
    "client_folder_url": "https://drive.google.com/drive/folders/client-example?usp=sharing",
    "odoo_opportunity_url": "https://crm.example.com/web#id=71&model=crm.lead&view_type=form",
}


def test_create_read_edit_clear_audit(
    sales_ops_client: TestClient, operational_project: str, db: Session
) -> None:
    base = f"{sales_url(operational_project)}/clients"
    created = sales_ops_client.post(base, json={"display_name": "Linked buyer", **LINKS})
    assert created.status_code == 201, created.text
    url = f"{base}/{created.json()['id']}"
    assert all(created.json()[key] == value for key, value in LINKS.items())
    assert all(sales_ops_client.get(url).json()[key] == value for key, value in LINKS.items())
    patch = sales_ops_client.patch(url, json={"display_name": "Renamed buyer"})
    assert (
        patch.status_code == 200
        and patch.json()["odoo_opportunity_url"] == LINKS["odoo_opportunity_url"]
    )
    for value in (None, "   "):
        response = sales_ops_client.patch(url, json=dict.fromkeys(LINKS, value))
        assert response.status_code == 200, response.text
        assert all(response.json()[key] is None for key in LINKS)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(created.json()["id"]))
        )
    )
    assert any(
        "client_folder_url" in (event.after_data or {}).get("changed_fields", [])
        for event in events
    )
    assert all("https://" not in str(event.after_data) + str(event.before_data) for event in events)
    db.rollback()
    owner = client_for(
        make_user(db, email="links-owner@example.com", roles=("master_admin",)).email
    )
    response = owner.delete(url, params={"reason": "Test buyer"})
    assert response.status_code == 204, response.text
    assert owner.get(url).status_code == 404


def test_invalid_links_are_atomic(
    sales_ops_client: TestClient, project_id: str, buyer_id: str
) -> None:
    url = f"{sales_url(project_id)}/clients/{buyer_id}"
    for key, value in [
        ("client_folder_url", "https://drive.google.com.evil.example/folders/a"),
        ("client_folder_url", "https://example.com/folder"),
        ("odoo_opportunity_url", "javascript:alert(1)"),
        ("odoo_opportunity_url", "http://crm.example.com"),
        ("odoo_opportunity_url", "https://user:pass@example.com"),
        ("odoo_opportunity_url", "https://example.com/\npath"),
        ("odoo_opportunity_url", 123),
    ]:
        result = sales_ops_client.patch(url, json={key: value, "display_name": "Must not change"})
        assert result.status_code == 422, result.text
    assert sales_ops_client.get(url).json()["display_name"] == "Rana Haddad"


def test_links_follow_buyer_scope(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    advisor_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    buyer_id: str,
) -> None:
    url = f"{sales_url(project_id)}/clients/{buyer_id}"
    assert sales_ops_client.patch(url, json=LINKS).status_code == 200
    for actor in (admin_client, finance_client):
        read = actor.get(url)
        assert read.status_code == 200, read.text
        assert all(key not in read.json() for key in LINKS)
        assert actor.patch(url, json=LINKS).status_code == 403
    assert advisor_client.get(url).status_code == 404
    assert advisor_client.patch(url, json=LINKS).status_code == 404
    assert (
        sales_ops_client.get(f"{sales_url(str(uuid.uuid4()))}/clients/{buyer_id}").status_code
        == 404
    )


def test_buyer_and_draft_workbooks_preserve_links(
    sales_ops_client: TestClient, operational_project: str
) -> None:
    body = workbook(
        sales_ops_client,
        operational_project,
        "buyers",
        [{"display_name": "Workbook buyer", **LINKS}],
    )
    result = upload(sales_ops_client, operational_project, "buyers", body)
    assert result.status_code == 200 and result.json()["created_count"] == 1, result.text
    buyer = sales_ops_client.get(f"{sales_url(operational_project)}/clients").json()[0]
    assert all(buyer[key] == value for key, value in LINKS.items())
    book = load_workbook(io.BytesIO(body))
    sheet = book["Buyers"]
    sheet.delete_cols(6, 2)
    sheet.cell(2, 1, "Legacy workbook buyer")
    stream = io.BytesIO()
    book.save(stream)
    book.close()
    legacy = upload(sales_ops_client, operational_project, "buyers", stream.getvalue())
    assert legacy.status_code == 200 and legacy.json()["created_count"] == 1, legacy.text
    payload = {
        "Sales": [{"unit_reference": "UNIT"}],
        "Buyer": [{"display_name": "Draft buyer", **LINKS}],
    }
    parsed = import_draft_workbook.parse(
        import_draft_workbook.template(operational_project, [("A", payload)]), operational_project
    )
    normalized = import_draft_workbook.validate_payload(parsed[0][2])
    assert all(normalized["Buyer"][0][key] == value for key, value in LINKS.items())
    assert (
        ClientCreateRequest.model_validate(normalized["Buyer"][0]).client_folder_url
        == LINKS["client_folder_url"]
    )


def test_migration_retention(sales_ops_client: TestClient, project_id: str, buyer_id: str) -> None:
    config = alembic_config()
    url = f"{sales_url(project_id)}/clients/{buyer_id}"
    assert sales_ops_client.patch(url, json=LINKS).status_code == 200
    with pytest.raises(RuntimeError, match="Client links exist"):
        command.downgrade(config, "0063_plan_sources")
    assert sales_ops_client.get(url).json()["client_folder_url"] == LINKS["client_folder_url"]
    assert sales_ops_client.patch(url, json=dict.fromkeys(LINKS)).status_code == 200
    command.downgrade(config, "0063_plan_sources")
    command.upgrade(config, "head")
    command.check(config)
