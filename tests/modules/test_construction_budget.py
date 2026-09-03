"""The budget: what the company authorised itself to spend, and by whom.

Four properties, each of which has a failure behind it that reaches a board
paper. A budget nobody approved is a number somebody typed. A budget that
silently omits a cost code cannot be distinguished from one that authorises
nothing for it. A revision that restates the original baseline erases the
overrun it was meant to explain. And a budget activated under a commitment it
does not cover puts the project over its limit retrospectively, in the same
motion that hides it.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    construction_url,
    cover_budget,
    create_budget,
    create_contract,
    create_cost_code,
    govern_budget,
    govern_contract,
    set_budget_line,
    set_contract_line,
)


class TestBudgetGovernance:
    def test_a_draft_budget_authorises_nothing_until_it_is_activated(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
    ) -> None:
        """Given / When / Then: a draft carries figures and no authority."""
        created = create_budget(finance_client, project_id)
        assert created.status_code == 201, created.text
        version_id = created.json()["id"]
        cover_budget(finance_client, project_id, version_id, cost_codes)

        summary = finance_client.get(f"{construction_url(project_id)}/summary")
        assert summary.status_code == 200, summary.text
        body = summary.json()
        assert body["budget_version_number"] is None
        assert body["cost_control"]["control_budget"] == "0.00"
        assert body["controls"]["has_active_budget"] is False

        assert govern_budget(finance_client, cfo_client, project_id, version_id).status_code == 200
        after = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert after["budget_version_number"] == 1
        assert after["controls"]["has_active_budget"] is True

    def test_the_person_who_submits_a_budget_may_not_approve_it(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
    ) -> None:
        """One pair of eyes is not two, whatever roles the account holds."""
        version_id = create_budget(finance_client, project_id).json()["id"]
        cover_budget(finance_client, project_id, version_id, cost_codes)
        base = f"{construction_url(project_id)}/budgets/{version_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        refused = finance_client.post(f"{base}/approve", json={"reason": "Looks right to me"})
        assert refused.status_code == 403, refused.text

    def test_an_administrator_may_read_a_budget_and_approve_none(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
    ) -> None:
        """Reaching the database is not authority over what it says."""
        version_id = create_budget(finance_client, project_id).json()["id"]
        cover_budget(finance_client, project_id, version_id, cost_codes)
        base = f"{construction_url(project_id)}/budgets/{version_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        assert admin_client.get(base).status_code == 200
        refused = admin_client.post(f"{base}/approve", json={"reason": "Administratively fine"})
        assert refused.status_code == 403, refused.text

    def test_only_one_budget_is_ever_being_prepared(
        self, finance_client: TestClient, project_id: str, cost_codes: dict[str, str]
    ) -> None:
        """Two open drafts is two answers to "which revision are we discussing"."""
        assert create_budget(finance_client, project_id).status_code == 201
        second = create_budget(finance_client, project_id, change_reason="Another go")
        assert second.status_code == 409, second.text


class TestCostCodeCoverage:
    """PR-MVP-09 foundation fix: an omitted line is not an authorisation of zero."""

    def test_a_budget_missing_a_cost_code_cannot_be_submitted(
        self, finance_client: TestClient, project_id: str, cost_codes: dict[str, str]
    ) -> None:
        version_id = create_budget(finance_client, project_id).json()["id"]
        line = set_budget_line(
            finance_client,
            project_id,
            version_id,
            cost_code_id=cost_codes["hard"],
            approved_budget_amount="1000000.00",
        )
        assert line.status_code == 200, line.text

        refused = finance_client.post(
            f"{construction_url(project_id)}/budgets/{version_id}/submit", json={}
        )
        assert refused.status_code == 422, refused.text
        assert "SFT-01" in refused.json()["detail"]

    def test_an_explicit_zero_is_an_answer(
        self, finance_client: TestClient, project_id: str, cost_codes: dict[str, str]
    ) -> None:
        version_id = create_budget(finance_client, project_id).json()["id"]
        cover_budget(
            finance_client,
            project_id,
            version_id,
            cost_codes,
            hard="1000000.00",
            soft="0.00",
            contingency="0.00",
            other="0.00",
        )
        submitted = finance_client.post(
            f"{construction_url(project_id)}/budgets/{version_id}/submit", json={}
        )
        assert submitted.status_code == 200, submitted.text

    def test_a_retired_cost_code_does_not_force_a_line(
        self, finance_client: TestClient, project_id: str, cost_codes: dict[str, str]
    ) -> None:
        """A code nobody may spend against is not a code a budget must address."""
        extra = create_cost_code(finance_client, project_id, code="HRD-99")
        assert extra.status_code == 201, extra.text
        retired = finance_client.post(
            f"{construction_url(project_id)}/cost-codes/{extra.json()['id']}/retire",
            json={"reason": "Scope removed from the package"},
        )
        assert retired.status_code == 200, retired.text

        version_id = create_budget(finance_client, project_id).json()["id"]
        cover_budget(finance_client, project_id, version_id, cost_codes)
        submitted = finance_client.post(
            f"{construction_url(project_id)}/budgets/{version_id}/submit", json={}
        )
        assert submitted.status_code == 200, submitted.text


class TestBaselineIsNeverRestated:
    def test_a_revision_carries_the_original_baseline_forward(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
    ) -> None:
        """Given / When / Then: the first authorisation survives every revision."""
        first = create_budget(finance_client, project_id).json()["id"]
        opening = set_budget_line(
            finance_client,
            project_id,
            first,
            cost_code_id=cost_codes["hard"],
            approved_budget_amount="1000000.00",
            baseline_amount="1000000.00",
        )
        assert opening.status_code == 200, opening.text
        for category in ("soft", "contingency", "other"):
            assert (
                set_budget_line(
                    finance_client,
                    project_id,
                    first,
                    cost_code_id=cost_codes[category],
                    approved_budget_amount="0.00",
                ).status_code
                == 200
            )
        assert govern_budget(finance_client, cfo_client, project_id, first).status_code == 200

        second = create_budget(
            finance_client,
            project_id,
            effective_date=date.today().isoformat(),
            change_reason="Scope growth on the substructure",
        )
        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        restated = set_budget_line(
            finance_client,
            project_id,
            second_id,
            cost_code_id=cost_codes["hard"],
            approved_budget_amount="1250000.00",
            baseline_amount="1250000.00",
        )
        assert restated.status_code == 409, restated.text

        raised = set_budget_line(
            finance_client,
            project_id,
            second_id,
            cost_code_id=cost_codes["hard"],
            approved_budget_amount="1250000.00",
        )
        assert raised.status_code == 200, raised.text

        detail = finance_client.get(f"{construction_url(project_id)}/budgets/{second_id}").json()
        hard = next(line for line in detail["lines"] if line["cost_code"] == "HRD-01")
        assert hard["baseline_amount"] == "1000000.00"
        assert hard["approved_budget_amount"] == "1250000.00"
        assert detail["total_baseline"] == "1000000.00"


class TestEffectiveDating:
    """PR-MVP-09 foundation fix: a replacement never governs a period already lived."""

    def test_the_first_budget_may_be_backdated(
        self, finance_client: TestClient, project_id: str
    ) -> None:
        """A project may have been building for two years before this module."""
        created = create_budget(finance_client, project_id, effective_date="2024-01-01")
        assert created.status_code == 201, created.text

    def test_a_replacement_budget_may_not_be_backdated(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        active_budget: str,
    ) -> None:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        refused = create_budget(
            finance_client,
            project_id,
            effective_date=yesterday,
            change_reason="Retrospective correction",
        )
        assert refused.status_code == 422, refused.text
        assert yesterday in refused.json()["detail"]

    def test_a_replacement_budget_may_take_effect_today(
        self, finance_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        created = create_budget(
            finance_client,
            project_id,
            effective_date=date.today().isoformat(),
            change_reason="Revised package prices",
        )
        assert created.status_code == 201, created.text


class TestActivationProvesCoverage:
    def test_a_budget_that_would_leave_a_commitment_uncovered_is_refused(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        currency_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        """Revise then commit. Never commit then authorise less than you signed."""
        second = create_budget(
            finance_client,
            project_id,
            effective_date=date.today().isoformat(),
            change_reason="Cost saving exercise",
        )
        assert second.status_code == 201, second.text
        version_id = second.json()["id"]
        cut = set_budget_line(
            finance_client,
            project_id,
            version_id,
            cost_code_id=cost_codes["hard"],
            approved_budget_amount="500000.00",
        )
        assert cut.status_code == 200, cut.text

        base = f"{construction_url(project_id)}/budgets/{version_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert (
            cfo_client.post(f"{base}/approve", json={"reason": "Savings agreed"}).status_code == 200
        )
        refused = finance_client.post(f"{base}/activate", json={})
        assert refused.status_code == 409, refused.text
        assert "HRD-01" in refused.json()["detail"]


class TestHeadroomGovernsCommitment:
    def test_a_contract_beyond_the_authorisation_cannot_be_activated(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        currency_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        """The budget is a limit on commitment, not a note beside it."""
        created = create_contract(
            finance_client,
            project_id,
            currency_id,
            contract_number="CT-BIG",
            original_contract_value_ex_tax="11000000.00",
        )
        assert created.status_code == 201, created.text
        contract_id = created.json()["id"]
        line = set_contract_line(
            finance_client,
            project_id,
            contract_id,
            sequence=1,
            cost_code_id=cost_codes["hard"],
            original_amount_ex_tax="11000000.00",
        )
        assert line.status_code == 200, line.text

        refused = govern_contract(finance_client, cfo_client, project_id, contract_id)
        assert refused.status_code == 409, refused.text
