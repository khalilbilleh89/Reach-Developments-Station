"""Architect evidence and unit charters share Reports, not contractor certification."""

import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.consultant_engineering.models import ProjectSiteReport
from app.modules.inventory.models import Unit
from tests.factories import client_for, make_user
from tests.modules.conftest import inventory_url, unit_payload
from tests.modules.test_consultant_engineering_reports import pdf, root, upload
from tests.test_migrations import _alembic_config


def link(client: TestClient, project_id: str, **fields: object) -> Response:
    return client.post(
        root(project_id) + "/links",
        json={
            "title": "Architect completion",
            "source_url": "https://drive.google.com/file/d/synthetic/view",
            **fields,
        },
    )


def test_certificate_building_and_multiple_units(
    manager_member_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    building_id: str,
    floor_id: str,
    unit_id: str,
    db: Session,
) -> None:
    client = manager_member_client
    second = admin_client.post(
        inventory_url(project_id) + "/units",
        json=unit_payload(floor_id, unit_number="102", unit_reference="B1-102"),
    ).json()["id"]
    targets = client.get(root(project_id) + "/targets")
    assert targets.status_code == 200
    assert {u["id"] for u in targets.json()["units"]} == {unit_id, second}
    building = link(client, project_id, kind="architect_certificate", building_id=building_id)
    assert building.status_code == 201, building.text
    assert building.json()["building_label"] == "B1 — Building 1"
    response = client.post(
        root(project_id),
        params={
            "title": "Unit completion",
            "kind": "architect_certificate",
            "unit_ids": [unit_id, second],
            "filename": "certificate.pdf",
        },
        content=pdf(),
    )
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["report_date"] is None
    assert set(row["unit_ids"]) == {unit_id, second}
    assert row["unit_labels"] == ["B1-101", "B1-102"]
    assert client.get(root(project_id)).json() == []
    assert len(client.get(root(project_id), params={"kind": "architect_certificate"}).json()) == 2
    url = root(project_id) + "/" + row["id"]
    assert client.get(url + "/preview").json()["page_count"] == 2
    assert client.get(url + "/document").content.startswith(b"%PDF-")
    # Metadata updates do not authorize a transition to another section.
    fields = {
        k: row[k] for k in ("title", "kind", "report_date", "notes", "building_id", "unit_ids")
    }
    changed = client.put(url, json={**fields, "title": "Corrected name", "expected_version": 1})
    assert changed.status_code == 200 and changed.json()["version"] == 2
    assert client.put(url, json={**fields, "expected_version": 1}).status_code == 409
    assert (
        client.put(
            url,
            json={**fields, "kind": "client_charter", "unit_ids": [unit_id], "expected_version": 2},
        ).status_code
        == 422
    )
    assert (
        client.post(
            url + "/delete", json={"reason": "Superseded", "expected_version": 2}
        ).status_code
        == 204
    )
    assert client.get(url + "/preview").status_code == 404
    db.rollback()
    retained = db.get(ProjectSiteReport, uuid.UUID(row["id"]))
    assert retained.is_deleted and len(retained.units) == 2 and retained.document
    event = db.scalar(
        select(AuditEvent).where(AuditEvent.entity_id == retained.id, AuditEvent.action == "delete")
    )
    assert event.after_data["kind"] == "architect_certificate"
    assert set(event.after_data["unit_ids"]) == {unit_id, second}


