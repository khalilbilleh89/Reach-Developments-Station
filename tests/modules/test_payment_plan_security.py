"""Who may see a schedule, who may write one, and what a hidden phase answers.

The disclosure this file exists to prevent: confirming that a phase somebody
was never granted contains a particular contract. A hidden plan answers exactly
as a plan that does not exist — 404, never 403.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.access.models import User
from tests.factories import client_for, make_user
from tests.modules.conftest import (
    current_version_id,
    fixed_row,
    grant_access,
    plans_url,
    write_schedule,
)

READERS = ("project_manager", "finance", "approver_cfo", "legal", "auditor", "executive_viewer")


def _member(db: Session, admin_client: TestClient, project_id: str, role: str) -> TestClient:
    user = make_user(db, email=f"{role}-reader@example.com", roles=(role,))
    grant_access(admin_client, project_id, user)
    return client_for(user.email)


def test_every_stakeholder_role_may_read_the_register(
    db: Session, admin_client: TestClient, project_id: str, plan_id: str
) -> None:
    for role in READERS:
        client = _member(db, admin_client, project_id, role)
        response = client.get(plans_url(project_id))
        assert response.status_code == 200, f"{role}: {response.text}"
        assert response.json()["total"] >= 1


def test_design_engineering_cannot_open_the_payment_plans_workspace(
    engineer_member: User, project_id: str, plan_id: str
) -> None:
    """Their work ends at the unit; a receivable schedule is not theirs."""
    client = client_for(engineer_member.email)
    refused = client.get(plans_url(project_id))
    assert refused.status_code == 403


def test_only_collections_may_open_a_plan(
    db: Session, admin_client: TestClient, project_id: str, active_sale: str
) -> None:
    for role in ("project_manager", "finance", "approver_cfo", "sales_operations", "legal"):
        client = _member(db, admin_client, project_id, role)
        refused = client.post(
            plans_url(project_id),
            json={"sale_contract_id": active_sale, "name": "Not mine to write"},
        )
        assert refused.status_code == 403, f"{role} was allowed to create a plan"


def test_only_collections_may_replace_a_draft_schedule(
    db: Session,
    admin_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    for role in ("finance", "approver_cfo", "sales_operations", "system_admin"):
        client = _member(db, admin_client, project_id, role)
        refused = write_schedule(
            client, project_id, plan_id, version_id, [fixed_row(1, "1.000000", "2026-03-01")]
        )
        assert refused.status_code == 403, f"{role} was allowed to write a schedule"


def test_finance_reads_the_full_schedule_but_does_not_sanction_it(
    db: Session,
    admin_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
) -> None:
    plan_id, version_id = reconciled_plan
    collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/submit", json={}
    )
    finance = _member(db, admin_client, project_id, "finance")
    readable = finance.get(f"{plans_url(project_id)}/{plan_id}")
    assert readable.status_code == 200
    assert readable.json()["current"]["reconciliation"]["is_reconciled"] is True
    refused = finance.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/approve",
        json={"reason": "Finance says yes"},
    )
    assert refused.status_code == 403


def test_a_plan_on_a_hidden_phase_is_invisible_and_answers_404(
    db: Session,
    admin_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    phase_id: str,
    plan_id: str,
) -> None:
    """404 and not 403: a 403 would confirm the identifier names a real plan.

    The outsider is a member of the project restricted to a phase that holds no
    units, so the sold unit's phase is hidden from them. The plan must not
    appear in their register and its identifier must answer as if it were never
    created.
    """
    other_phase = admin_client.post(
        f"/api/v1/projects/{project_id}/inventory/phases",
        json={"code": "PHASE-Z", "name": "Empty phase"},
    )
    assert other_phase.status_code == 201, other_phase.text

    outsider = make_user(db, email="phase-outsider@example.com", roles=("collections",))
    grant_access(admin_client, project_id, outsider)
    scoped = admin_client.patch(
        f"/api/v1/projects/{project_id}/access/{outsider.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    assert scoped.status_code == 200, scoped.text
    restricted = admin_client.put(
        f"/api/v1/projects/{project_id}/access/{outsider.id}/phases/{other_phase.json()['id']}"
    )
    assert restricted.status_code == 200, restricted.text

    client = client_for(outsider.email)
    register = client.get(plans_url(project_id))
    assert register.status_code == 200
    assert register.json()["total"] == 0

    hidden = client.get(f"{plans_url(project_id)}/{plan_id}")
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "Payment plan not found."

    # The same plan is plainly visible to somebody granted the whole project.
    assert collections_client.get(f"{plans_url(project_id)}/{plan_id}").status_code == 200


def test_an_unknown_plan_identifier_is_not_found(
    collections_client: TestClient, project_id: str
) -> None:
    response = collections_client.get(f"{plans_url(project_id)}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment plan not found."


def test_a_sale_from_another_project_cannot_be_scheduled(
    collections_client: TestClient,
    admin_client: TestClient,
    db: Session,
    project_id: str,
    active_sale: str,
    collections_officer: User,
) -> None:
    other = admin_client.post(
        "/api/v1/projects",
        json={
            "code": "OTHER-PRJ",
            "name": "Other development",
            "developer_entity": "Reach",
            "country_pack_id": admin_client.get("/api/v1/settings/country-packs").json()[0]["id"],
            "base_currency_id": admin_client.get("/api/v1/settings/currencies").json()[0]["id"],
            "reporting_currency_id": admin_client.get("/api/v1/settings/currencies").json()[0][
                "id"
            ],
        },
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]
    grant_access(admin_client, other_id, collections_officer)
    refused = collections_client.post(
        plans_url(other_id),
        json={"sale_contract_id": active_sale, "name": "Wrong project"},
    )
    assert refused.status_code == 404


def test_a_plan_screen_never_carries_buyer_identity_documents(
    db: Session, admin_client: TestClient, project_id: str, plan_id: str
) -> None:
    """A payment schedule needs a name, not a passport number."""
    for role in ("collections", "finance", "approver_cfo", "auditor"):
        client = _member(db, admin_client, project_id, role)
        body = client.get(f"{plans_url(project_id)}/{plan_id}").json()
        serialised = str(body)
        assert "identity_document_number" not in serialised
        assert "tax_id" not in serialised
        assert "passport" not in serialised.lower()


def test_an_unauthenticated_caller_is_refused(project_id: str, plan_id: str) -> None:
    from tests.factories import anonymous_client

    response = anonymous_client().get(plans_url(project_id))
    assert response.status_code == 401
