"""One response, one reporting date.

The historical read reconstructs the receivable exactly — the receipts, the
allocations, the schedule that was governing, the disputes and the waivers. That
is not enough on its own. A March receivable returned beside a June refund, a
clearance signed in June and a follow-up written in June is *two* reporting
dates in one answer, and nothing on the response says which figure belongs to
which. A reader reconciling it has no way to tell.

So every date-sensitive field on the response obeys the same cutoff:

    was the contract cancelled *then*
    had the refund been sanctioned *then*
    had refund cash actually left *then*
    was the collection clearance given *then*
    had the follow-up been written down *then*

What this produces is a restated operational position as at the requested date —
what was true of the account then, judged by when things actually happened. It
is not a snapshot of a screen somebody looked at, and nothing here claims to be.

Every history in this file is arranged by moving lifecycle stamps with
``backdate()`` and by using the real routes for everything else. What is
simulated is the passage of time, never a figure.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    at,
    backdate,
    collection_account,
    collections_url,
    confirm_receipt,
    current_version_id,
    governing_installments,
    record_receipt,
    sales_url,
)

TODAY = date.today()


def _stamp(db: Session, table: str, row_id: str, column: str, value: object) -> None:
    """Move one non-timestamp lifecycle date that ``backdate`` does not cover."""
    db.execute(
        text(f"UPDATE {table} SET {column} = :value WHERE id = :row_id"),
        {"value": value, "row_id": row_id},
    )
    db.commit()


@pytest.fixture
def january_schedule(
    collections_client: TestClient,
    db: Session,
    project_id: str,
    collecting_sale: str,
    plan_id: str,
) -> str:
    """The fixture schedule, governing since 5 January 2026."""
    del collecting_sale
    version_id = current_version_id(collections_client, project_id, plan_id)
    backdate(db, table="payment_plan_versions", row_id=version_id, activated_at=at("2026-01-05"))
    return version_id


class TestCancellationAfterTheReportingDate:
    """Given a contract cancelled in June, when March is read."""

    @pytest.fixture
    def cancelled_in_june(
        self,
        sales_ops_client: TestClient,
        cfo_client: TestClient,
        legal_client: TestClient,
        db: Session,
        project_id: str,
        collecting_sale: str,
        january_schedule: str,
    ) -> str:
        del january_schedule
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
        cancellation_id = opened.json()["id"]
        approved = cfo_client.post(
            f"{sales_url(project_id)}/cancellations/{cancellation_id}/approve-financial-terms",
            json={"reason": "Terms reviewed"},
        )
        assert approved.status_code == 200, approved.text
        del legal_client

        base = f"{sales_url(project_id)}/cancellations/{cancellation_id}"
        for to_status in ("termination_pending_approval", "ready_for_unit_return"):
            moved = sales_ops_client.post(f"{base}/advance", json={"to_status": to_status})
            assert moved.status_code == 200, moved.text
        completed = sales_ops_client.post(f"{base}/complete", json={})
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "completed"

        # Inventory refuses a commercial change dated before the unit's last
        # one, and this unit moved this morning — so the return is completed
        # today and its effective date moved afterwards. That date is the one
        # Collections reads, and moving it is the same simulation of elapsed
        # time every other history in this file uses.
        _stamp(db, "sale_cancellations", cancellation_id, "unit_return_date", date(2026, 6, 15))
        return cancellation_id

    def test_march_does_not_know_about_a_june_cancellation(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cancelled_in_june: str,
    ) -> None:
        """The receivable was live in March, and the account says so."""
        del cancelled_in_june
        march = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-03-31"
        )
        assert march["derived_collection_status"] != "cancelled"
        assert all(row["status"] != "cancelled" for row in march["installments"])
        assert march["installments"], "the historical receivable must still be visible"
        assert march["outstanding_total"] != "0.00"

    def test_the_day_the_unit_came_back_is_the_boundary(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cancelled_in_june: str,
    ) -> None:
        """Not the day somebody typed it in — the day the unwind took effect."""
        del cancelled_in_june
        before = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-06-14"
        )
        assert before["derived_collection_status"] != "cancelled"

        on_the_day = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-06-15"
        )
        assert on_the_day["derived_collection_status"] == "cancelled"
        assert all(row["status"] == "cancelled" for row in on_the_day["installments"])

    def test_today_still_reads_cancelled(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cancelled_in_june: str,
    ) -> None:
        del cancelled_in_june
        now = collection_account(collections_client, project_id, collecting_sale)
        assert now["derived_collection_status"] == "cancelled"

    def test_the_register_agrees_with_the_account(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cancelled_in_june: str,
    ) -> None:
        """One derivation, so the two screens cannot disagree."""
        del cancelled_in_june
        rows = collections_client.get(
            f"{collections_url(project_id)}/receivables", params={"as_of": "2026-03-31"}
        ).json()
        row = next(r for r in rows if r["sale_id"] == collecting_sale)
        account = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-03-31"
        )
        assert row["summary"]["derived_collection_status"] == (account["derived_collection_status"])
        assert row["summary"]["derived_collection_status"] != "cancelled"


class TestRefundApprovedLater:
    """Given a refund sanctioned in June, when March is read."""

    @pytest.fixture
    def approved_in_june(
        self,
        sales_ops_client: TestClient,
        cfo_client: TestClient,
        db: Session,
        project_id: str,
        collecting_sale: str,
        january_schedule: str,
    ) -> str:
        del january_schedule
        opened = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation",
            json={
                "initiated_by_party": "buyer",
                "initiation_date": "2026-05-01",
                "reason": "Buyer withdrew",
                "refund_due_amount": "12000.00",
                "forfeiture_amount": "0.00",
            },
        )
        assert opened.status_code == 201, opened.text
        cancellation_id = opened.json()["id"]
        approved = cfo_client.post(
            f"{sales_url(project_id)}/cancellations/{cancellation_id}/approve-financial-terms",
            json={"reason": "Terms reviewed"},
        )
        assert approved.status_code == 200, approved.text
        _stamp(db, "sale_cancellations", cancellation_id, "financial_approved_at", at("2026-06-10"))
        return cancellation_id

    def test_march_carries_no_refund_liability(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        approved_in_june: str,
    ) -> None:
        del approved_in_june
        march = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-03-31"
        )
        assert march["refund_due_total"] == "0.00"
        assert march["refund_outstanding"] == "0.00"

    def test_it_appears_from_the_day_it_was_sanctioned(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        approved_in_june: str,
    ) -> None:
        del approved_in_june
        before = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-06-09"
        )
        assert before["refund_due_total"] == "0.00"

        after = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-06-10"
        )
        assert after["refund_due_total"] == "12000.00"

    def test_an_unapproved_proposal_is_not_a_debt_at_any_date(
        self,
        sales_ops_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        january_schedule: str,
    ) -> None:
        """The same rule at every cutoff, today included.

        ``refund_due_amount`` is captured when the case is opened, which is a
        proposal. Until a financial approver signs it, nothing is owed — and a
        rule that applied only to historical reads would make today the one date
        the figure meant something different.
        """
        del january_schedule
        opened = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation",
            json={
                "initiated_by_party": "buyer",
                "initiation_date": "2026-05-01",
                "reason": "Buyer withdrew",
                "refund_due_amount": "9000.00",
                "forfeiture_amount": "0.00",
            },
        )
        assert opened.status_code == 201, opened.text
        assert opened.json()["financial_approved_at"] is None

        now = collection_account(collections_client, project_id, collecting_sale)
        assert now["refund_due_total"] == "0.00"


class TestRefundCashOut:
    """Given refund cash, when a date either side of it is read."""

    @pytest.fixture
    def refunded(
        self,
        sales_ops_client: TestClient,
        cfo_client: TestClient,
        collections_client: TestClient,
        finance_client: TestClient,
        db: Session,
        project_id: str,
        collecting_sale: str,
        january_schedule: str,
    ) -> dict[str, str]:
        """12,000 sanctioned in May, 5,000 of it actually paid in July."""
        del january_schedule
        opened = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{collecting_sale}/cancellation",
            json={
                "initiated_by_party": "buyer",
                "initiation_date": "2026-05-01",
                "reason": "Buyer withdrew",
                "refund_due_amount": "12000.00",
                "forfeiture_amount": "0.00",
            },
        )
        assert opened.status_code == 201, opened.text
        cancellation_id = opened.json()["id"]
        approved = cfo_client.post(
            f"{sales_url(project_id)}/cancellations/{cancellation_id}/approve-financial-terms",
            json={"reason": "Terms reviewed"},
        )
        assert approved.status_code == 200, approved.text
        _stamp(db, "sale_cancellations", cancellation_id, "financial_approved_at", at("2026-05-10"))

        recorded = collections_client.post(
            f"{collections_url(project_id)}/sales/{collecting_sale}/refunds",
            json={
                "cancellation_id": cancellation_id,
                "amount": "5000.00",
                "refund_date": "2026-07-05",
            },
        )
        assert recorded.status_code == 201, recorded.text
        refund_id = recorded.json()["id"]
        confirmed = finance_client.post(
            f"{collections_url(project_id)}/refunds/{refund_id}/confirm", json={}
        )
        assert confirmed.status_code == 200, confirmed.text
        db.execute(
            text("UPDATE collection_refunds SET confirmed_at = :c WHERE id = :r"),
            {"c": at("2026-07-06"), "r": refund_id},
        )
        db.commit()
        return {"cancellation_id": cancellation_id, "refund_id": refund_id}

    def test_june_does_not_see_july_cash(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        refunded: dict[str, str],
    ) -> None:
        del refunded
        june = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-06-30"
        )
        assert june["refund_due_total"] == "12000.00"
        assert june["refund_confirmed_total"] == "0.00"
        assert june["refund_outstanding"] == "12000.00"

    def test_august_does(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        refunded: dict[str, str],
    ) -> None:
        del refunded
        august = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-08-31"
        )
        assert august["refund_confirmed_total"] == "5000.00"
        assert august["refund_outstanding"] == "7000.00"

    def test_a_september_reversal_does_not_rewrite_august(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        refunded: dict[str, str],
    ) -> None:
        """The money did leave in July. Getting it back later is a second fact."""
        reversed_refund = finance_client.post(
            f"{collections_url(project_id)}/refunds/{refunded['refund_id']}/reverse",
            json={"reason": "Buyer's account rejected the transfer"},
        )
        assert reversed_refund.status_code == 200, reversed_refund.text

        august = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-08-31"
        )
        assert august["refund_confirmed_total"] == "5000.00"

        now = collection_account(collections_client, project_id, collecting_sale)
        assert now["refund_confirmed_total"] == "0.00"

    def test_the_register_reports_the_same_refund_figures(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        refunded: dict[str, str],
    ) -> None:
        """Two batched queries and one per-sale pair must not disagree."""
        del refunded
        for as_of in ("2026-06-30", "2026-08-31"):
            rows = collections_client.get(
                f"{collections_url(project_id)}/receivables", params={"as_of": as_of}
            ).json()
            row = next(r for r in rows if r["sale_id"] == collecting_sale)
            account = collection_account(
                collections_client, project_id, collecting_sale, as_of=as_of
            )
            assert row["summary"]["refund_due_total"] == account["refund_due_total"], as_of
            assert row["summary"]["refund_confirmed_total"] == account["refund_confirmed_total"], (
                as_of
            )


class TestClearanceHistory:
    """Given a clearance signed in June, when May and July are read."""

    @pytest.fixture
    def cleared_in_june(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        db: Session,
        project_id: str,
        collecting_sale: str,
        january_schedule: str,
    ) -> str:
        del january_schedule
        handover = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{collecting_sale}/handover", json={}
        )
        assert handover.status_code in (200, 201), handover.text

        rows = governing_installments(collections_client, project_id, collecting_sale)
        for row in rows:
            if row["outstanding"] == "0.00":
                continue
            recorded = record_receipt(
                collections_client, project_id, collecting_sale, row["outstanding"]
            )
            assert recorded.status_code == 201, recorded.text
            receipt_id = recorded.json()["id"]
            assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
            applied = collections_client.post(
                f"{collections_url(project_id)}/receipts/{receipt_id}/allocations",
                json={
                    "installment_id": row["installment_id"],
                    "amount": row["outstanding"],
                },
            )
            assert applied.status_code == 201, applied.text

        granted = collections_client.post(
            f"{collections_url(project_id)}/sales/{collecting_sale}/collection-clearance",
            json={"evidence_reference": "LEDGER-2026-06"},
        )
        assert granted.status_code == 200, granted.text
        assert granted.json()["status"] == "cleared"
        # The Collections route answers with the position, not the row, so the
        # clearance whose stamps are about to be moved is read back by hand.
        clearance_id = str(
            db.execute(
                text(
                    "SELECT c.id FROM handover_clearances c "
                    "JOIN handover_records h ON h.id = c.handover_id "
                    "WHERE h.sale_contract_id = :s AND c.clearance_type = 'collection' "
                    "AND c.status = 'cleared'"
                ),
                {"s": collecting_sale},
            ).scalar_one()
        )
        db.execute(
            text("UPDATE handover_clearances SET created_at = :c, cleared_at = :d WHERE id = :r"),
            {"c": at("2026-06-01"), "d": at("2026-06-20"), "r": clearance_id},
        )
        db.execute(
            text("UPDATE handover_records SET created_at = :c WHERE sale_contract_id = :s"),
            {"c": at("2026-06-01"), "s": collecting_sale},
        )
        db.commit()
        return clearance_id

    def test_may_was_not_cleared(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cleared_in_june: str,
    ) -> None:
        del cleared_in_june
        may = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-05-31"
        )
        assert may["collection_clearance_status"] != "cleared"

    def test_july_was(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cleared_in_june: str,
    ) -> None:
        del cleared_in_june
        july = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-07-31"
        )
        assert july["collection_clearance_status"] == "cleared"

    def test_a_later_revocation_leaves_july_cleared(
        self,
        collections_client: TestClient,
        db: Session,
        project_id: str,
        collecting_sale: str,
        cleared_in_june: str,
    ) -> None:
        """It was cleared in July. It stopped being cleared in August.

        The revocation is dated inside the past, not merely "later": a stamp in
        the future would be a state the system has not reached yet, and reading
        it as already true is the mistake this whole patch exists to stop.
        """
        db.execute(
            text(
                "UPDATE handover_clearances SET status = 'revoked', revoked_at = :v, "
                "revocation_reason = :why WHERE id = :r"
            ),
            {"v": at("2026-08-20"), "why": "The ledger reopened", "r": cleared_in_june},
        )
        db.commit()

        july = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-07-31"
        )
        assert july["collection_clearance_status"] == "cleared"

        now = collection_account(collections_client, project_id, collecting_sale)
        assert now["collection_clearance_status"] != "cleared"


class TestNextActionHistory:
    """Given a follow-up written in June, when March is read."""

    @pytest.fixture
    def chased_in_june(
        self,
        collections_client: TestClient,
        db: Session,
        project_id: str,
        collecting_sale: str,
        january_schedule: str,
    ) -> str:
        del january_schedule
        recorded = collections_client.post(
            f"{collections_url(project_id)}/sales/{collecting_sale}/actions",
            json={
                "action_type": "call",
                "action_at": "2026-06-20",
                "notes": "Spoke to the buyer about the arrears",
                "next_action_date": "2026-07-01",
            },
        )
        assert recorded.status_code == 201, recorded.text
        action_id = recorded.json()["id"]
        db.execute(
            text("UPDATE collection_actions SET created_at = :c WHERE id = :r"),
            {"c": at("2026-06-20"), "r": action_id},
        )
        db.commit()
        return action_id

    def test_march_shows_no_follow_up_nobody_had_made_yet(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        chased_in_june: str,
    ) -> None:
        del chased_in_june
        march = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-03-31"
        )
        assert march["next_action_date"] is None

    def test_it_appears_once_it_had_been_written_down(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        chased_in_june: str,
    ) -> None:
        del chased_in_june
        june = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-06-25"
        )
        assert june["next_action_date"] == "2026-07-01"

    def test_the_register_agrees(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        chased_in_june: str,
    ) -> None:
        del chased_in_june
        rows = collections_client.get(
            f"{collections_url(project_id)}/receivables", params={"as_of": "2026-03-31"}
        ).json()
        row = next(r for r in rows if r["sale_id"] == collecting_sale)
        assert row["summary"]["next_action_date"] is None


class TestTodayIsUnchanged:
    """Given today, when the account is read. The reconstruction must not leak.

    Every rule above is written so that asked for today it collapses to the
    status filter it replaced. These check the collapse on the shapes that
    matter, because a historical read that quietly changed the operational one
    would be a far worse bug than the one being fixed.
    """

    def test_a_live_account_reads_exactly_as_before(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        rows = governing_installments(collections_client, project_id, collecting_sale)
        recorded = record_receipt(collections_client, project_id, collecting_sale, "9000.00")
        receipt_id = recorded.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
        applied = collections_client.post(
            f"{collections_url(project_id)}/receipts/{receipt_id}/allocations",
            json={"installment_id": rows[0]["installment_id"], "amount": "9000.00"},
        )
        assert applied.status_code == 201, applied.text

        omitted = collection_account(collections_client, project_id, collecting_sale)
        explicit = collection_account(
            collections_client, project_id, collecting_sale, as_of=TODAY.isoformat()
        )
        assert omitted == explicit
        assert omitted["confirmed_receipts_total"] == "9000.00"
        assert omitted["derived_collection_status"] != "cancelled"
        assert omitted["collection_clearance_status"] is None

    def test_yesterday_and_today_differ_only_where_something_happened(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        january_schedule: str,
    ) -> None:
        """Nothing happened overnight, so the two agree on everything but the date.

        The schedule has to have been governing yesterday for this to mean
        anything — otherwise the honest difference between the two reads is that
        the plan was activated this morning, which is a real event and not a
        leak.
        """
        del january_schedule
        yesterday = (TODAY - timedelta(days=1)).isoformat()
        today = collection_account(collections_client, project_id, collecting_sale)
        before = collection_account(
            collections_client, project_id, collecting_sale, as_of=yesterday
        )
        for field in (
            "confirmed_receipts_total",
            "allocated_total",
            "unapplied_cash",
            "refund_due_total",
            "refund_confirmed_total",
            "collection_clearance_status",
            "derived_collection_status",
            "installments_total",
        ):
            assert before[field] == today[field], field
