"""Disputes, waivers and chases: the operational half, and what it may not touch.

One sentence covers all three: none of them moves money.

A dispute records that the buyer contests an amount. A waiver records that the
CFO has agreed to stop chasing one for a while. An action records what somebody
did about it. The scheduled amount, the tax, the buyer fee, the contract value
and every day of aging are identical before and after each of them, and the
tests below say so explicitly rather than leaving it to be inferred.

The one thing a dispute *does* change is the badge, and even then the days
overdue and the outstanding balance stay on the row beside it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    collection_account,
    collections_url,
    governing_installments,
)


def _first(client: TestClient, project_id: str, sale_id: str) -> dict:
    return governing_installments(client, project_id, sale_id)[0]


def _open_dispute(
    client: TestClient, project_id: str, installment_id: str, reason: str = "Snagging unresolved"
) -> object:
    return client.post(
        f"{collections_url(project_id)}/installments/{installment_id}/disputes",
        json={"reason": reason},
    )


class TestDisputes:
    """Given an instalment, when the buyer contests it."""

    def test_a_dispute_changes_no_figure(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        before = collection_account(collections_client, project_id, collecting_sale)
        row = before["installments"][0]

        response = _open_dispute(collections_client, project_id, row["installment_id"])
        assert response.status_code == 201, response.text

        after = collection_account(collections_client, project_id, collecting_sale)
        assert after["scheduled_total"] == before["scheduled_total"]
        assert after["outstanding_total"] == before["outstanding_total"]
        assert after["confirmed_receipts_total"] == before["confirmed_receipts_total"]
        assert after["open_disputes"] == 1

        disputed = after["installments"][0]
        assert disputed["scheduled"] == row["scheduled"]
        assert disputed["outstanding"] == row["outstanding"]
        assert disputed["due_date"] == row["due_date"]

    def test_a_dispute_does_not_erase_aging(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        """Disputed and forty-seven days late are both true at once."""
        row = _first(collections_client, project_id, collecting_sale)
        _open_dispute(collections_client, project_id, row["installment_id"])

        account = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-04-17"
        )
        disputed = account["installments"][0]
        assert disputed["status"] == "disputed"
        assert disputed["is_disputed"] is True
        assert disputed["overdue_days"] == 47
        assert disputed["bucket"] == "31_60"
        assert disputed["outstanding"] == row["scheduled"]
        assert account["overdue_total"] == row["scheduled"]

    def test_only_one_dispute_may_be_open_on_an_instalment(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        opened = _open_dispute(collections_client, project_id, row["installment_id"])
        assert opened.status_code == 201
        second = _open_dispute(collections_client, project_id, row["installment_id"])
        assert second.status_code == 409

    def test_a_dispute_needs_a_reason(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        response = _open_dispute(collections_client, project_id, row["installment_id"], reason="")
        assert response.status_code == 422

    def test_resolving_a_dispute_reopens_the_slot_and_keeps_the_record(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        dispute = _open_dispute(collections_client, project_id, row["installment_id"]).json()

        resolved = collections_client.post(
            f"{collections_url(project_id)}/disputes/{dispute['id']}/resolve",
            json={"resolution": "Snagging completed and accepted"},
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["status"] == "resolved"

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["open_disputes"] == 0
        assert account["installments"][0]["is_disputed"] is False

        # The closed dispute is still readable.
        history = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/disputes"
        ).json()
        assert [d["status"] for d in history] == ["resolved"]

        # And a fresh one may now be raised.
        again = _open_dispute(collections_client, project_id, row["installment_id"])
        assert again.status_code == 201

    def test_a_dispute_may_be_withdrawn(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        dispute = _open_dispute(collections_client, project_id, row["installment_id"]).json()
        response = collections_client.post(
            f"{collections_url(project_id)}/disputes/{dispute['id']}/withdraw",
            json={"resolution": "Raised against the wrong instalment"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "withdrawn"

    def test_a_closed_dispute_cannot_be_closed_again(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        dispute = _open_dispute(collections_client, project_id, row["installment_id"]).json()
        url = f"{collections_url(project_id)}/disputes/{dispute['id']}/resolve"
        assert collections_client.post(url, json={"resolution": "Done"}).status_code == 200
        assert collections_client.post(url, json={"resolution": "Again"}).status_code == 409

    def test_finance_may_not_open_a_dispute(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        refused = _open_dispute(finance_client, project_id, row["installment_id"])
        assert refused.status_code == 403


class TestWaivers:
    """Given an overdue instalment, when a pause on chasing it is asked for."""

    def _submit(
        self,
        client: TestClient,
        project_id: str,
        installment_id: str,
        waived_until: str = "2099-01-01",
    ) -> object:
        return client.post(
            f"{collections_url(project_id)}/installments/{installment_id}/waivers",
            json={
                "waiver_type": "collection_hold",
                "waived_until": waived_until,
                "reason": "Buyer hospitalised; agreed pause",
            },
        )

    def test_an_approved_waiver_reduces_nothing(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        before = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-04-17"
        )
        row = before["installments"][0]

        waiver = self._submit(collections_client, project_id, row["installment_id"]).json()
        approved = cfo_client.post(
            f"{collections_url(project_id)}/waivers/{waiver['id']}/approve", json={}
        )
        assert approved.status_code == 200, approved.text

        after = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-04-17"
        )
        assert after["scheduled_total"] == before["scheduled_total"]
        assert after["outstanding_total"] == before["outstanding_total"]
        assert after["overdue_total"] == before["overdue_total"]

        held = after["installments"][0]
        assert held["has_active_waiver"] is True
        assert held["waived_until"] == "2099-01-01"
        # The obligation and the delinquency both survive the concession.
        assert held["outstanding"] == row["outstanding"]
        assert held["overdue_days"] == row["overdue_days"]
        assert after["active_waivers"] == 1

    def test_a_waiver_must_run_to_a_future_date(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        response = self._submit(
            collections_client, project_id, row["installment_id"], waived_until="2020-01-01"
        )
        assert response.status_code == 422
        assert "future" in response.json()["detail"]

    def test_collections_may_not_approve_its_own_waiver(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        waiver = self._submit(collections_client, project_id, row["installment_id"]).json()
        response = collections_client.post(
            f"{collections_url(project_id)}/waivers/{waiver['id']}/approve", json={}
        )
        assert response.status_code == 403

    def test_the_system_administrator_may_not_approve_a_waiver(
        self,
        collections_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        waiver = self._submit(collections_client, project_id, row["installment_id"]).json()
        response = admin_client.post(
            f"{collections_url(project_id)}/waivers/{waiver['id']}/approve", json={}
        )
        assert response.status_code == 403

    def test_only_one_live_waiver_per_instalment(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        first = self._submit(collections_client, project_id, row["installment_id"])
        assert first.status_code == 201
        second = self._submit(collections_client, project_id, row["installment_id"])
        assert second.status_code == 409

    def test_a_refused_waiver_is_kept_and_frees_the_slot(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        waiver = self._submit(collections_client, project_id, row["installment_id"]).json()
        rejected = cfo_client.post(
            f"{collections_url(project_id)}/waivers/{waiver['id']}/reject",
            json={"reason": "No evidence provided"},
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["rejection_reason"] == "No evidence provided"

        history = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/waivers"
        ).json()
        assert [w["status"] for w in history] == ["rejected"]
        replacement = self._submit(collections_client, project_id, row["installment_id"])
        assert replacement.status_code == 201

    def test_an_approved_waiver_can_be_withdrawn_and_is_kept(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        waiver = self._submit(collections_client, project_id, row["installment_id"]).json()
        cfo_client.post(f"{collections_url(project_id)}/waivers/{waiver['id']}/approve", json={})
        revoked = cfo_client.post(
            f"{collections_url(project_id)}/waivers/{waiver['id']}/revoke",
            json={"reason": "Buyer recovered; collection resumes"},
        )
        assert revoked.status_code == 200, revoked.text
        assert revoked.json()["status"] == "revoked"

        account = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-04-17"
        )
        assert account["installments"][0]["has_active_waiver"] is False

    def test_a_submitted_waiver_cannot_be_revoked(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        row = _first(collections_client, project_id, collecting_sale)
        waiver = self._submit(collections_client, project_id, row["installment_id"]).json()
        response = cfo_client.post(
            f"{collections_url(project_id)}/waivers/{waiver['id']}/revoke",
            json={"reason": "Too early"},
        )
        assert response.status_code == 409


class TestActions:
    """Given an account, when Collections records what it did about it."""

    def _record(
        self, client: TestClient, project_id: str, sale_id: str, **overrides: object
    ) -> object:
        body: dict[str, object] = {
            "action_type": "call",
            "action_at": "2026-04-01",
            "notes": "Spoke to the buyer; promised to pay next week",
        }
        body.update(overrides)
        return client.post(f"{collections_url(project_id)}/sales/{sale_id}/actions", json=body)

    def test_an_action_is_appended(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        response = self._record(collections_client, project_id, collecting_sale)
        assert response.status_code == 201, response.text
        assert response.json()["action_type"] == "call"

    def test_a_promise_to_pay_is_never_cash(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        """The whole point of recording it is the gap between promise and money."""
        before = collection_account(collections_client, project_id, collecting_sale)
        response = self._record(
            collections_client,
            project_id,
            collecting_sale,
            action_type="promise_to_pay",
            promised_amount="10000.00",
            promised_date="2099-01-01",
        )
        assert response.status_code == 201, response.text

        after = collection_account(collections_client, project_id, collecting_sale)
        assert after["confirmed_receipts_total"] == before["confirmed_receipts_total"] == "0.00"
        assert after["allocated_total"] == "0.00"
        assert after["outstanding_total"] == before["outstanding_total"]

    def test_a_promise_needs_the_amount_promised(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        response = self._record(
            collections_client, project_id, collecting_sale, action_type="promise_to_pay"
        )
        assert response.status_code == 422

    def test_an_action_cannot_have_happened_in_the_future(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        response = self._record(
            collections_client, project_id, collecting_sale, action_at="2099-01-01"
        )
        assert response.status_code == 422

    def test_a_planned_follow_up_may_be_in_the_future(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        """The difference between what happened and what is intended."""
        response = self._record(
            collections_client, project_id, collecting_sale, next_action_date="2099-06-01"
        )
        assert response.status_code == 201, response.text
        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["next_action_date"] == "2099-06-01"

    def test_the_history_reads_most_recent_first(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        self._record(collections_client, project_id, collecting_sale, action_at="2026-03-01")
        self._record(collections_client, project_id, collecting_sale, action_at="2026-04-01")
        history = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/actions"
        ).json()
        assert [a["action_at"] for a in history] == ["2026-04-01", "2026-03-01"]

    def test_there_is_no_update_or_delete_route(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        """A mistake is followed by another note, not by rewriting the first."""
        action = self._record(collections_client, project_id, collecting_sale).json()
        url = f"{collections_url(project_id)}/sales/{collecting_sale}/actions/{action['id']}"
        assert collections_client.patch(url, json={"notes": "changed"}).status_code == 404
        assert collections_client.delete(url).status_code == 404

    def test_finance_may_not_record_a_chase(
        self, finance_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        assert self._record(finance_client, project_id, collecting_sale).status_code == 403
