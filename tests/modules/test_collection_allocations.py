"""Allocations: applying cash, and the two ceilings that stop it going wrong.

Receiving money and deciding what it settles are separate acts, and this file is
about the second. Two invariants run through all of it:

* a receipt cannot have more applied out of it than it contains, and
* an instalment cannot have more applied to it than it asks for.

The second is the one that matters most. Excess cash stays *unapplied* and
visible, rather than being pushed into an instalment where it would hide an
overpayment inside a negative balance — which is the shape in which
overpayments get discovered years later, by the buyer.

Underneath both sits the rule that makes the figures mean anything: an
allocation from a receipt Finance has not confirmed moves no balance at all.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    allocate,
    collection_account,
    collections_url,
    confirm_receipt,
    governing_installments,
    record_receipt,
)


def _rows(client: TestClient, project_id: str, sale_id: str) -> list[dict]:
    return governing_installments(client, project_id, sale_id)


class TestApplyingCash:
    """Given a confirmed receipt, when Collections applies it."""

    def test_a_full_allocation_settles_an_instalment(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        first = _rows(collections_client, project_id, collecting_sale)[0]
        response = allocate(
            collections_client, project_id, confirmed_receipt, first["installment_id"], "10000.00"
        )
        assert response.status_code == 201, response.text

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["allocated_total"] == "10000.00"
        assert account["unapplied_cash"] == "0.00"
        row = account["installments"][0]
        assert row["paid"] == "10000.00"
        assert row["outstanding"] == f"{float(first['scheduled']) - 10000.0:.2f}"

    def test_a_partial_payment_is_ordinary(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        """No special transaction type: partial is just paid < scheduled."""
        first = _rows(collections_client, project_id, collecting_sale)[0]
        assert (
            allocate(
                collections_client,
                project_id,
                confirmed_receipt,
                first["installment_id"],
                "4000.00",
            ).status_code
            == 201
        )

        row = _rows(collections_client, project_id, collecting_sale)[0]
        assert row["paid"] == "4000.00"
        expected = f"{float(first['scheduled']) - 4000.0:.2f}"
        assert row["outstanding"] == expected

        # Today the badge is ``overdue``, because delinquency is the more urgent
        # fact — and ``paid`` and ``outstanding`` are unchanged beside it, which
        # is the point of keeping the numbers next to the badge.
        assert row["status"] == "overdue"
        assert row["overdue_days"] > 0

        # Read as at a date before this schedule was ever activated, the account
        # honestly reports no governing schedule rather than back-dating today's
        # instalments into a month they did not exist in. The part payment is
        # still there in the cash figures.
        early = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-01-15"
        )
        assert early["installments"] == []
        assert early["active_payment_plan_version_id"] is None

    def test_one_receipt_splits_across_several_instalments(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        recorded = record_receipt(collections_client, project_id, collecting_sale, "30000.00")
        receipt_id = recorded.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200

        rows = _rows(collections_client, project_id, collecting_sale)
        for row, amount in zip(rows, ("10000.00", "15000.00", "5000.00"), strict=False):
            assert (
                allocate(
                    collections_client, project_id, receipt_id, row["installment_id"], amount
                ).status_code
                == 201
            )

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["allocated_total"] == "30000.00"
        assert account["unapplied_cash"] == "0.00"
        assert [r["paid"] for r in account["installments"]] == [
            "10000.00",
            "15000.00",
            "5000.00",
        ]

    def test_several_receipts_settle_one_instalment(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        first = _rows(collections_client, project_id, collecting_sale)[0]
        assert (
            allocate(
                collections_client,
                project_id,
                confirmed_receipt,
                first["installment_id"],
                "10000.00",
            ).status_code
            == 201
        )

        second = record_receipt(collections_client, project_id, collecting_sale, "5000.00")
        second_id = second.json()["id"]
        assert confirm_receipt(finance_client, project_id, second_id).status_code == 200
        assert (
            allocate(
                collections_client, project_id, second_id, first["installment_id"], "5000.00"
            ).status_code
            == 201
        )

        row = _rows(collections_client, project_id, collecting_sale)[0]
        assert row["paid"] == "15000.00"

    def test_an_allocation_must_be_positive(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        first = _rows(collections_client, project_id, collecting_sale)[0]
        assert (
            allocate(
                collections_client, project_id, confirmed_receipt, first["installment_id"], "0.00"
            ).status_code
            == 422
        )


class TestCeilings:
    """Given the two capacities, when somebody tries to exceed one."""

    def test_a_receipt_cannot_be_over_allocated(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        rows = _rows(collections_client, project_id, collecting_sale)
        assert (
            allocate(
                collections_client,
                project_id,
                confirmed_receipt,
                rows[0]["installment_id"],
                "8000.00",
            ).status_code
            == 201
        )
        too_much = allocate(
            collections_client, project_id, confirmed_receipt, rows[1]["installment_id"], "3000.00"
        )
        assert too_much.status_code == 409
        assert "2000.00 unapplied" in too_much.json()["detail"]

    def test_an_instalment_cannot_be_over_allocated_and_the_excess_stays_unapplied(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        """The 20 / 30 / 50 schedule's first instalment cannot absorb the lot."""
        rows = _rows(collections_client, project_id, collecting_sale)
        first = rows[0]
        scheduled = float(first["scheduled"])

        recorded = record_receipt(
            collections_client, project_id, collecting_sale, f"{scheduled + 5000:.2f}"
        )
        receipt_id = recorded.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200

        refused = allocate(
            collections_client,
            project_id,
            receipt_id,
            first["installment_id"],
            f"{scheduled + 5000:.2f}",
        )
        assert refused.status_code == 409
        assert "remaining" in refused.json()["detail"]

        # The most it can take is exactly what it asks for; the rest stays visible.
        assert (
            allocate(
                collections_client,
                project_id,
                receipt_id,
                first["installment_id"],
                f"{scheduled:.2f}",
            ).status_code
            == 201
        )
        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["unapplied_cash"] == "5000.00"
        assert account["installments"][0]["outstanding"] == "0.00"


