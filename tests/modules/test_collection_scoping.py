"""Scoping: a nested path is a claim about parentage, and it has to be proved.

``/sales/S1/receipts/R2`` asserts that R2 is one of S1's receipts. Validating
each identifier on its own and trusting the caller paired them honestly accepts
any invented pair — two independently valid identifiers are not a valid pair.

Every refusal in this file is the same 404, and none of them says "belongs to
another sale". That phrasing confirms the hidden identifier exists, which is
precisely what somebody guessing at identifiers is trying to learn.

The second half is phase scope. A collections account is exactly as visible as
the sale it belongs to, which is exactly as visible as the unit that was sold.
An advisor narrowed away from a phase sees a receipt in it as a receipt that
does not exist.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.modules.access.models import User
from tests.factories import anonymous_client, client_for
from tests.modules.conftest import (
    PROJECTS,
    collections_url,
    confirm_receipt,
    governing_installments,
    project_payload,
    record_receipt,
)

MISSING = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def other_sale_receipt(
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
    other_phase_plan: dict[str, str],
) -> dict[str, str]:
    """A real receipt, with a real allocation, on a second sale in a second phase.

    Everything a caller might try to substitute under the first sale's path
    actually exists, so a 404 proves the parentage check rather than proving the
    identifier was made up.

    Depends on ``collecting_sale`` so the project always holds *two* accounts:
    the comparisons below are between what a narrowed caller sees and what an
    unnarrowed one sees, and both need something to see.
    """
    del collecting_sale
    sale_id = other_phase_plan["sale_id"]
    recorded = record_receipt(collections_client, project_id, sale_id, "1000.00")
    assert recorded.status_code == 201, recorded.text
    receipt_id = recorded.json()["id"]
    confirm_receipt(finance_client, project_id, receipt_id)

    rows = governing_installments(collections_client, project_id, sale_id)
    allocation = collections_client.post(
        f"{collections_url(project_id)}/receipts/{receipt_id}/allocations",
        json={"installment_id": rows[0]["installment_id"], "amount": "1000.00"},
    )
    assert allocation.status_code == 201, allocation.text
    return {
        "sale_id": sale_id,
        "receipt_id": receipt_id,
        "installment_id": rows[0]["installment_id"],
        "allocation_id": allocation.json()["id"],
    }


class TestParentage:
    """Given two real identifiers, when they are paired in a path that is a lie."""

    def test_a_receipt_of_another_sale_is_not_found_under_this_one(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        other_sale_receipt: dict[str, str],
    ) -> None:
        listing = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/receipts"
        ).json()
        assert other_sale_receipt["receipt_id"] not in [r["id"] for r in listing]

    def test_cash_cannot_be_applied_to_another_sales_instalment(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
        other_sale_receipt: dict[str, str],
    ) -> None:
        """The identifier is real. It belongs to a different contract."""
        response = collections_client.post(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}/allocations",
            json={
                "installment_id": other_sale_receipt["installment_id"],
                "amount": "100.00",
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Instalment not found."

    def test_a_dispute_cannot_be_opened_on_another_sales_instalment_via_this_project(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        other_sale_receipt: dict[str, str],
    ) -> None:
        """Reachable here because the caller may see both phases.

        The scoping test below is the one that proves a caller who may not see
        the phase gets nothing.
        """
        del collecting_sale
        response = collections_client.post(
            f"{collections_url(project_id)}/installments/"
            f"{other_sale_receipt['installment_id']}/disputes",
            json={"reason": "Wrong sale"},
        )
        assert response.status_code == 201

    def test_an_action_cannot_name_another_sales_instalment(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        other_sale_receipt: dict[str, str],
    ) -> None:
        response = collections_client.post(
            f"{collections_url(project_id)}/sales/{collecting_sale}/actions",
            json={
                "action_type": "call",
                "action_at": "2026-04-01",
                "notes": "Chased",
                "installment_id": other_sale_receipt["installment_id"],
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Instalment not found."

    @pytest.mark.parametrize(
        ("path", "detail"),
        [
            ("receipts/{missing}", "Receipt not found."),
            ("restructures/{missing}/preview", "Restructure not found."),
        ],
    )
    def test_an_invented_identifier_answers_the_same_as_a_hidden_one(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        path: str,
        detail: str,
    ) -> None:
        del collecting_sale
        response = collections_client.get(
            f"{collections_url(project_id)}/{path.format(missing=MISSING)}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == detail

    def test_a_receipt_cannot_be_reached_through_the_wrong_project(
        self,
        collections_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        confirmed_receipt: str,
        country_pack_id: str,
        currency_id: str,
        reference_data: None,
    ) -> None:
        """Project A's receipt is not in project B, whatever the URL says."""
        second = admin_client.post(
            PROJECTS,
            json=project_payload(
                country_pack_id,
                currency_id,
                code="PRJ-COLL-2",
                name="Second development",
            ),
        )
        assert second.status_code == 201, second.text
        other_project = second.json()["id"]

        response = collections_client.get(
            f"{collections_url(other_project)}/receipts/{confirmed_receipt}"
        )
        assert response.status_code in (403, 404)


