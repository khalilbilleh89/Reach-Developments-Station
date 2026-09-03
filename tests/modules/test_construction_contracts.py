"""Commitment: what the company has signed, and what that leaves it room for.

A contract is the moment a budget stops being an intention. So the properties
proved here are all about the boundary: lines that add up to the header, a
commitment that cannot exceed the authorisation behind it, a maker who is not
the checker, and a status change that moves no money.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    PROJECTS,
    construction_url,
    create_contract,
    govern_contract,
    project_payload,
    set_contract_line,
)


class TestLinesReconcileToTheHeader:
    def test_a_contract_whose_lines_do_not_add_up_cannot_be_submitted(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        """Given / When / Then: 400,000 of lines against a 1,000,000 header."""
        contract_id = create_contract(finance_client, project_id, currency_id).json()["id"]
        assert (
            set_contract_line(
                finance_client,
                project_id,
                contract_id,
                sequence=1,
                cost_code_id=cost_codes["hard"],
                original_amount_ex_tax="400000.00",
            ).status_code
            == 200
        )
        refused = finance_client.post(
            f"{construction_url(project_id)}/contracts/{contract_id}/submit", json={}
        )
        assert refused.status_code == 422, refused.text

    def test_a_contract_with_no_lines_cannot_be_submitted(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_budget: str,
    ) -> None:
        contract_id = create_contract(finance_client, project_id, currency_id).json()["id"]
        refused = finance_client.post(
            f"{construction_url(project_id)}/contracts/{contract_id}/submit", json={}
        )
        assert refused.status_code == 422, refused.text


class TestMakerIsNotChecker:
    """PR-MVP-09 foundation fix: activating a contract commits the company."""

    def test_the_person_who_submitted_a_contract_may_not_activate_it(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        contract_id = create_contract(finance_client, project_id, currency_id).json()["id"]
        assert (
            set_contract_line(
                finance_client,
                project_id,
                contract_id,
                sequence=1,
                cost_code_id=cost_codes["hard"],
                original_amount_ex_tax="1000000.00",
            ).status_code
            == 200
        )
        base = f"{construction_url(project_id)}/contracts/{contract_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        refused = finance_client.post(f"{base}/activate", json={})
        assert refused.status_code == 403, refused.text

    def test_a_second_person_may_activate_it(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        currency_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        contract_id = create_contract(finance_client, project_id, currency_id).json()["id"]
        assert (
            set_contract_line(
                finance_client,
                project_id,
                contract_id,
                sequence=1,
                cost_code_id=cost_codes["hard"],
                original_amount_ex_tax="1000000.00",
            ).status_code
            == 200
        )
        activated = govern_contract(finance_client, cfo_client, project_id, contract_id)
        assert activated.status_code == 200, activated.text
        assert activated.json()["status"] == "active"


class TestCommitmentAppearsOnlyWhenLive:
    def test_a_draft_contract_commits_nothing(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        """A negotiation is not a commitment, however detailed it is."""
        contract_id = create_contract(finance_client, project_id, currency_id).json()["id"]
        assert (
            set_contract_line(
                finance_client,
                project_id,
                contract_id,
                sequence=1,
                cost_code_id=cost_codes["hard"],
                original_amount_ex_tax="1000000.00",
            ).status_code
            == 200
        )
        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["cost_control"]["revised_commitment"] == "0.00"

    def test_a_live_contract_commits_its_value(
        self, finance_client: TestClient, project_id: str, active_contract: str
    ) -> None:
        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["cost_control"]["original_commitment"] == "1000000.00"
        assert summary["cost_control"]["revised_commitment"] == "1000000.00"

    def test_terminating_a_contract_moves_no_money(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        active_contract: str,
    ) -> None:
        """Status is a statement about a relationship, never about a balance."""
        before = finance_client.get(f"{construction_url(project_id)}/summary").json()
        terminated = cfo_client.post(
            f"{construction_url(project_id)}/contracts/{active_contract}/terminate",
            json={"reason": "Contractor entered administration"},
        )
        assert terminated.status_code == 200, terminated.text
        after = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert after["cost_control"] == before["cost_control"]
        assert after["payable"] == before["payable"]


class TestContractFile:
    def test_the_contract_file_separates_commitment_certification_and_cash(
        self, finance_client: TestClient, project_id: str, active_contract: str
    ) -> None:
        """Six truths, six fields. None of them is derived from another's basis."""
        detail = finance_client.get(
            f"{construction_url(project_id)}/contracts/{active_contract}"
        ).json()
        assert detail["original_contract_value_ex_tax"] == "1000000.00"
        assert detail["approved_variation_delta"] == "0.00"
        assert detail["revised_commitment"] == "1000000.00"
        assert detail["certified_to_date"] == "0.00"
        assert detail["confirmed_paid"] == "0.00"
        assert detail["retention_held"] == "0.00"
        assert detail["advance_outstanding"] == "0.00"

    def test_a_contract_cannot_be_read_from_another_project(
        self,
        admin_client: TestClient,
        currency_id: str,
        country_pack_id: str,
        project_id: str,
        active_contract: str,
    ) -> None:
        """Given / When / Then: the identifier is real; the project is not this one."""
        other = admin_client.post(
            PROJECTS,
            json=project_payload(
                country_pack_id,
                currency_id,
                code="OTHER-01",
                name="Another development",
            ),
        )
        assert other.status_code == 201, other.text
        other_id = other.json()["id"]

        found = admin_client.get(f"{construction_url(other_id)}/contracts/{active_contract}")
        assert found.status_code == 404, found.text
