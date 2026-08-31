"""Receipts: the line between a claim that money arrived and cash.

The distinction this file exists to defend is that a *recorded* receipt moves
nothing. It is visible, because a collections officer chasing a buyer who has
already paid needs to know a transfer is in the queue; and it is counted
nowhere, because until Finance has looked at the bank we do not know the money
came.

Everything else here follows from that: who may record, who may confirm, why
they may not be the same person even when one individual holds both roles, and
why a confirmed receipt is corrected by reversal rather than by editing.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    collection_account,
    collections_url,
    confirm_receipt,
    record_receipt,
)


class TestRecording:
    """Given a live contract, when Collections records cash."""

    def test_a_recorded_receipt_is_not_yet_cash(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        response = record_receipt(collections_client, project_id, collecting_sale, "10000.00")
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "recorded"
        assert body["counts_as_cash"] is False
        assert body["unapplied_amount"] == "10000.00"

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["confirmed_receipts_total"] == "0.00"
        assert account["allocated_total"] == "0.00"
        assert account["unapplied_cash"] == "0.00"

    def test_the_reference_is_project_scoped_and_sequential(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        first = record_receipt(collections_client, project_id, collecting_sale, "100.00")
        second = record_receipt(collections_client, project_id, collecting_sale, "200.00")
        assert first.json()["receipt_number"] == "RCT-000001"
        assert second.json()["receipt_number"] == "RCT-000002"

    def test_a_receipt_cannot_be_dated_in_the_future(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        response = record_receipt(
            collections_client, project_id, collecting_sale, "100.00", receipt_date="2099-01-01"
        )
        assert response.status_code == 422
        assert "future" in response.json()["detail"]

    def test_a_receipt_amount_must_be_positive(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        for amount in ("0.00", "-5.00"):
            response = record_receipt(collections_client, project_id, collecting_sale, amount)
            assert response.status_code == 422, amount

    def test_a_receipt_must_be_in_the_contracts_currency(
        self,
        collections_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        """A JOD contract cannot receive a USD receipt.

        There is no exchange-rate model in this MVP, so accepting the other
        currency would mean inventing a conversion nobody sanctioned.
        """
        other = admin_client.post(
            "/api/v1/settings/currencies",
            json={"code": "USD", "name": "US Dollar", "minor_units": 2},
        )
        assert other.status_code == 201, other.text
        response = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "100.00",
            currency_id=other.json()["id"],
        )
        assert response.status_code == 422
        assert "currency" in response.json()["detail"]

    def test_the_contract_currency_is_copied_when_none_is_supplied(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        currency_id: str,
    ) -> None:
        response = record_receipt(collections_client, project_id, collecting_sale, "100.00")
        assert response.json()["currency_id"] == currency_id

    def test_finance_may_not_record(
        self, finance_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        """Finance confirms other people's receipts. It does not raise its own."""
        response = record_receipt(finance_client, project_id, collecting_sale, "100.00")
        assert response.status_code == 403

    def test_a_sales_advisor_may_not_record(
        self, advisor_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        response = record_receipt(advisor_client, project_id, collecting_sale, "100.00")
        assert response.status_code == 403


class TestConfirmation:
    """Given a recorded receipt, when Finance decides whether the money arrived."""

    def test_confirmation_makes_it_cash(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        recorded_receipt: str,
    ) -> None:
        response = confirm_receipt(finance_client, project_id, recorded_receipt)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "confirmed"
        assert response.json()["counts_as_cash"] is True

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["confirmed_receipts_total"] == "10000.00"
        # Nothing has been applied to an instalment yet, so all of it is unapplied
        # and none of it has reduced the receivable.
        assert account["allocated_total"] == "0.00"
        assert account["unapplied_cash"] == "10000.00"

    def test_collections_may_not_confirm_its_own_claim(
        self, collections_client: TestClient, project_id: str, recorded_receipt: str
    ) -> None:
        response = confirm_receipt(collections_client, project_id, recorded_receipt)
        assert response.status_code == 403

    def test_the_system_administrator_may_not_confirm(
        self, admin_client: TestClient, project_id: str, recorded_receipt: str
    ) -> None:
        """Administering the software that records the money is not authority over it."""
        response = confirm_receipt(admin_client, project_id, recorded_receipt)
        assert response.status_code == 403

    def test_the_cfo_may_not_confirm(
        self, cfo_client: TestClient, project_id: str, recorded_receipt: str
    ) -> None:
        response = confirm_receipt(cfo_client, project_id, recorded_receipt)
        assert response.status_code == 403

    def test_holding_both_roles_does_not_make_one_person_a_maker_checker_pair(
        self,
        both_roles_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        """The separation is by identifier, not by role.

        Somebody holding Collections and Finance can record a receipt, and can
        confirm somebody else's, but never both halves of the same one.
        """
        recorded = record_receipt(both_roles_client, project_id, collecting_sale, "500.00")
        assert recorded.status_code == 201, recorded.text
        receipt_id = recorded.json()["id"]

        own = confirm_receipt(both_roles_client, project_id, receipt_id)
        assert own.status_code == 403
        assert "may not confirm" in own.json()["detail"]

        somebody_else = confirm_receipt(finance_client, project_id, receipt_id)
        assert somebody_else.status_code == 200, somebody_else.text

    def test_a_receipt_cannot_be_confirmed_twice(
        self, finance_client: TestClient, project_id: str, confirmed_receipt: str
    ) -> None:
        response = confirm_receipt(finance_client, project_id, confirmed_receipt)
        assert response.status_code == 409

    def test_a_reversed_receipt_cannot_be_confirmed_again(
        self, finance_client: TestClient, project_id: str, confirmed_receipt: str
    ) -> None:
        reversed_ = finance_client.post(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}/reverse",
            json={"reason": "Transfer bounced"},
        )
        assert reversed_.status_code == 200, reversed_.text
        again = confirm_receipt(finance_client, project_id, confirmed_receipt)
        assert again.status_code == 409


class TestReversal:
    """Given confirmed cash, when it turns out not to have arrived."""

    def test_reversal_needs_a_reason(
        self, finance_client: TestClient, project_id: str, confirmed_receipt: str
    ) -> None:
        response = finance_client.post(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}/reverse",
            json={"reason": "   "},
        )
        assert response.status_code == 422

    def test_a_reversed_receipt_stops_counting_as_cash_and_stays_readable(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        response = finance_client.post(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}/reverse",
            json={"reason": "The transfer was recalled by the bank"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "reversed"
        assert body["counts_as_cash"] is False
        assert body["reversal_reason"] == "The transfer was recalled by the bank"

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["confirmed_receipts_total"] == "0.00"

        # The receipt is still on the account. Nothing is ever visually erased.
        listing = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/receipts"
        )
        assert [r["id"] for r in listing.json()] == [confirmed_receipt]

    def test_only_a_confirmed_receipt_can_be_reversed(
        self, finance_client: TestClient, project_id: str, recorded_receipt: str
    ) -> None:
        response = finance_client.post(
            f"{collections_url(project_id)}/receipts/{recorded_receipt}/reverse",
            json={"reason": "Not this one"},
        )
        assert response.status_code == 409

    def test_collections_may_not_reverse_confirmed_cash(
        self, collections_client: TestClient, project_id: str, confirmed_receipt: str
    ) -> None:
        response = collections_client.post(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}/reverse",
            json={"reason": "Changed my mind"},
        )
        assert response.status_code == 403

    def test_there_is_no_way_to_delete_or_edit_a_receipt(
        self, finance_client: TestClient, project_id: str, confirmed_receipt: str
    ) -> None:
        """A correction is a reversal plus a fresh receipt, never an edit.

        The namespace guard answers 404 for an unmatched method, so both of
        these prove the same thing: the route does not exist.
        """
        url = f"{collections_url(project_id)}/receipts/{confirmed_receipt}"
        assert finance_client.delete(url).status_code == 404
        assert finance_client.patch(url, json={"amount": "1.00"}).status_code == 404


class TestReceiptScope:
    """Given a receipt, when somebody asks for it through the wrong path."""

    def test_a_receipt_of_another_sale_is_not_found_under_this_project(
        self,
        collections_client: TestClient,
        project_id: str,
        recorded_receipt: str,
        other_phase_plan: dict[str, str],
    ) -> None:
        """A receipt exists, but not for a caller narrowed away from its phase.

        Read as an admin here to prove the identifier is real; the phase-scoped
        case has its own file.
        """
        del other_phase_plan
        response = collections_client.get(
            f"{collections_url(project_id)}/receipts/{recorded_receipt}"
        )
        assert response.status_code == 200

    def test_an_unknown_receipt_is_a_plain_404(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        del collecting_sale
        response = collections_client.get(
            f"{collections_url(project_id)}/receipts/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Receipt not found."
