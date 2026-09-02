"""Who may see a margin, who may decide one, and who may see neither.

Cost and margin are the most sensitive numbers this platform holds. A buyer
negotiates the price in the open; the developer's margin on it is not part of
that conversation, and an advisor who can see both has an argument for a
discount the company never agreed to make available.

So this file proves three things. The reading list is genuinely shorter than
sales' — being able to see a unit is not a reason to see what it earns. The
maker never signs their own cost basis. And the System Administrator, who can
reach the database, can approve nothing that is in it.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.access.models import User
from tests.factories import client_for, make_user
from tests.modules.conftest import (
    PROJECTS,
    cover_required_pools,
    create_version,
    economics_url,
    govern,
    grant_access,
)

AUDIT = "/api/v1/audit-events"


def version_url(project_id: str, version_id: str) -> str:
    return f"{economics_url(project_id)}/allocation-versions/{version_id}"


@pytest.fixture
def governed_basis_for_security(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    priced_pair: tuple[str, str],
) -> str:
    """One active cost basis, so every read below has something to refuse or return."""
    del priced_pair
    version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
    cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
    assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200
    return version_id


class TestWhoMaySeeAMargin:
    """Given each role, when the economics of a project are requested."""

    def test_finance_the_cfo_the_manager_the_executive_and_the_auditor_may_read(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        manager_client: TestClient,
        manager: User,
        executive_client: TestClient,
        auditor_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis_for_security: str,
    ) -> None:
        del priced_pair, governed_basis_for_security
        # The manager fixture is not a project member by default; every other
        # client here is granted by its own fixture.
        grant_access(admin_client, project_id, manager)
        for client in (
            finance_client,
            cfo_client,
            manager_client,
            executive_client,
            auditor_client,
            admin_client,
        ):
            response = client.get(f"{economics_url(project_id)}/summary")
            assert response.status_code == 200, response.text

    def test_a_sales_advisor_may_not_see_cost_or_margin(
        self,
        advisor_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis_for_security: str,
    ) -> None:
        """They can see the unit and the price. That is not a reason to see the margin."""
        first, _second = priced_pair
        del governed_basis_for_security
        for path in ("/summary", "/units", f"/units/{first}", "/allocation-versions"):
            response = advisor_client.get(f"{economics_url(project_id)}{path}")
            assert response.status_code == 403, f"{path}: {response.text}"

    def test_sales_operations_collections_and_legal_may_not_either(
        self,
        sales_ops_client: TestClient,
        collections_client: TestClient,
        legal_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis_for_security: str,
    ) -> None:
        del priced_pair, governed_basis_for_security
        for client in (sales_ops_client, collections_client, legal_client):
            assert client.get(f"{economics_url(project_id)}/summary").status_code == 403


class TestWhoMayWrite:
    """Given each role, when a cost basis or a unit cost is written."""

    def test_only_finance_may_open_a_cost_basis(
        self,
        cfo_client: TestClient,
        executive_client: TestClient,
        auditor_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        operational_project: str,
    ) -> None:
        del operational_project
        body = {
            "effective_from": "2026-01-01",
            "change_reason": "Trying it on",
            "finance_treatment": "excluded",
        }
        for client in (cfo_client, executive_client, auditor_client, admin_client):
            response = client.post(f"{economics_url(project_id)}/allocation-versions", json=body)
            assert response.status_code == 403, response.text

    def test_an_auditor_reads_everything_and_writes_nothing(
        self,
        auditor_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis_for_security: str,
    ) -> None:
        """Both halves matter, and the read half is the one easily lost.

        Audit exists to examine the numbers, so the register must answer them —
        a 403 here would defeat the role. What audit must never do is change
        one, because an auditor who can record a cost is auditing their own
        work.
        """
        first, _second = priced_pair
        del governed_basis_for_security
        assert auditor_client.get(f"{economics_url(project_id)}/units").status_code == 200
        response = auditor_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "finishes",
                "basis": "forecast",
                "amount": "100.00",
                "effective_date": "2026-04-01",
            },
        )
        assert response.status_code == 403

    def test_the_system_administrator_may_not_approve_a_cost_basis(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """Administering the software that stores the margin is not authority over it."""
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        response = admin_client.post(f"{base}/approve", json={"reason": "Looks fine"})
        assert response.status_code == 403
        assert admin_client.post(f"{base}/reject", json={"reason": "No"}).status_code == 403

    def test_the_system_administrator_may_not_activate_one_either(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Checked"}).status_code == 200
        assert admin_client.post(f"{base}/activate", json={}).status_code == 403


class TestPhaseScoping:
    """Given a caller granted one phase, when they read another phase's economics."""

    def test_a_hidden_unit_answers_as_a_unit_that_does_not_exist(
        self,
        db: Session,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis_for_security: str,
    ) -> None:
        """404, never 403. A 403 confirms the identifier names something real."""
        del governed_basis_for_security
        first, _second = priced_pair
        scoped = make_user(db, email="scoped-finance@example.com", roles=("finance",))
        grant_access(admin_client, project_id, scoped)
        narrowed = admin_client.patch(
            f"{PROJECTS}/{project_id}/access/{scoped.id}/phase-scope",
            json={"phase_scope": "selected"},
        )
        assert narrowed.status_code == 200, narrowed.text

        client = client_for(scoped.email)
        assert client.get(f"{economics_url(project_id)}/units/{first}").status_code == 404
        assert client.get(f"{economics_url(project_id)}/units").json() == []
        assert client.get(f"{economics_url(project_id)}/summary").json()["unit_count"] == 0

    def test_a_unit_of_another_project_is_not_found(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis_for_security: str,
    ) -> None:
        del priced_pair, governed_basis_for_security
        response = finance_client.get(f"{economics_url(project_id)}/units/{uuid.uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Unit not found."

    def test_a_version_of_another_project_is_not_found(
        self, finance_client: TestClient, project_id: str, operational_project: str
    ) -> None:
        del operational_project
        response = finance_client.get(version_url(project_id, str(uuid.uuid4())))
        assert response.status_code == 404
        assert response.json()["detail"] == "Allocation version not found."

    def test_the_allocations_of_a_version_that_does_not_exist_are_not_an_empty_list(
        self, finance_client: TestClient, project_id: str
    ) -> None:
        """An unknown version is 404, not 200 with nothing in it.

        A caller cannot act on those two answers the same way: one means the
        basis has not been calculated yet, the other means they asked the wrong
        project. Returning an empty list for both invites a reader to conclude
        the version allocates nothing.
        """
        response = finance_client.get(f"{version_url(project_id, str(uuid.uuid4()))}/allocations")
        assert response.status_code == 404
        assert response.json()["detail"] == "Allocation version not found."


class TestAudit:
    """Given a governed basis, when the audit trail is read."""

    def test_every_step_of_the_lifecycle_is_recorded(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        events = admin_client.get(AUDIT, params={"entity_id": version_id, "limit": 50})
        assert events.status_code == 200, events.text
        actions = {row["action"] for row in events.json()["items"]}
        assert {
            "unit_economics.version_created",
            "unit_economics.version_calculated",
            "unit_economics.version_submitted",
            "unit_economics.version_approved",
            "unit_economics.version_activated",
        } <= actions

    def test_a_unit_cost_and_its_reversal_are_both_recorded(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis_for_security: str,
    ) -> None:
        del governed_basis_for_security
        first, _second = priced_pair
        created = finance_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "finishes",
                "basis": "forecast",
                "amount": "1200.00",
                "effective_date": "2026-04-01",
            },
        )
        assert created.status_code == 201, created.text
        cost_id = created.json()["id"]
        assert (
            finance_client.post(
                f"{economics_url(project_id)}/unit-costs/{cost_id}/reverse",
                json={"reason": "Wrong unit"},
            ).status_code
            == 200
        )
        events = admin_client.get(AUDIT, params={"entity_id": cost_id, "limit": 20}).json()["items"]
        actions = {row["action"] for row in events}
        assert actions == {
            "unit_economics.unit_cost_recorded",
            "unit_economics.unit_cost_reversed",
        }