class TestConfirmationGatesTheFinancialEffect:
    """Given an allocation from a receipt Finance has not accepted."""

    def test_an_allocation_on_a_recorded_receipt_moves_no_balance(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        recorded_receipt: str,
    ) -> None:
        first = _rows(collections_client, project_id, collecting_sale)[0]
        assert (
            allocate(
                collections_client,
                project_id,
                recorded_receipt,
                first["installment_id"],
                "10000.00",
            ).status_code
            == 201
        )

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["confirmed_receipts_total"] == "0.00"
        assert account["allocated_total"] == "0.00"
        assert account["installments"][0]["paid"] == "0.00"
        assert account["installments"][0]["outstanding"] == first["scheduled"]

    def test_confirming_the_receipt_activates_the_effect(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        recorded_receipt: str,
    ) -> None:
        first = _rows(collections_client, project_id, collecting_sale)[0]
        allocate(
            collections_client, project_id, recorded_receipt, first["installment_id"], "10000.00"
        )
        assert confirm_receipt(finance_client, project_id, recorded_receipt).status_code == 200

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["allocated_total"] == "10000.00"
        assert account["installments"][0]["paid"] == "10000.00"


class TestReversal:
    """Given applied cash, when the application turns out to be wrong."""

    def test_reversing_an_allocation_returns_the_amount_to_unapplied(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        rows = _rows(collections_client, project_id, collecting_sale)
        first = allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "6000.00"
        ).json()
        allocate(
            collections_client, project_id, confirmed_receipt, rows[1]["installment_id"], "4000.00"
        )

        response = collections_client.post(
            f"{collections_url(project_id)}/allocations/{first['id']}/reverse",
            json={"reason": "Applied to the wrong instalment"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "reversed"

        account = collection_account(collections_client, project_id, collecting_sale)
        # No cash was lost: the receipt is still confirmed, six thousand is
        # simply back in the pot.
        assert account["confirmed_receipts_total"] == "10000.00"
        assert account["allocated_total"] == "4000.00"
        assert account["unapplied_cash"] == "6000.00"

    def test_reversal_needs_a_reason(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        rows = _rows(collections_client, project_id, collecting_sale)
        allocation = allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "100.00"
        ).json()
        response = collections_client.post(
            f"{collections_url(project_id)}/allocations/{allocation['id']}/reverse",
            json={"reason": "  "},
        )
        assert response.status_code == 422

    def test_an_allocation_cannot_be_reversed_twice(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        rows = _rows(collections_client, project_id, collecting_sale)
        allocation = allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "100.00"
        ).json()
        url = f"{collections_url(project_id)}/allocations/{allocation['id']}/reverse"
        assert collections_client.post(url, json={"reason": "First"}).status_code == 200
        assert collections_client.post(url, json={"reason": "Again"}).status_code == 409

    def test_reversing_a_receipt_reverses_its_active_allocations(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        """Atomically, and the receivable reopens from the ledger."""
        rows = _rows(collections_client, project_id, collecting_sale)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "10000.00"
        )
        reversed_ = finance_client.post(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}/reverse",
            json={"reason": "The transfer was recalled"},
        )
        assert reversed_.status_code == 200, reversed_.text

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["confirmed_receipts_total"] == "0.00"
        assert account["allocated_total"] == "0.00"
        assert account["installments"][0]["paid"] == "0.00"
        assert account["installments"][0]["outstanding"] == rows[0]["scheduled"]

        detail = collections_client.get(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}"
        ).json()
        assert [a["status"] for a in detail["allocations"]] == ["reversed"]

    def test_cash_cannot_be_applied_from_a_reversed_receipt(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        finance_client.post(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}/reverse",
            json={"reason": "Recalled"},
        )
        rows = _rows(collections_client, project_id, collecting_sale)
        response = allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "100.00"
        )
        assert response.status_code == 409


