"""Refunds: money leaving, kept separate from money arriving.

PR-MVP-05 records what a cancellation makes *due* and is careful never to call
it paid. This is the other half, and the discipline that matters is that the two
stay two.

A refund is not a negative receipt. It has its own table, so every ``SUM`` over
receipts means one thing, and "we owe them twelve thousand" and "we have paid
them five" are reported side by side rather than netted into a single figure
that answers neither question.

The cancellation's own financial approval remains the authority for how much is
owed. Finance confirming a refund says only that the money actually went out.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    collection_account,
    collections_url,
    record_receipt,
    sales_url,
)


@pytest.fixture
def cancelled_sale(
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    collecting_sale: str,
) -> tuple[str, str]:
    """A contract unwound with an approved refund due of 12,000.

    Built through the real cancellation routes so the amount due carries its own
    approval, exactly as it would in production.
    """
    opened = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation",
        json={
            "initiated_by_party": "buyer",
            "initiation_date": "2026-05-01",
            "reason": "Buyer withdrew after failing to secure finance",
            "refund_due_amount": "12000.00",
            "forfeiture_amount": "0.00",
        },
    )
    assert opened.status_code == 201, opened.text
    return collecting_sale, opened.json()["id"]


def _record_refund(
    client: TestClient,
    project_id: str,
    sale_id: str,
    cancellation_id: str,
    amount: str,
    **overrides: object,
) -> object:
    body: dict[str, object] = {
        "cancellation_id": cancellation_id,
        "amount": amount,
        "refund_date": "2026-06-01",
    }
    body.update(overrides)
    return client.post(f"{collections_url(project_id)}/sales/{sale_id}/refunds", json=body)


class TestRecordingARefund:
    """Given a cancellation with an amount due, when a repayment is recorded."""

    def test_a_refund_is_recorded_against_its_cancellation(
        self, collections_client: TestClient, project_id: str, cancelled_sale: tuple[str, str]
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        response = _record_refund(
            collections_client, project_id, sale_id, cancellation_id, "5000.00"
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "recorded"
        assert body["refund_number"] == "RFD-000001"
        assert body["cancellation_id"] == cancellation_id

    def test_a_refund_must_be_positive_and_not_future_dated(
        self, collections_client: TestClient, project_id: str, cancelled_sale: tuple[str, str]
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        assert (
            _record_refund(
                collections_client, project_id, sale_id, cancellation_id, "0.00"
            ).status_code
            == 422
        )
        future = _record_refund(
            collections_client,
            project_id,
            sale_id,
            cancellation_id,
            "100.00",
            refund_date="2099-01-01",
        )
        assert future.status_code == 422
        assert "future" in future.json()["detail"]

    def test_a_refund_must_be_in_the_contracts_currency(
        self,
        collections_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        other = admin_client.post(
            "/api/v1/settings/currencies",
            json={"code": "EUR", "name": "Euro", "minor_units": 2},
        )
        assert other.status_code == 201, other.text
        response = _record_refund(
            collections_client,
            project_id,
            sale_id,
            cancellation_id,
            "100.00",
            currency_id=other.json()["id"],
        )
        assert response.status_code == 422

    def test_a_cancellation_of_another_sale_is_not_found(
        self, collections_client: TestClient, project_id: str, cancelled_sale: tuple[str, str]
    ) -> None:
        sale_id, _ = cancelled_sale
        response = _record_refund(
            collections_client,
            project_id,
            sale_id,
            "00000000-0000-0000-0000-000000000000",
            "100.00",
        )
        assert response.status_code == 404

    def test_finance_may_not_record_a_refund(
        self, finance_client: TestClient, project_id: str, cancelled_sale: tuple[str, str]
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        assert (
            _record_refund(
                finance_client, project_id, sale_id, cancellation_id, "100.00"
            ).status_code
            == 403
        )


class TestConfirmingARefund:
    """Given a recorded refund, when Finance confirms the money left."""

    def test_confirmation_is_what_makes_it_paid(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        refund = _record_refund(
            collections_client, project_id, sale_id, cancellation_id, "5000.00"
        ).json()

        before = collection_account(collections_client, project_id, sale_id)
        assert before["refund_due_total"] == "12000.00"
        assert before["refund_confirmed_total"] == "0.00"
        assert before["refund_outstanding"] == "12000.00"

        confirmed = finance_client.post(
            f"{collections_url(project_id)}/refunds/{refund['id']}/confirm", json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        after = collection_account(collections_client, project_id, sale_id)
        assert after["refund_due_total"] == "12000.00"
        assert after["refund_confirmed_total"] == "5000.00"
        assert after["refund_outstanding"] == "7000.00"

    def test_due_and_paid_are_reported_separately_and_never_netted(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        """Three figures, because a buyer will ask about all three."""
        sale_id, cancellation_id = cancelled_sale
        refund = _record_refund(
            collections_client, project_id, sale_id, cancellation_id, "5000.00"
        ).json()
        finance_client.post(
            f"{collections_url(project_id)}/refunds/{refund['id']}/confirm", json={}
        )
        account = collection_account(collections_client, project_id, sale_id)
        assert {
            account["refund_due_total"],
            account["refund_confirmed_total"],
            account["refund_outstanding"],
        } == {"12000.00", "5000.00", "7000.00"}

    def test_several_partial_refunds_are_allowed_up_to_the_amount_due(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        for amount in ("5000.00", "4000.00", "3000.00"):
            refund = _record_refund(
                collections_client, project_id, sale_id, cancellation_id, amount
            ).json()
            confirmed = finance_client.post(
                f"{collections_url(project_id)}/refunds/{refund['id']}/confirm", json={}
            )
            assert confirmed.status_code == 200, confirmed.text

        account = collection_account(collections_client, project_id, sale_id)
        assert account["refund_confirmed_total"] == "12000.00"
        assert account["refund_outstanding"] == "0.00"

    def test_the_cumulative_total_may_not_exceed_the_amount_due(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        first = _record_refund(
            collections_client, project_id, sale_id, cancellation_id, "10000.00"
        ).json()
        finance_client.post(f"{collections_url(project_id)}/refunds/{first['id']}/confirm", json={})
        too_much = _record_refund(
            collections_client, project_id, sale_id, cancellation_id, "5000.00"
        )
        assert too_much.status_code == 409
        assert "2000.00 still due" in too_much.json()["detail"]

    def test_the_recorder_may_not_confirm_their_own_refund(
        self,
        both_roles_client: TestClient,
        project_id: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        refund = _record_refund(
            both_roles_client, project_id, sale_id, cancellation_id, "1000.00"
        ).json()
        response = both_roles_client.post(
            f"{collections_url(project_id)}/refunds/{refund['id']}/confirm", json={}
        )
        assert response.status_code == 403

    def test_the_system_administrator_may_not_confirm_a_refund(
        self,
        collections_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        refund = _record_refund(
            collections_client, project_id, sale_id, cancellation_id, "1000.00"
        ).json()
        response = admin_client.post(
            f"{collections_url(project_id)}/refunds/{refund['id']}/confirm", json={}
        )
        assert response.status_code == 403


class TestReversingARefund:
    """Given a confirmed refund, when it turns out not to have gone out."""

    def test_a_reversed_refund_stops_counting_and_frees_the_headroom(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        refund = _record_refund(
            collections_client, project_id, sale_id, cancellation_id, "12000.00"
        ).json()
        finance_client.post(
            f"{collections_url(project_id)}/refunds/{refund['id']}/confirm", json={}
        )
        reversed_ = finance_client.post(
            f"{collections_url(project_id)}/refunds/{refund['id']}/reverse",
            json={"reason": "The transfer was returned by the receiving bank"},
        )
        assert reversed_.status_code == 200, reversed_.text
        assert reversed_.json()["status"] == "reversed"

        account = collection_account(collections_client, project_id, sale_id)
        assert account["refund_confirmed_total"] == "0.00"
        assert account["refund_outstanding"] == "12000.00"

        # And the full amount can be paid again.
        again = _record_refund(collections_client, project_id, sale_id, cancellation_id, "12000.00")
        assert again.status_code == 201, again.text

    def test_only_a_confirmed_refund_can_be_reversed(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        sale_id, cancellation_id = cancelled_sale
        refund = _record_refund(
            collections_client, project_id, sale_id, cancellation_id, "100.00"
        ).json()
        response = finance_client.post(
            f"{collections_url(project_id)}/refunds/{refund['id']}/reverse",
            json={"reason": "Not this one"},
        )
        assert response.status_code == 409


class TestARefundIsNotAReceipt:
    """The distinction that keeps PR-MVP-10's cashflow honest."""

    def test_a_refund_never_appears_as_incoming_cash(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cancelled_sale: tuple[str, str],
    ) -> None:
        """Money out is its own table, never a negative row in the other one."""
        sale_id, cancellation_id = cancelled_sale
        refund = _record_refund(
            collections_client, project_id, sale_id, cancellation_id, "5000.00"
        ).json()
        finance_client.post(
            f"{collections_url(project_id)}/refunds/{refund['id']}/confirm", json={}
        )

        receipts = collections_client.get(
            f"{collections_url(project_id)}/sales/{sale_id}/receipts"
        ).json()
        assert all(float(r["amount"]) > 0 for r in receipts)
        assert refund["id"] not in [r["id"] for r in receipts]

        account = collection_account(collections_client, project_id, sale_id)
        assert account["confirmed_receipts_total"] == "0.00"

    def test_a_receipt_amount_can_never_be_negative(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        assert (
            record_receipt(collections_client, project_id, collecting_sale, "-5000.00").status_code
            == 422
        )
