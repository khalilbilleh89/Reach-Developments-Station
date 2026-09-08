"""Focused Consultant Engineer contract tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def clean_consultant_rows(db: Session) -> Iterator[None]:
    yield
    db.execute(
        text(
            "TRUNCATE consultant_deliverables, consultant_design_stages, "
            "consultant_disciplines, consultant_engagements CASCADE"
        )
    )
    db.commit()


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/consultant-engineering"


def test_create_activate_and_deliverable_lifecycle(
    manager_member_client: TestClient, project_id: str
) -> None:
    created = manager_member_client.post(
        f"{root(project_id)}/engagements",
        json={"consultant_name": "Atelier One", "agreement_reference": "CE-01"},
    )
    assert created.status_code == 201, created.text
    engagement = created.json()
    activated = manager_member_client.post(
        f"{root(project_id)}/engagements/{engagement['id']}/activate"
    )
    assert activated.status_code == 200, activated.text
    discipline = manager_member_client.post(
        f"{root(project_id)}/engagements/{engagement['id']}/disciplines",
        json={"name": "MEP"},
    )
    assert discipline.status_code == 201, discipline.text
    duplicate = manager_member_client.post(
        f"{root(project_id)}/engagements/{engagement['id']}/disciplines",
        json={"name": "  mep  "},
    )
    assert duplicate.status_code == 409
    stage = manager_member_client.post(
        f"{root(project_id)}/engagements/{engagement['id']}/stages",
        json={"name": "Detailed design", "planned_date": "2026-04-01"},
    )
    assert stage.status_code == 201, stage.text
    deliverable = manager_member_client.post(
        f"{root(project_id)}/engagements/{engagement['id']}/deliverables",
        json={
            "stage_id": stage.json()["id"],
            "discipline_id": discipline.json()["id"],
            "name": "Coordinated drawings",
            "status": "submitted",
            "submitted_date": "2026-03-30",
            "document_reference": "DMS-MEP-001",
        },
    )
    assert deliverable.status_code == 201, deliverable.text
    workspace = manager_member_client.get(root(project_id)).json()
    assert workspace["active_engagement"]["id"] == engagement["id"]
    assert workspace["outstanding_deliverables"] == 1
    assert workspace["accepted_deliverables"] == 0


def test_second_activation_conflicts(manager_member_client: TestClient, project_id: str) -> None:
    ids = []
    for number in (1, 2):
        result = manager_member_client.post(
            f"{root(project_id)}/engagements",
            json={"consultant_name": f"Consultant {number}", "agreement_reference": f"CE-{number}"},
        )
        assert result.status_code == 201
        ids.append(result.json()["id"])
    assert (
        manager_member_client.post(f"{root(project_id)}/engagements/{ids[0]}/activate").status_code
        == 200
    )
    assert (
        manager_member_client.post(f"{root(project_id)}/engagements/{ids[1]}/activate").status_code
        == 409
    )


def test_commercial_reader_is_refused(advisor_client: TestClient, project_id: str) -> None:
    assert advisor_client.get(root(project_id)).status_code == 403