class TestWhichScheduleCashMayReach:
    """Given several versions, when cash is applied to one of them."""

    def test_cash_may_only_be_applied_to_the_governing_version(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
        active_plan: tuple[str, str],
    ) -> None:
        """A superseded schedule's instalments are not a place to put money.

        Opening a revision leaves the active version governing, so its rows stay
        the only allocatable ones; the draft's rows answer 404 exactly as an
        instalment that does not exist would.
        """
        plan_id, _ = active_plan
        revision = collections_client.post(
            f"/api/v1/projects/{project_id}/payment-plans/{plan_id}/versions",
            json={"change_reason": "Renegotiated"},
        )
        assert revision.status_code == 201, revision.text
        draft_version = revision.json()["version"]["id"]

        draft_rows = collections_client.get(
            f"/api/v1/projects/{project_id}/payment-plans/{plan_id}/versions/{draft_version}"
        ).json()["installments"]
        assert draft_rows, "the revision copied the standing schedule"

        refused = allocate(
            collections_client, project_id, confirmed_receipt, draft_rows[0]["id"], "100.00"
        )
        assert refused.status_code == 404
        assert refused.json()["detail"] == "Instalment not found."

    def test_an_unknown_instalment_is_the_same_404(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        del collecting_sale
        response = allocate(
            collections_client,
            project_id,
            confirmed_receipt,
            "00000000-0000-0000-0000-000000000000",
            "100.00",
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Instalment not found."


class TestSuggestions:
    """Given unapplied cash, when the operator asks where it would go."""

    def test_the_suggestion_fills_the_oldest_actionable_instalment_first(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        rows = _rows(collections_client, project_id, collecting_sale)
        # Deliberately more than the first instalment can take, so the
        # suggestion has to spill into the second and the ordering is visible.
        amount = float(rows[0]["outstanding"]) + 1000.0
        recorded = record_receipt(collections_client, project_id, collecting_sale, f"{amount:.2f}")
        receipt_id = recorded.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)

        response = collections_client.get(
            f"{collections_url(project_id)}/receipts/{receipt_id}/suggested-allocations"
        )
        assert response.status_code == 200, response.text
        suggestions = response.json()
        assert [s["sequence"] for s in suggestions] == [1, 2]
        assert suggestions[0]["amount"] == rows[0]["outstanding"]
        assert suggestions[1]["amount"] == "1000.00"
        assert sum(float(s["amount"]) for s in suggestions) == amount

    def test_a_suggestion_writes_nothing(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        collections_client.get(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}/suggested-allocations"
        )
        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["allocated_total"] == "0.00"
        assert account["unapplied_cash"] == "10000.00"