def test_charter_requires_one_project_unit_and_retains_removed_assignment(
    manager_member_client: TestClient, project_id: str, unit_id: str, building_id: str, db: Session
) -> None:
    client = manager_member_client
    for fields in (
        {},
        {"building_id": building_id},
        {"unit_ids": [unit_id, unit_id]},
        {"unit_ids": [str(uuid.uuid4())]},
    ):
        assert link(client, project_id, kind="client_charter", **fields).status_code == 422
    result = link(
        client, project_id, kind="client_charter", unit_ids=[unit_id], title="Client charter"
    )
    assert result.status_code == 201, result.text
    row = result.json()
    assert row["report_date"] is None and row["unit_labels"] == ["B1-101"]
    unit = db.get(Unit, uuid.UUID(unit_id))
    before = (
        unit.delivery_status,
        unit.commercial_status,
        unit.legal_status,
        unit.collection_status,
    )
    unit.removed_at = datetime.now(UTC)
    unit.is_active = False
    db.commit()
    assert client.get(root(project_id) + "/targets").json()["units"] == []
    assert link(client, project_id, kind="client_charter", unit_ids=[unit_id]).status_code == 422
    fields = {
        k: row[k] for k in ("title", "kind", "report_date", "notes", "building_id", "unit_ids")
    }
    response = client.put(
        root(project_id) + "/" + row["id"],
        json={**fields, "title": "Corrected charter", "expected_version": 1},
    )
    assert response.status_code == 200, response.text
    db.expire_all()
    assert (
        unit.delivery_status,
        unit.commercial_status,
        unit.legal_status,
        unit.collection_status,
    ) == before
    db.rollback()
    # Both normal permanent removal and explicit purge protect Reports evidence.
    owner = client_for(
        make_user(db, email="report-owner@example.com", roles=("master_admin",)).email
    )
    unit_url = inventory_url(project_id) + "/units/" + unit_id
    assert (
        owner.delete(unit_url, params={"reason": "Test protection", "permanent": True}).status_code
        == 409
    )
    preview = owner.get(unit_url + "/purge-preview")
    assert preview.status_code == 200, preview.text
    assert preview.json()["blockers"]


def test_scopes_and_invalid_applicability(
    manager_member_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    building_id: str,
    db: Session,
) -> None:
    client = manager_member_client
    for fields in (
        {},
        {"building_id": building_id, "unit_ids": [unit_id]},
        {"building_id": str(uuid.uuid4())},
        {"unit_ids": [str(uuid.uuid4())]},
    ):
        assert link(client, project_id, kind="architect_certificate", **fields).status_code == 422
    # The same real unit/building IDs are invalid in another authorized project.
    from app.modules.projects.models import Project
    from tests.modules.conftest import project_payload

    original = db.get(Project, uuid.UUID(project_id))
    other = admin_client.post(
        "/api/v1/projects",
        json=project_payload(
            str(original.country_pack_id), str(original.base_currency_id), code="OTHER-REPORT"
        ),
    ).json()["id"]
    db.rollback()
    editor = client_for(
        make_user(
            db, email="cross-project-reports@example.com", roles=("system_admin", "project_manager")
        ).email
    )
    for fields in ({"building_id": building_id}, {"unit_ids": [unit_id]}):
        assert link(editor, other, kind="architect_certificate", **fields).status_code == 422
    assert client.get(root(str(uuid.uuid4())) + "/targets").status_code == 404
    assert (
        link(
            client, project_id, kind="site_report", report_date="2026-11-12", unit_ids=[unit_id]
        ).status_code
        == 422
    )
    assert (
        client.get(root(project_id), params={"kind": "contractor_certificate"}).status_code == 422
    )


def test_sections_migration_preserves_site_reports(
    manager_member_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    client = manager_member_client
    original = upload(client, project_id).json()
    db.rollback()
    config = _alembic_config()
    command.downgrade(config, "0070_operations_commissions")
    command.upgrade(config, "head")
    command.check(config)
    rows = client.get(root(project_id)).json()
    assert rows[0]["id"] == original["id"] and rows[0]["kind"] == "site_report"
    assert rows[0]["report_date"] == "2026-11-10" and rows[0]["unit_ids"] == []
    charter = link(client, project_id, kind="client_charter", unit_ids=[unit_id]).json()
    assert (
        client.post(
            root(project_id) + "/" + charter["id"] + "/delete",
            json={"reason": "Retain", "expected_version": 1},
        ).status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="Certificates or charters exist"):
        command.downgrade(config, "0070_operations_commissions")
    db.rollback()
    assert db.scalar(text("SELECT count(*) FROM project_report_units")) == 1
