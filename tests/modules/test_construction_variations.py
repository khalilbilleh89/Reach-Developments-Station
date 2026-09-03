"""Change orders: who may sign one, and what a signed one may not undo.

Three properties. Escalation is decided on the absolute value of the change, so
a large reduction needs the same signature as a large increase. A variation
cannot take a commitment below what has already been certified, because
certification is a statement that work was done and authorised. And an approved
variation never exceeds the budget's headroom, whichever direction it runs.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.modules.conftest import SETTINGS, construction_url


def set_review_amount(admin_client: TestClient, country_pack_id: str, amount: str) -> None:
    """Configure the country pack's construction escalation threshold."""
    response = admin_client.put(
        f"{SETTINGS}/country-packs/{country_pack_id}/approval-thresholds",
        json={
            "construction_variation_review_amount": amount,
            "reason": "Construction delegation limits",
        },
    )
    assert response.status_code == 200, response.text


def open_variation(
    client: TestClient,
    project_id: str,
    contract_id: str,
    *,
    variation_number: str = "VO-001",
    description: str = "Additional basement waterproofing",
    requested_date: str = "2026-02-10",
) -> str:
    response = client.post(
        f"{construction_url(project_id)}/contracts/{contract_id}/variations",
        json={
            "variation_number": variation_number,
            "description": description,
            "requested_date": requested_date,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def set_variation_line(
    client: TestClient,
    project_id: str,
    variation_id: str,
    *,
    cost_code_id: str,
    value_delta_ex_tax: str,
    sequence: int = 1,
    description: str = "Change",
) -> None:
    response = client.put(
        f"{construction_url(project_id)}/variations/{variation_id}/lines",
        json={
            "sequence": sequence,
            "cost_code_id": cost_code_id,
            "description": description,
            "value_delta_ex_tax": value_delta_ex_tax,
        },
    )
    assert response.status_code == 200, response.text


class TestEscalationUsesTheAbsoluteValue:
    """PR-MVP-09: a million removed is as much a decision as a million added."""

    def test_a_large_increase_needs_the_approver(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        country_pack_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        set_review_amount(admin_client, country_pack_id, "100000.00")
        variation_id = open_variation(finance_client, project_id, active_contract)
        set_variation_line(
            finance_client,
            project_id,
            variation_id,
            cost_code_id=cost_codes["hard"],
            value_delta_ex_tax="250000.00",
        )
        base = f"{construction_url(project_id)}/variations/{variation_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        detail = finance_client.get(base).json()
        assert detail["requires_escalation"] is True
        assert detail["review_amount"] == "100000.00"

        refused = second_finance_client.post(f"{base}/approve", json={})
        assert refused.status_code == 403, refused.text

    def test_a_large_reduction_needs_the_same_approver(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        country_pack_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        """Given / When / Then: -250,000 escalates exactly as +250,000 does."""
        set_review_amount(admin_client, country_pack_id, "100000.00")
        variation_id = open_variation(
            finance_client, project_id, active_contract, variation_number="VO-CUT"
        )
        set_variation_line(
            finance_client,
            project_id,
            variation_id,
            cost_code_id=cost_codes["hard"],
            value_delta_ex_tax="-250000.00",
        )
        base = f"{construction_url(project_id)}/variations/{variation_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        detail = finance_client.get(base).json()
        assert detail["total_value_ex_tax"] == "-250000.00"
        assert detail["requires_escalation"] is True

        refused = second_finance_client.post(f"{base}/approve", json={})
        assert refused.status_code == 403, refused.text

    def test_a_change_below_the_threshold_takes_a_second_finance_signature(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        country_pack_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        set_review_amount(admin_client, country_pack_id, "500000.00")
        variation_id = open_variation(finance_client, project_id, active_contract)
        set_variation_line(
            finance_client,
            project_id,
            variation_id,
            cost_code_id=cost_codes["hard"],
            value_delta_ex_tax="50000.00",
        )
        base = f"{construction_url(project_id)}/variations/{variation_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        approved = second_finance_client.post(f"{base}/approve", json={})
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"


class TestReductionFloors:
    """PR-MVP-09 foundation fix: a variation may reduce, but not into fiction."""

    def test_a_variation_cannot_take_a_commitment_below_certified_work(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """200,000 is certified; removing 900,000 would unauthorise history."""
        variation_id = open_variation(
            finance_client, project_id, active_contract, variation_number="VO-DEEP"
        )
        set_variation_line(
            finance_client,
            project_id,
            variation_id,
            cost_code_id=cost_codes["hard"],
            value_delta_ex_tax="-900000.00",
        )
        base = f"{construction_url(project_id)}/variations/{variation_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        refused = cfo_client.post(f"{base}/approve", json={})
        assert refused.status_code == 409, refused.text
        assert "HRD-01" in refused.json()["detail"]

    def test_a_reduction_down_to_certified_work_is_allowed(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """The floor is exactly the certified figure, not a margin above it."""
        variation_id = open_variation(
            finance_client, project_id, active_contract, variation_number="VO-FLOOR"
        )
        set_variation_line(
            finance_client,
            project_id,
            variation_id,
            cost_code_id=cost_codes["hard"],
            value_delta_ex_tax="-800000.00",
        )
        base = f"{construction_url(project_id)}/variations/{variation_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        approved = cfo_client.post(f"{base}/approve", json={})
        assert approved.status_code == 200, approved.text

        contract = finance_client.get(
            f"{construction_url(project_id)}/contracts/{active_contract}"
        ).json()
        assert contract["revised_commitment"] == "200000.00"
        assert contract["certified_to_date"] == "200000.00"


class TestVariationShape:
    def test_a_line_worth_nothing_is_refused(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        variation_id = open_variation(finance_client, project_id, active_contract)
        refused = finance_client.put(
            f"{construction_url(project_id)}/variations/{variation_id}/lines",
            json={
                "sequence": 1,
                "cost_code_id": cost_codes["hard"],
                "description": "No change at all",
                "value_delta_ex_tax": "0.00",
            },
        )
        assert refused.status_code == 422, refused.text

    def test_a_variation_with_no_lines_cannot_be_submitted(
        self, finance_client: TestClient, project_id: str, active_contract: str
    ) -> None:
        variation_id = open_variation(finance_client, project_id, active_contract)
        refused = finance_client.post(
            f"{construction_url(project_id)}/variations/{variation_id}/submit", json={}
        )
        assert refused.status_code == 422, refused.text

    def test_the_submitter_may_not_approve_their_own_variation(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        country_pack_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        set_review_amount(admin_client, country_pack_id, "500000.00")
        variation_id = open_variation(finance_client, project_id, active_contract)
        set_variation_line(
            finance_client,
            project_id,
            variation_id,
            cost_code_id=cost_codes["hard"],
            value_delta_ex_tax="10000.00",
        )
        base = f"{construction_url(project_id)}/variations/{variation_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        refused = finance_client.post(f"{base}/approve", json={})
        assert refused.status_code == 403, refused.text


class TestApprovedChangeMovesTheCommitment:
    def test_an_approved_variation_raises_the_revised_commitment(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        country_pack_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        """Original value never moves. Revised commitment is where change lands."""
        set_review_amount(admin_client, country_pack_id, "100000.00")
        variation_id = open_variation(finance_client, project_id, active_contract)
        set_variation_line(
            finance_client,
            project_id,
            variation_id,
            cost_code_id=cost_codes["hard"],
            value_delta_ex_tax="250000.00",
        )
        base = f"{construction_url(project_id)}/variations/{variation_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={}).status_code == 200

        contract = finance_client.get(
            f"{construction_url(project_id)}/contracts/{active_contract}"
        ).json()
        assert contract["original_contract_value_ex_tax"] == "1000000.00"
        assert contract["approved_variation_delta"] == "250000.00"
        assert contract["revised_commitment"] == "1250000.00"

    def test_a_submitted_variation_moves_nothing(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        country_pack_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        set_review_amount(admin_client, country_pack_id, "100000.00")
        variation_id = open_variation(finance_client, project_id, active_contract)
        set_variation_line(
            finance_client,
            project_id,
            variation_id,
            cost_code_id=cost_codes["hard"],
            value_delta_ex_tax="250000.00",
        )
        assert (
            finance_client.post(
                f"{construction_url(project_id)}/variations/{variation_id}/submit", json={}
            ).status_code
            == 200
        )
        contract = finance_client.get(
            f"{construction_url(project_id)}/contracts/{active_contract}"
        ).json()
        assert contract["revised_commitment"] == "1000000.00"
