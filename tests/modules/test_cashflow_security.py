"""Who may see the project's cash, and who may move it.

Four separations, and each one is a specific failure.

The reading list is short. Being able to see a unit, a contract or a receipt is
not a reason to see the development's funding position — a Sales Advisor who
could read the peak deficit would know exactly how badly the company needs their
next deal to close.

The System Administrator reads and signs nothing. Administering the software
that stores the cash position is not authority over the cash.

Cash moves only when a second person says it did, compared by identifier.

And a phase-scoped reader is **refused** a project total rather than shown a
filtered one. This is the rule cash makes most tempting to break: there is no
per-phase bank account, so any per-phase figure would be invented.
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
    cashflow_url,
    cover_cashflow_construction,
    create_cashflow_forecast,
    grant_access,
    project_payload,
    record_development,
    record_financing,
)

#: Every whole-project cash surface. A phase-scoped reader gets none of them.
PROJECT_TOTALS = (
    "/summary",
    "/monthly",
    "/reconciliation",
    "/drilldown",
    "/management",
    "/forecasts",
    "/development-movements",
    "/financing-movements",
    "/restrictions",
)


@pytest.fixture
def scoped_reader(db: Session, admin_client: TestClient, project_id: str, phase_id: str) -> User:
    """A Finance user granted one phase rather than the whole project."""
    user = make_user(db, email="scoped.cash@example.com", roles=("finance",))
    grant_access(admin_client, project_id, user)
    # Membership alone sees every phase. Narrowing is a second, explicit act,
    # and without it this fixture would build a full-access reader.
    narrowed = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{user.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    assert narrowed.status_code == 200, narrowed.text
    granted = admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}/phases/{phase_id}")
    assert granted.status_code in {200, 201}, granted.text
    return user


class TestTheReadingList:
    @pytest.mark.parametrize("role", ["sales_advisor", "sales_operations", "legal", "collections"])
    def test_a_commercial_role_may_not_read_the_cash_position(
        self,
        db: Session,
        admin_client: TestClient,
        project_id: str,
        flat_construction_forecast: str,
        role: str,
    ) -> None:
        """Collections is the interesting exclusion: it keeps its own surfaces.

        What it does not get here is the development cost side, the financing
        arrangements and the funding gap, none of which is needed to chase a
        buyer and all of which is a wider disclosure than the job.
        """
        user = make_user(db, email=f"{role}@cash.example", roles=(role,))
        grant_access(admin_client, project_id, user)
        refused = client_for(user.email).get(f"{cashflow_url(project_id)}/summary")
        assert refused.status_code == 403, refused.text

    @pytest.mark.parametrize(
        "role",
        [
            "system_admin",
            "project_manager",
            "finance",
            "approver_cfo",
            "executive_viewer",
            "auditor",
        ],
    )
    def test_a_finance_or_oversight_role_may_read_the_cash_position(
        self,
        db: Session,
        admin_client: TestClient,
        project_id: str,
        flat_construction_forecast: str,
        role: str,
    ) -> None:
        user = make_user(db, email=f"{role}@reader.cash", roles=(role,))
        grant_access(admin_client, project_id, user)
        allowed = client_for(user.email).get(f"{cashflow_url(project_id)}/summary")
        assert allowed.status_code == 200, allowed.text


class TestTheAdministratorSignsNothing:
    def test_an_administrator_reads_everything_and_records_nothing(
        self,
        admin_client: TestClient,
        project_id: str,
        currency_id: str,
        flat_construction_forecast: str,
    ) -> None:
        assert admin_client.get(f"{cashflow_url(project_id)}/summary").status_code == 200
        refused = record_development(admin_client, project_id, currency_id)
        assert refused.status_code == 403, refused.text

    def test_an_administrator_may_not_confirm_cash(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        flat_construction_forecast: str,
    ) -> None:
        """The person who can reach the database does not say money left the bank."""
        movement = record_development(finance_client, project_id, currency_id)
        refused = admin_client.post(
            f"{cashflow_url(project_id)}/development-movements/{movement.json()['id']}/confirm",
            json={},
        )
        assert refused.status_code == 403, refused.text

    def test_an_administrator_may_not_approve_a_forecast(
        self,
        admin_client: TestClient,
        project_id: str,
        flat_construction_forecast: str,
    ) -> None:
        refused = create_cashflow_forecast(admin_client, project_id)
        assert refused.status_code == 403, refused.text


class TestWhoDoesWhat:
    def test_a_project_manager_prepares_but_does_not_approve(
        self,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        flat_construction_forecast: str,
    ) -> None:
        """The monthly shape of build spend is a delivery judgement first."""
        created = create_cashflow_forecast(manager_member_client, project_id)
        assert created.status_code == 201, created.text
        version_id = created.json()["id"]
        cover_cashflow_construction(manager_member_client, project_id, version_id, cost_codes)
        submitted = manager_member_client.post(
            f"{cashflow_url(project_id)}/forecasts/{version_id}/submit", json={}
        )
        assert submitted.status_code == 200, submitted.text
        refused = manager_member_client.post(
            f"{cashflow_url(project_id)}/forecasts/{version_id}/approve",
            json={"reason": "Looks right to me"},
        )
        assert refused.status_code == 403, refused.text

    def test_only_finance_records_cash_this_module_owns(
        self,
        manager_member_client: TestClient,
        project_id: str,
        currency_id: str,
        flat_construction_forecast: str,
    ) -> None:
        refused = record_financing(manager_member_client, project_id, currency_id)
        assert refused.status_code == 403, refused.text

    def test_an_executive_reads_and_writes_nothing(
        self,
        executive_client: TestClient,
        project_id: str,
        currency_id: str,
        flat_construction_forecast: str,
    ) -> None:
        assert executive_client.get(f"{cashflow_url(project_id)}/summary").status_code == 200
        refused = record_development(executive_client, project_id, currency_id)
        assert refused.status_code == 403, refused.text

    def test_an_auditor_reads_and_writes_nothing(
        self,
        auditor_client: TestClient,
        project_id: str,
        currency_id: str,
        flat_construction_forecast: str,
    ) -> None:
        assert auditor_client.get(f"{cashflow_url(project_id)}/summary").status_code == 200
        refused = record_financing(auditor_client, project_id, currency_id)
        assert refused.status_code == 403, refused.text


class TestAPartialViewIsRefusedNotFiltered:
    def test_a_phase_scoped_reader_is_refused_every_project_total(
        self,
        scoped_reader: User,
        project_id: str,
        flat_construction_forecast: str,
    ) -> None:
        """There is no per-phase bank account, so there is no honest subset."""
        client = client_for(scoped_reader.email)
        for path in PROJECT_TOTALS:
            refused = client.get(f"{cashflow_url(project_id)}{path}")
            assert refused.status_code == 403, f"{path}: {refused.text}"

    def test_the_refusal_says_why(
        self, scoped_reader: User, project_id: str, flat_construction_forecast: str
    ) -> None:
        """A 403 with no reason invites somebody to build the filtered view."""
        client = client_for(scoped_reader.email)
        refused = client.get(f"{cashflow_url(project_id)}/summary")
        assert "whole-project" in refused.json()["detail"]

    def test_a_phase_scoped_reader_may_not_record_cash_either(
        self,
        scoped_reader: User,
        project_id: str,
        currency_id: str,
        flat_construction_forecast: str,
    ) -> None:
        client = client_for(scoped_reader.email)
        refused = record_development(client, project_id, currency_id)
        assert refused.status_code == 403, refused.text


class TestAnotherProjectAnswersAsAbsent:
    def test_a_forecast_of_another_project_is_not_found(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        country_pack_id: str,
        currency_id: str,
        flat_construction_forecast: str,
    ) -> None:
        """A 403 would confirm the identifier names something real."""
        created = create_cashflow_forecast(finance_client, project_id)
        assert created.status_code == 201, created.text
        version_id = created.json()["id"]

        other = admin_client.post(
            PROJECTS,
            json=project_payload(
                country_pack_id, currency_id, code="OTHER-10", name="Second development"
            ),
        )
        assert other.status_code == 201, other.text
        answer = admin_client.get(f"{cashflow_url(other.json()['id'])}/forecasts/{version_id}")
        assert answer.status_code == 404, answer.text

    def test_an_identifier_of_nothing_answers_the_same_way(
        self, finance_client: TestClient, project_id: str, flat_construction_forecast: str
    ) -> None:
        missing = finance_client.get(f"{cashflow_url(project_id)}/forecasts/{uuid.uuid4()}")
        assert missing.status_code == 404, missing.text

    def test_a_non_member_sees_no_project_at_all(
        self, db: Session, project_id: str, flat_construction_forecast: str
    ) -> None:
        outsider = make_user(db, email="outsider@cash.example", roles=("finance",))
        answer = client_for(outsider.email).get(f"{cashflow_url(project_id)}/summary")
        assert answer.status_code == 404, answer.text


class TestNothingIsDeletable:
    def test_cashflow_exposes_no_delete_route(self) -> None:
        """A confirmed movement is a record of a decision, reversed and never removed."""
        from app.main import create_app

        paths = create_app().openapi()["paths"]
        deletes = [
            path for path, methods in paths.items() if "/cashflow" in path and "delete" in methods
        ]
        assert deletes == []
