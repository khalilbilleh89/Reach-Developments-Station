"""Historical all-project scope, current revocation and established role gates."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access
from tests.modules.test_management_reporting import ROOT, capture
from tests.modules.test_portfolio_scale import copy_project


def test_phase_hidden_and_later_partial_reader_never_receive_document(
    admin_client: TestClient, project_id: str, phase_id: str, db: Session
) -> None:
    phase = copy_project(db, uuid.UUID(project_id), "PHASE-ONLY")
    hidden = copy_project(db, uuid.UUID(project_id), "HIDDEN")
    manager = make_user(db, email="reporting-manager@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, manager)
    grant_access(admin_client, str(phase), manager)
    r = admin_client.patch(
        f"/api/v1/projects/{phase}/access/{manager.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    assert r.status_code == 200, r.text
    with client_for(manager.email) as client:
        report = capture(client)
        assert report["project_count"] == 1
        assert str(phase) not in str(report) and str(hidden) not in str(report)
        assert db.execute(
            text(
                "SELECT project_id FROM management_report_snapshot_projects WHERE snapshot_id=:sid"
            ),
            {"sid": report["id"]},
        ).scalars().all() == [uuid.UUID(project_id)]
        assert (
            client.post(
                f"{ROOT}/snapshots", json={"scope": "project", "project_id": str(phase)}
            ).status_code
            == 404
        )
        global_report = capture(admin_client)
        for suffix in ("", "/board-pack"):
            assert client.get(f"{ROOT}/snapshots/{global_report['id']}{suffix}").status_code == 404
        assert client.get(f"{ROOT}/snapshots").json()["total"] == 1


@pytest.mark.parametrize(
    "role,can_write",
    [
        ("master_admin", True),
        ("system_admin", True),
        ("project_manager", True),
        ("finance", False),
        ("approver_cfo", False),
        ("executive_viewer", False),
        ("auditor", False),
    ],
)
def test_reporting_role_matrix(
    admin_client: TestClient, project_id: str, db: Session, role: str, can_write: bool
) -> None:
    user = make_user(db, email=f"report-{role}@example.com", roles=(role,))
    if role not in ("master_admin", "system_admin"):
        grant_access(admin_client, project_id, user)
    report = capture(admin_client, project_id)
    with client_for(user.email) as client:
        assert client.get(f"{ROOT}/snapshots/{report['id']}").status_code == 200
        result = client.post(
            f"{ROOT}/snapshots", json={"scope": "project", "project_id": project_id}
        )
        assert result.status_code == (201 if can_write else 403), result.text
