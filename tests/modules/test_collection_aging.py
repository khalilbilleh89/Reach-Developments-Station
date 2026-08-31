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
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.modules.collections import ledger
from tests.modules.conftest import collection_account, collections_url

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
    """Given the ledger, when somebody asks what it looked like on a past date."""

    def test_the_aging_report_answers_for_a_supplied_date(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        """Nothing is snapshotted, so any date can be asked and re-asked.

        The fixture schedule falls due on 1 March, 1 June and 1 September 2026.
        """
        del collecting_sale
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
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        del collecting_sale
        params = {"as_of": "2026-06-15", "overdue_only": True}
        rows = collections_client.get(f"{collections_url(project_id)}/aging", params=params).json()
        assert rows
        assert all(row["installment"]["overdue_days"] > 0 for row in rows)

    def test_the_account_ages_on_the_supplied_date_too(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        account = collection_account(
            collections_client, project_id, collecting_sale, as_of="2026-03-15"
        )
        assert account["as_of"] == "2026-03-15"
        assert account["oldest_overdue_days"] == 14
        assert account["installments_overdue"] == 1
        assert account["overdue_total"] == account["installments"][0]["scheduled"]
