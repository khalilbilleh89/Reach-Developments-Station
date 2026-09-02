"""Aging: what is late, by how many days, and what may never make it late.

Most of this file is the pure arithmetic, tested directly, because an off-by-one
in a grace boundary is a financial reporting error and building a project, a
unit, a contract and a plan to find one is a bad trade.

Two rules dominate.

**A forecast never makes money due.** A construction milestone expected in March
and never certified is *awaiting its trigger* in December, not two hundred and
seventy days overdue. PR-MVP-06 enforces this in the database as well as the
service; here it is proved again at the point where somebody would actually see
the wrong number.

**Grace is part of the date.** An amount is overdue when the as-of date is
strictly past ``due + grace``, so the boundary day itself is not late. Every
edge of every bucket is stated rather than assumed.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.collections import ledger
from tests.modules.conftest import (
    allocate,
    at,
    backdate,
    collection_account,
    collections_url,
    confirm_receipt,
    current_version_id,
    fixed_row,
    plans_url,
    record_receipt,
    write_schedule,
)

FIVE_K = Decimal("5000.00")
ZERO = Decimal("0.00")


def _view(**overrides: object) -> ledger.InstallmentView:
    """One dated instalment of 5,000, unpaid, with everything else defaulted."""
    kwargs: dict[str, object] = {
        "installment_id": uuid.uuid4(),
        "sequence": 1,
        "label": "Instalment 1",
        "trigger_type": "fixed_date",
        "trigger_status": "scheduled",
        "date_based": True,
        "contractual_due_date": date(2026, 6, 1),
        "actual_due_date": date(2026, 6, 1),
        "triggered": False,
        "grace_days": 0,
        "principal": FIVE_K,
        "tax": ZERO,
        "fee": ZERO,
        "paid": ZERO,
        "as_of": date(2026, 6, 1),
        "disputed": False,
        "waived_until": None,
        "owner_user_id": None,
        "sale_cancelled": False,
    }
    kwargs.update(overrides)
    return ledger.installment_view(**kwargs)  # type: ignore[arg-type]


class TestTheScheduledAmount:
    """Given the three components, when the buyer total is worked out."""

    def test_the_total_is_principal_plus_tax_plus_fee(self) -> None:
        assert ledger.scheduled_amount(
            Decimal("20000.00"), Decimal("3200.00"), Decimal("150.00")
        ) == Decimal("23350.00")

    def test_the_view_uses_the_same_definition(self) -> None:
        view = _view(principal=Decimal("20000.00"), tax=Decimal("3200.00"), fee=Decimal("150.00"))
        assert view.scheduled == Decimal("23350.00")
        assert view.outstanding == Decimal("23350.00")


class TestTheDueDate:
    """Given a trigger, when the system decides whether money is due."""

    def test_a_dated_instalment_is_due_on_its_contractual_date(self) -> None:
        assert _view().due_date == date(2026, 6, 1)

    def test_a_contingent_instalment_awaiting_its_trigger_has_no_due_date(self) -> None:
        view = _view(
            trigger_type="construction_milestone",
            date_based=False,
            contractual_due_date=None,
            actual_due_date=None,
            triggered=False,
            trigger_status="awaiting_trigger",
        )
        assert view.due_date is None
        assert view.status == ledger.INSTALLMENT_AWAITING
        assert view.bucket == ledger.BUCKET_AWAITING

    def test_a_forecast_three_months_past_creates_no_aging_at_all(self) -> None:
        """The control this whole module is built around.

        ``forecast_due_date`` is not even a parameter of the calculation: there
        is no branch that could read it, which is stronger than a branch that
        chooses not to.
        """
        view = _view(
            trigger_type="construction_milestone",
            date_based=False,
            contractual_due_date=None,
            actual_due_date=None,
            triggered=False,
            trigger_status="awaiting_trigger",
            as_of=date(2026, 12, 31),
        )
        assert view.overdue_days == 0
        assert view.overdue_amount == ZERO
        assert view.status == ledger.INSTALLMENT_AWAITING

    def test_a_triggered_contingent_instalment_is_due_on_the_date_it_happened(self) -> None:
        view = _view(
            trigger_type="handover",
            date_based=False,
            contractual_due_date=None,
            actual_due_date=date(2026, 7, 15),
            triggered=True,
            trigger_status="triggered",
            as_of=date(2026, 7, 20),
        )
        assert view.due_date == date(2026, 7, 15)
        assert view.overdue_days == 5


class TestTheGraceBoundary:
    """Given a due date and a grace period, when the clock is read."""

    @pytest.mark.parametrize(
        ("as_of", "expected"),
        [
            (date(2026, 5, 31), 0),  # before the due date
            (date(2026, 6, 1), 0),  # the due date itself
            (date(2026, 6, 2), 1),  # first day late
            (date(2026, 7, 1), 30),
            (date(2026, 7, 2), 31),
            (date(2026, 7, 31), 60),
            (date(2026, 8, 1), 61),
            (date(2026, 8, 30), 90),
            (date(2026, 8, 31), 91),
        ],
    )
    def test_days_overdue_counts_from_the_day_after_the_boundary(
        self, as_of: date, expected: int
    ) -> None:
        assert _view(as_of=as_of).overdue_days == expected

    @pytest.mark.parametrize(
        ("as_of", "expected"),
        [
            (date(2026, 6, 8), 0),  # inside a seven-day grace
            (date(2026, 6, 9), 1),  # the day after grace ends
        ],
    )
    def test_grace_moves_the_boundary_and_nothing_else(self, as_of: date, expected: int) -> None:
        assert _view(grace_days=7, as_of=as_of).overdue_days == expected

    def test_a_settled_instalment_is_never_overdue_however_old(self) -> None:
        view = _view(paid=FIVE_K, as_of=date(2030, 1, 1))
        assert view.overdue_days == 0
        assert view.status == ledger.INSTALLMENT_PAID
        assert view.bucket == ledger.BUCKET_CURRENT

    def test_a_part_paid_instalment_ages_on_what_is_left(self) -> None:
        view = _view(paid=Decimal("2000.00"), as_of=date(2026, 7, 2))
        assert view.outstanding == Decimal("3000.00")
        assert view.overdue_days == 31
        assert view.overdue_amount == Decimal("3000.00")


class TestBuckets:
    """Given a number of days overdue, when the report bands it."""

    @pytest.mark.parametrize(
        ("as_of", "bucket"),
        [
            (date(2026, 6, 1), ledger.BUCKET_CURRENT),
            (date(2026, 6, 2), ledger.BUCKET_1_30),
            (date(2026, 7, 1), ledger.BUCKET_1_30),
            (date(2026, 7, 2), ledger.BUCKET_31_60),
            (date(2026, 7, 31), ledger.BUCKET_31_60),
            (date(2026, 8, 1), ledger.BUCKET_61_90),
            (date(2026, 8, 30), ledger.BUCKET_61_90),
            (date(2026, 8, 31), ledger.BUCKET_91_PLUS),
        ],
    )
    def test_each_band_starts_exactly_where_the_last_one_ends(
        self, as_of: date, bucket: str
    ) -> None:
        assert _view(as_of=as_of).bucket == bucket


class TestStatusKeepsTheFacts:
    """Given several things true at once, when one label has to be chosen."""

    def test_a_disputed_overdue_instalment_still_reports_its_days_and_balance(self) -> None:
        view = _view(disputed=True, as_of=date(2026, 7, 18))
        assert view.status == ledger.INSTALLMENT_DISPUTED
        assert view.is_disputed is True
        assert view.overdue_days == 47
        assert view.outstanding == FIVE_K
        assert view.bucket == ledger.BUCKET_31_60

    def test_a_waiver_is_a_flag_and_never_a_reduction(self) -> None:
        view = _view(waived_until=date(2026, 9, 1), as_of=date(2026, 7, 2))
        assert view.has_active_waiver is True
        assert view.waived_until == date(2026, 9, 1)
        # The concession is about chasing. The money is still owed and still late.
        assert view.outstanding == FIVE_K
        assert view.overdue_days == 31

    def test_an_expired_waiver_stops_being_active(self) -> None:
        view = _view(waived_until=date(2026, 6, 1), as_of=date(2026, 7, 1))
        assert view.has_active_waiver is False
        assert view.waived_until is None

    def test_a_cancelled_sale_marks_every_row_cancelled(self) -> None:
        assert _view(sale_cancelled=True).status == ledger.INSTALLMENT_CANCELLED

    def test_a_future_instalment_is_scheduled_not_due(self) -> None:
        assert _view(as_of=date(2026, 1, 1)).status == ledger.INSTALLMENT_SCHEDULED

    def test_an_instalment_reaching_its_date_is_due(self) -> None:
        assert _view(as_of=date(2026, 6, 1)).status == ledger.INSTALLMENT_DUE


class TestAsOfIsReal:
    """Given the ledger, when somebody asks what it looked like on a past date.

    Nothing is snapshotted, so the answer has to be reconstructed — and the
    reconstruction has to cover the *cash* as well as the arithmetic. Aging a
    March schedule against the receipts confirmed in June is worse than
    refusing the question, because the answer looks authoritative and is wrong
    by however much arrived in between.

    Every row Collections owns records when it changed state, so these tests
    arrange a real history with :func:`backdate` and then read it through the
    ordinary route.
    """

    def test_the_aging_report_answers_for_a_supplied_date(
        self,
        collections_client: TestClient,
        project_id: str,
        historical_schedule: str,
    ) -> None:
        """The fixture schedule falls due on 1 March, 1 June and 1 September."""
        del historical_schedule
        before = collections_client.get(
            f"{collections_url(project_id)}/aging", params={"as_of": "2026-02-01"}
        )
        assert before.status_code == 200, before.text
        assert all(row["installment"]["overdue_days"] == 0 for row in before.json())

        after = collections_client.get(
            f"{collections_url(project_id)}/aging", params={"as_of": "2026-03-15"}
        )
        assert after.status_code == 200
        overdue = [row for row in after.json() if row["installment"]["overdue_days"] > 0]
        assert len(overdue) == 1
        assert overdue[0]["installment"]["overdue_days"] == 14
        assert overdue[0]["installment"]["bucket"] == "1_30"

    def test_the_same_date_asked_twice_gives_the_same_answer(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        del collecting_sale
        params = {"as_of": "2026-06-15"}
        first = collections_client.get(f"{collections_url(project_id)}/aging", params=params)
        second = collections_client.get(f"{collections_url(project_id)}/aging", params=params)
        assert first.json() == second.json()

    def test_overdue_only_narrows_the_report_without_changing_the_figures(
        self,
        collections_client: TestClient,
        project_id: str,
        historical_schedule: str,
    ) -> None:
        del historical_schedule
        params = {"as_of": "2026-06-15", "overdue_only": True}
        rows = collections_client.get(f"{collections_url(project_id)}/aging", params=params).json()
        assert rows
        assert all(row["installment"]["overdue_days"] > 0 for row in rows)

    def test_the_account_ages_on_the_supplied_date_too(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        historical_schedule: str,
    ) -> None:
        del historical_schedule
        account = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-03-15"
        )
        assert account["as_of"] == "2026-03-15"
        assert account["oldest_overdue_days"] == 14
        assert account["installments_overdue"] == 1
        assert account["overdue_total"] == account["installments"][0]["scheduled"]

    def test_a_schedule_activated_later_does_not_govern_an_earlier_date(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        """The plan really was activated today, so January had no schedule.

        Back-dating today's instalments into a month they did not exist in
        would invent a demand the buyer was never given.
        """
        account = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-01-15"
        )
        assert account["installments"] == []
        assert account["active_payment_plan_version_id"] is None
        assert account["outstanding_total"] == "0.00"


class TestHistoricalCash:
    """Given a receipt, when the account is read for a date before it arrived."""

    @pytest.fixture
    def settled_in_june(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        db: Session,
        project_id: str,
        collecting_sale: str,
        plan_id: str,
    ) -> dict[str, str]:
        """January schedule, first instalment settled by cash confirmed in June."""
        version_id = current_version_id(collections_client, project_id, plan_id)
        backdate(
            db,
            table="payment_plan_versions",
            row_id=version_id,
            activated_at=at("2026-01-05"),
        )
        rows = collection_account(collections_client, project_id, collecting_sale)["installments"]
        first = rows[0]
        recorded = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            first["scheduled"],
            receipt_date="2026-06-02",
        )
        assert recorded.status_code == 201, recorded.text
        receipt_id = recorded.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
        allocation = allocate(
            collections_client,
            project_id,
            receipt_id,
            first["installment_id"],
            first["scheduled"],
        )
        assert allocation.status_code == 201, allocation.text
        allocation_id = allocation.json()["id"]

        backdate(
            db,
            table="collection_receipts",
            row_id=receipt_id,
            confirmed_at=at("2026-06-03"),
        )
        backdate(
            db,
            table="collection_receipt_allocations",
            row_id=allocation_id,
            created_at=at("2026-06-03"),
        )
        return {
            "receipt_id": receipt_id,
            "allocation_id": allocation_id,
            "installment_id": first["installment_id"],
            "scheduled": first["scheduled"],
        }

    def test_a_june_receipt_does_not_reduce_the_march_balance(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        settled_in_june: dict[str, str],
    ) -> None:
        """The March position is what was true in March, not what we know now."""
        march = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-03-15"
        )
        assert march["confirmed_receipts_total"] == "0.00"
        assert march["allocated_total"] == "0.00"
        assert march["installments"][0]["paid"] == "0.00"
        assert march["installments"][0]["outstanding"] == settled_in_june["scheduled"]
        assert march["installments"][0]["overdue_days"] == 14

    def test_the_receipt_appears_from_the_date_it_was_confirmed(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        settled_in_june: dict[str, str],
    ) -> None:
        """Before its effective point it is absent; after it, it is counted."""
        just_before = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-06-02"
        )
        assert just_before["confirmed_receipts_total"] == "0.00"

        just_after = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-06-03"
        )
        assert just_after["confirmed_receipts_total"] == settled_in_june["scheduled"]
        assert just_after["allocated_total"] == settled_in_june["scheduled"]
        assert just_after["installments"][0]["status"] == "paid"

    def test_a_later_reversal_does_not_rewrite_the_earlier_position(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        settled_in_june: dict[str, str],
    ) -> None:
        """Reversing today says nothing about what was true in June.

        This is the difference between a ledger and a mutable balance. The
        instalment was settled in June; it is outstanding again now; both are
        facts and the account reports whichever one was asked for.
        """
        reversal = finance_client.post(
            f"{collections_url(project_id)}/receipts/{settled_in_june['receipt_id']}/reverse",
            json={"reason": "Bank returned the transfer"},
        )
        assert reversal.status_code == 200, reversal.text

        june = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-06-30"
        )
        assert june["confirmed_receipts_total"] == settled_in_june["scheduled"]
        assert june["installments"][0]["status"] == "paid"

        now = collection_account(collections_client, project_id, collecting_sale)
        assert now["confirmed_receipts_total"] == "0.00"
        assert now["installments"][0]["outstanding"] == settled_in_june["scheduled"]

    def test_a_future_as_of_is_refused(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        """Collections reports what happened. PR-MVP-10 owns what is expected."""
        ahead = (date.today() + timedelta(days=1)).isoformat()
        for path, params in (
            (f"{collections_url(project_id)}/sales/{collecting_sale}", {"as_of": ahead}),
            (f"{collections_url(project_id)}/aging", {"as_of": ahead}),
            (f"{collections_url(project_id)}/summary", {"as_of": ahead}),
            (f"{collections_url(project_id)}/receivables", {"as_of": ahead}),
        ):
            response = collections_client.get(path, params=params)
            assert response.status_code == 422, (path, response.status_code, response.text)
            assert "latest date" in response.text

    def test_today_is_still_allowed(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        response = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}",
            params={"as_of": date.today().isoformat()},
        )
        assert response.status_code == 200, response.text


class TestDueNow:
    """Given a schedule, when the workspace asks what is payable today.

    ``Due now`` is the number an operator acts on: it is what they will chase
    this morning. So it has to mean *the buyer has been asked for this and has
    not paid it*, and nothing else.

    Three things it must not be. It is not the whole schedule — an instalment
    falling due in three months is a commitment, and counting it turns plan
    activation into an invoice for the full contract value. It is not reduced
    by grace — a payment inside its grace period has been asked for, it is
    simply not yet late. And it is not the scheduled amount once something has
    been paid against it; only the remainder is still being asked for.
    """

    def _rows(self, client: TestClient, project_id: str, sale_id: str) -> tuple[dict, list[dict]]:
        account = collection_account(client, project_id, sale_id)
        return account, account["installments"]

    def test_a_future_instalment_is_not_due_now(
        self,
        collections_client: TestClient,
        project_id: str,
        active_sale: str,
        relative_plan: dict,
    ) -> None:
        del relative_plan
        account, rows = self._rows(collections_client, project_id, active_sale)
        ahead = rows[2]
        assert ahead["due_date"] > date.today().isoformat()
        assert ahead["status"] == "scheduled"
        assert ahead["outstanding"] == ahead["scheduled"]
        # The one row that has not been asked for is the one excluded.
        expected = Decimal(rows[0]["outstanding"]) + Decimal(rows[1]["outstanding"])
        assert Decimal(account["due_total"]) == expected
        assert Decimal(account["outstanding_total"]) == expected + Decimal(ahead["outstanding"])

    def test_an_instalment_due_today_is_due_now(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        active_sale: str,
        plan_id: str,
    ) -> None:
        """The boundary day itself counts. Due means due."""
        version_id = current_version_id(collections_client, project_id, plan_id)
        today = date.today()
        written = write_schedule(
            collections_client,
            project_id,
            plan_id,
            version_id,
            [
                fixed_row(1, "1.000000", today.isoformat()),
            ],
        )
        assert written.status_code == 200, written.text
        base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
        assert collections_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Agreed"}).status_code == 200
        assert cfo_client.post(f"{base}/activate", json={}).status_code == 200

        account, rows = self._rows(collections_client, project_id, active_sale)
        assert rows[0]["due_date"] == today.isoformat()
        assert rows[0]["status"] == "due"
        assert account["due_total"] == rows[0]["outstanding"]

    def test_inside_grace_is_due_but_not_overdue(
        self,
        collections_client: TestClient,
        project_id: str,
        active_sale: str,
        relative_plan: dict,
    ) -> None:
        """Grace moves the overdue line, never the due line.

        The buyer has been asked for this money. They are simply not yet late
        with it, which is a statement about chasing, not about owing.
        """
        del relative_plan
        _, rows = self._rows(collections_client, project_id, active_sale)
        in_grace = rows[1]
        assert in_grace["due_date"] < date.today().isoformat()
        assert in_grace["overdue_days"] == 0
        assert in_grace["bucket"] == "current"
        assert in_grace["status"] == "due"

    def test_beyond_grace_is_due_and_overdue(
        self,
        collections_client: TestClient,
        project_id: str,
        active_sale: str,
        relative_plan: dict,
    ) -> None:
        del relative_plan
        account, rows = self._rows(collections_client, project_id, active_sale)
        late = rows[0]
        assert late["overdue_days"] > 0
        assert late["status"] == "overdue"
        assert Decimal(account["overdue_total"]) == Decimal(late["outstanding"])
        # Overdue is a subset of due, never a separate pile beside it.
        assert Decimal(account["due_total"]) >= Decimal(account["overdue_total"])

    def test_only_the_remainder_of_a_part_paid_instalment_is_due(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        active_sale: str,
        relative_plan: dict,
    ) -> None:
        del relative_plan
        _, rows = self._rows(collections_client, project_id, active_sale)
        late = rows[0]
        before = Decimal(late["outstanding"])

        recorded = record_receipt(collections_client, project_id, active_sale, "1000.00")
        assert recorded.status_code == 201, recorded.text
        receipt_id = recorded.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
        assert (
            allocate(
                collections_client, project_id, receipt_id, late["installment_id"], "1000.00"
            ).status_code
            == 201
        )

        account, rows = self._rows(collections_client, project_id, active_sale)
        assert Decimal(rows[0]["outstanding"]) == before - Decimal("1000.00")
        assert Decimal(account["due_total"]) == Decimal(rows[0]["outstanding"]) + Decimal(
            rows[1]["outstanding"]
        )

    def test_an_instalment_awaiting_its_trigger_is_never_due(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        active_sale: str,
        plan_id: str,
    ) -> None:
        """A forecast is not a demand, whatever date it carries."""
        version_id = current_version_id(collections_client, project_id, plan_id)
        written = write_schedule(
            collections_client,
            project_id,
            plan_id,
            version_id,
            [
                fixed_row(1, "0.400000", (date.today() - timedelta(days=30)).isoformat()),
                {
                    "sequence": 2,
                    "label": "On completion",
                    "trigger_type": "construction_milestone",
                    "trigger_reference": "SLAB-L3",
                    "forecast_due_date": (date.today() - timedelta(days=200)).isoformat(),
                    "principal_fraction": "0.600000",
                },
            ],
        )
        assert written.status_code == 200, written.text
        base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
        assert collections_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Agreed"}).status_code == 200
        assert cfo_client.post(f"{base}/activate", json={}).status_code == 200

        account, rows = self._rows(collections_client, project_id, active_sale)
        awaiting = rows[1]
        assert awaiting["due_date"] is None
        assert awaiting["status"] == "awaiting_trigger"
        assert awaiting["bucket"] == "awaiting_trigger"
        assert awaiting["overdue_days"] == 0
        # Its forecast date is two hundred days behind us and moves nothing.
        assert Decimal(account["due_total"]) == Decimal(rows[0]["outstanding"])
        assert Decimal(account["overdue_total"]) == Decimal(rows[0]["outstanding"])
