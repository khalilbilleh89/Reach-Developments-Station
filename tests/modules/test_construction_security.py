"""Who may see what the build costs, and what a partial view must never become.

Four separations, and each one is a specific leak if it is missing. The reading
list is shorter than the project's because a unit's build cost is not a
salesperson's business. The System Administrator reads and signs nothing. A
phase-scoped reader is refused a project total rather than shown a filtered one.
And a record of another project answers as absent, not as forbidden.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.access.models import User
from tests.factories import client_for, make_user
from tests.modules.conftest import (
    PROJECTS,
    construction_url,
    create_budget,
    grant_access,
    project_payload,
)

#: Every whole-project financial surface. A phase-scoped reader gets none.
PROJECT_TOTALS = (
    "/summary",
    "/reconciliation",
    "/budgets",
    "/contracts",
    "/variations",
    "/certificates",
    "/invoices",
    "/payments",
    "/forecasts",
)


@pytest.fixture
def scoped_engineer(db: Session, admin_client: TestClient, project_id: str, phase_id: str) -> User:
    """A Design / Engineering user granted one phase rather than the project."""
    user = make_user(db, email="scoped@example.com", roles=("design_engineering",))
    grant_access(admin_client, project_id, user)
    # Membership alone sees every phase. Narrowing is a second, explicit act,
    # and without it this fixture would build a full-access reader and the tests
    # below would pass for the wrong reason.
    narrowed = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{user.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    assert narrowed.status_code == 200, narrowed.text
    granted = admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}/phases/{phase_id}")
    assert granted.status_code in {200, 201}, granted.text
    return user


class TestTheReadingList:
    @pytest.mark.parametrize(
        "role",
        ["sales_advisor", "sales_operations", "legal", "collections"],
    )
    def test_a_commercial_role_may_not_read_construction(
        self,
        db: Session,
        admin_client: TestClient,
        project_id: str,
        active_budget: str,
        role: str,
    ) -> None:
        """Seeing a unit is not a reason to see what building it cost."""
        user = make_user(db, email=f"{role}@construction.example", roles=(role,))
        grant_access(admin_client, project_id, user)
        client = client_for(user.email)
        refused = client.get(f"{construction_url(project_id)}/summary")
        assert refused.status_code == 403, refused.text

    @pytest.mark.parametrize(
        "role",
        ["project_manager", "design_engineering", "finance", "approver_cfo", "auditor"],
    )
    def test_a_delivery_or_finance_role_may_read_construction(
        self,
        db: Session,
        admin_client: TestClient,
        project_id: str,
        active_budget: str,
        role: str,
    ) -> None:
        user = make_user(db, email=f"{role}@reader.example", roles=(role,))
        grant_access(admin_client, project_id, user)
        client = client_for(user.email)
        allowed = client.get(f"{construction_url(project_id)}/summary")
        assert allowed.status_code == 200, allowed.text

    def test_design_engineering_reads_construction_and_not_unit_economics(
        self,
        engineer_client: TestClient,
        project_id: str,
        active_budget: str,
    ) -> None:
        """The difference between the two modules, stated as a test.

        What the build costs the developer is information the people running the
        build need. What margin a unit earns is not.
        """
        from tests.modules.conftest import economics_url

        assert engineer_client.get(f"{construction_url(project_id)}/summary").status_code == 200
        refused = engineer_client.get(f"{economics_url(project_id)}/allocation-versions")
        assert refused.status_code == 403, refused.text


class TestTheAdministratorSignsNothing:
    def test_an_administrator_reads_everything_and_approves_nothing(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        assert admin_client.get(f"{construction_url(project_id)}/summary").status_code == 200

        version_id = create_budget(
            finance_client,
            project_id,
            effective_date="2026-12-01",
            change_reason="Revision",
        ).json()["id"]
        refused = admin_client.put(
            f"{construction_url(project_id)}/budgets/{version_id}/lines",
            json={"cost_code_id": cost_codes["hard"], "approved_budget_amount": "1.00"},
        )
        assert refused.status_code == 403, refused.text


class TestAPartialViewIsRefusedNotFiltered:
    def test_a_phase_scoped_reader_is_refused_every_project_total(
        self,
        admin_client: TestClient,
        scoped_engineer: User,
        project_id: str,
        active_budget: str,
    ) -> None:
        """A filtered total is neither the project's nor the reader's own."""
        client = client_for(scoped_engineer.email)
        for path in PROJECT_TOTALS:
            refused = client.get(f"{construction_url(project_id)}{path}")
            assert refused.status_code == 403, f"{path}: {refused.text}"

    def test_a_phase_scoped_reader_keeps_the_technical_record(
        self,
        admin_client: TestClient,
        scoped_engineer: User,
        project_id: str,
        active_budget: str,
    ) -> None:
        """Milestones and cost codes genuinely belong to a phase, and stay."""
        client = client_for(scoped_engineer.email)
        assert client.get(f"{construction_url(project_id)}/milestones").status_code == 200
        assert client.get(f"{construction_url(project_id)}/cost-codes").status_code == 200


class TestAnotherProjectAnswersAsAbsent:
    def test_a_contract_of_another_project_is_not_found(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        country_pack_id: str,
        currency_id: str,
        active_contract: str,
    ) -> None:
        """A 403 would confirm the identifier names something real."""
        other = admin_client.post(
            PROJECTS,
            json=project_payload(
                country_pack_id, currency_id, code="OTHER-03", name="Second development"
            ),
        )
        assert other.status_code == 201, other.text
        other_id = other.json()["id"]

        answer = admin_client.get(f"{construction_url(other_id)}/contracts/{active_contract}")
        assert answer.status_code == 404, answer.text

    def test_a_non_member_sees_no_project_at_all(
        self, db: Session, project_id: str, active_budget: str
    ) -> None:
        outsider = make_user(db, email="outsider@example.com", roles=("finance",))
        client = client_for(outsider.email)
        answer = client.get(f"{construction_url(project_id)}/summary")
        assert answer.status_code == 404, answer.text


class TestNothingIsDeletable:
    def test_construction_exposes_no_delete_route(self) -> None:
        """Governed history is superseded, reversed or voided. Never removed."""
        from app.main import create_app

        paths = create_app().openapi()["paths"]
        deletes = [
            path
            for path, methods in paths.items()
            if "/construction" in path and "delete" in methods
        ]
        assert deletes == []