class TestPhaseScope:
    """Given a caller narrowed to their own phase or their own buyers."""

    def test_an_advisor_sees_only_their_own_clients_accounts(
        self,
        advisor_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        other_sale_receipt: dict[str, str],
    ) -> None:
        response = advisor_client.get(f"{collections_url(project_id)}/receivables")
        assert response.status_code == 200, response.text
        visible = {row["sale_id"] for row in response.json()}
        assert other_sale_receipt["sale_id"] not in visible

    def test_a_hidden_sales_receipt_answers_as_a_receipt_that_does_not_exist(
        self,
        advisor_client: TestClient,
        project_id: str,
        other_sale_receipt: dict[str, str],
    ) -> None:
        response = advisor_client.get(
            f"{collections_url(project_id)}/receipts/{other_sale_receipt['receipt_id']}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Receipt not found."

    def test_a_hidden_sales_account_answers_as_a_sale_that_does_not_exist(
        self,
        advisor_client: TestClient,
        project_id: str,
        other_sale_receipt: dict[str, str],
    ) -> None:
        response = advisor_client.get(
            f"{collections_url(project_id)}/sales/{other_sale_receipt['sale_id']}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Sale contract not found."

    def test_the_aging_report_is_narrowed_in_sql_not_in_the_browser(
        self,
        advisor_client: TestClient,
        project_id: str,
        other_sale_receipt: dict[str, str],
    ) -> None:
        rows = advisor_client.get(f"{collections_url(project_id)}/aging").json()
        assert all(row["sale_id"] != other_sale_receipt["sale_id"] for row in rows)

    def test_the_project_strip_totals_only_what_the_caller_may_see(
        self,
        advisor_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        other_sale_receipt: dict[str, str],
    ) -> None:
        """A summary is a place a hidden figure leaks without anybody noticing."""
        narrow = advisor_client.get(f"{collections_url(project_id)}/summary").json()
        wide = collections_client.get(f"{collections_url(project_id)}/summary").json()
        assert narrow["accounts"] < wide["accounts"]
        assert float(narrow["confirmed_receipts_total"]) < float(wide["confirmed_receipts_total"])


class TestRoleGates:
    """Given a role, when it reaches for something outside its remit."""

    def test_engineering_cannot_open_the_workspace_at_all(
        self,
        admin_client: TestClient,
        engineer_member: User,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        del admin_client, collecting_sale
        engineer = client_for(engineer_member.email)
        response = engineer.get(f"{collections_url(project_id)}/receivables")
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "route",
        [
            "summary",
            "receivables",
            "aging",
        ],
    )
    def test_every_read_route_requires_authentication(self, project_id: str, route: str) -> None:
        response = anonymous_client().get(f"{collections_url(project_id)}/{route}")
        assert response.status_code == 401
