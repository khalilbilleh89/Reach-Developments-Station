"""A cashflow forecast is a governed statement, and it stays reproducible.

Four properties, and each one is a specific way a funding conversation with a
bank goes wrong if it is missing.

**It pins what it is measured against.** The construction forecast whose
remaining cost it schedules, and the buyer schedule it was built on. A version
that re-read either would not be the version anybody approved.

**Its monthly build schedule reconciles exactly.** Construction says how much is
left; this says when. If the months do not add up to the total, one of the two
documents is wrong about the project and nobody knows which.

**A source that moves underneath it makes it stale, not silently current.** The
refusal is the point: substituting a newer source under an approver changes what
they are approving, and the newer source being more accurate does not make the
substitution honest.

**The maker is never the checker.** By identifier, so one user holding Finance
and Approver / CFO is still one pair of eyes.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    cashflow_url,
    cover_construction_forecast,
    create_cashflow_forecast,
    create_forecast,
    current_version_id,
    fixed_row,
    govern_cashflow_forecast,
    govern_forecast,
    month_named,
    plans_url,
    set_cashflow_line,
    write_schedule,
)


def cover_construction_months(
    client: TestClient,
    project_id: str,
    version_id: str,
    cost_codes_by_category: dict[str, str],
    *,
    months: tuple[tuple[str, str], ...],
) -> None:
    """Schedule the hard cost code across months, in the shape a test states.

    The other three codes are written down as explicit zeros, because that is
    what a preparer has to do: the pinned construction forecast carries all four,
    and a code this version says nothing about fails its coverage check. Leaving
    them out would make every test here fail on the same three codes rather than
    on the thing it is about.
    """
    for month, amount in months:
        response = set_cashflow_line(
            client,
            project_id,
            version_id,
            period_month=month,
            source_kind="construction",
            category="construction",
            amount=amount,
            construction_cost_code_id=cost_codes_by_category["hard"],
        )
        assert response.status_code == 200, response.text
    for category, cost_code_id in cost_codes_by_category.items():
        if category == "hard":
            continue
        response = set_cashflow_line(
            client,
            project_id,
            version_id,
            period_month=months[0][0],
            source_kind="construction",
            category="construction",
            amount="0.00",
            construction_cost_code_id=cost_code_id,
        )
        assert response.status_code == 200, response.text


@pytest.fixture
def draft_forecast(
    finance_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    active_construction_forecast: str,
) -> str:
    """A cashflow forecast in draft, pinned to the construction forecast in force."""
    created = create_cashflow_forecast(finance_client, project_id)
    assert created.status_code == 201, created.text
    identifier: str = created.json()["id"]
    return identifier


class TestItPinsWhatItIsMeasuredAgainst:
    def test_a_forecast_names_the_construction_forecast_it_schedules(
        self,
        finance_client: TestClient,
        project_id: str,
        active_construction_forecast: str,
        draft_forecast: str,
    ) -> None:
        detail = finance_client.get(f"{cashflow_url(project_id)}/forecasts/{draft_forecast}").json()
        assert detail["construction_forecast_version_id"] == active_construction_forecast
        assert detail["construction_forecast_version_number"] == 1

    def test_a_project_with_no_construction_forecast_has_nothing_to_schedule(
        self, finance_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        """Zero would let a schedule of nothing reconcile against an uncosted build."""
        refused = create_cashflow_forecast(finance_client, project_id)
        assert refused.status_code == 409, refused.text
        assert "construction forecast" in refused.json()["detail"]

    def test_only_one_forecast_is_ever_being_prepared(
        self, finance_client: TestClient, project_id: str, draft_forecast: str
    ) -> None:
        second = create_cashflow_forecast(finance_client, project_id, change_reason="Another go")
        assert second.status_code == 409, second.text

    def test_a_forecast_cannot_be_taken_as_at_a_future_date(
        self,
        finance_client: TestClient,
        project_id: str,
        active_construction_forecast: str,
    ) -> None:
        tomorrow = date.today().replace(day=1)
        refused = create_cashflow_forecast(
            finance_client,
            project_id,
            as_of_date=date(tomorrow.year + 1, tomorrow.month, 1).isoformat(),
        )
        assert refused.status_code == 422, refused.text


class TestTheConstructionScheduleReconcilesExactly:
    def test_months_that_add_up_may_be_governed(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """1,000,000 left to spend, scheduled 400k + 600k. It activates."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "400000.00"), (month_named(2), "600000.00")),
        )
        activated = govern_cashflow_forecast(
            finance_client, cfo_client, project_id, draft_forecast, cost_codes=cost_codes
        )
        assert activated.status_code == 200, activated.text
        assert activated.json()["status"] == "active"

    def test_a_penny_short_is_refused(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """No tolerance. 999,999.99 against 1,000,000 is a cost nobody scheduled."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "400000.00"), (month_named(2), "599999.99")),
        )
        refused = finance_client.post(
            f"{cashflow_url(project_id)}/forecasts/{draft_forecast}/submit", json={}
        )
        assert refused.status_code == 409, refused.text
        assert "construction schedule" in refused.json()["detail"].lower()

    def test_scheduling_nothing_at_all_is_refused(
        self, finance_client: TestClient, project_id: str, draft_forecast: str
    ) -> None:
        """A missing cost code is not a zero: it is a code nobody considered."""
        refused = finance_client.post(
            f"{cashflow_url(project_id)}/forecasts/{draft_forecast}/submit", json={}
        )
        assert refused.status_code == 409, refused.text

    def test_the_reconciliation_is_visible_before_the_submit_button(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """Somebody approving a forecast should see the check on the same screen."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "400000.00"),),
        )
        detail = finance_client.get(f"{cashflow_url(project_id)}/forecasts/{draft_forecast}").json()
        checks = detail["construction_reconciliation"]
        assert checks, "the forecast file must show what it has to reconcile to"
        failing = [check for check in checks if not check["passed"]]
        assert failing, "400,000 scheduled against 1,000,000 remaining must fail"
        assert failing[0]["expected"] == "1000000.00"
        assert failing[0]["actual"] == "400000.00"


class TestAForecastOpensInTheMonthItWasTakenIn:
    """The opening balance has one temporal meaning, and the dates have to agree.

    The figures a preparer types are cash held at the start of the horizon, and
    every report rolls that balance forward through what has moved since. Let the
    horizon open in a *later* month and the balance describes a month that has
    not happened — while the current cash position, which is the opening balance
    plus this month's movement, quotes it as money in the bank today. Let it open
    in an *earlier* month and there is a stretch of unexamined history between
    the balance and the cutoff it is measured against.

    Tying the two together removes both without a second date field to keep in
    step: the balance is cash at the start of the month the forecast was taken
    in, and the days since it are actual transactions.
    """

    def test_a_forecast_opening_in_its_own_month_is_accepted(
        self, finance_client: TestClient, project_id: str, active_construction_forecast: str
    ) -> None:
        created = create_cashflow_forecast(
            finance_client,
            project_id,
            forecast_start_month=month_named(0),
            forecast_end_month=month_named(6),
        )
        assert created.status_code == 201, created.text

    def test_a_future_opening_month_is_refused(
        self, finance_client: TestClient, project_id: str, active_construction_forecast: str
    ) -> None:
        """Otherwise next month's opening balance is today's cash position."""
        refused = create_cashflow_forecast(
            finance_client,
            project_id,
            forecast_start_month=month_named(1),
            forecast_end_month=month_named(6),
        )
        assert refused.status_code == 422, refused.text
        detail = refused.json()["detail"]
        assert "opens in the month of its as-of date" in detail
        assert month_named(1) in detail

    def test_a_prior_opening_month_is_refused(
        self, finance_client: TestClient, project_id: str, active_construction_forecast: str
    ) -> None:
        """A balance from before the cutoff, with a month of history in between."""
        refused = create_cashflow_forecast(
            finance_client,
            project_id,
            forecast_start_month=month_named(-1),
            forecast_end_month=month_named(6),
        )
        assert refused.status_code == 422, refused.text
        assert "opens in the month of its as-of date" in refused.json()["detail"]

    def test_an_earlier_cutoff_may_open_in_its_own_month(
        self, finance_client: TestClient, project_id: str, active_construction_forecast: str
    ) -> None:
        """The rule ties the two dates together; it does not pin them to today."""
        created = create_cashflow_forecast(
            finance_client,
            project_id,
            as_of_date=month_named(-1),
            forecast_start_month=month_named(-1),
            forecast_end_month=month_named(6),
        )
        assert created.status_code == 201, created.text


class TestACodeNobodyOpenedIsNotACodeExpectingNothing:
    """Coverage and amount are two questions, and only one of them was being asked.

    ``scheduled.get(code, 0)`` reads an absent cost code as a schedule of zero.
    Against a code with nothing left to spend it agrees exactly, so the check
    passes — on the one code the preparer never opened. A build with a fully
    certified trade and a fully *forgotten* trade produced identical, green
    reconciliations.

    The fix is not a stricter amount check. It is a second question: does this
    forecast say anything at all about this code? An explicit zero answers it.
    """

    @pytest.fixture
    def settled_build(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> str:
        """A construction forecast in force with nothing left on any code."""
        version_id = create_forecast(finance_client, project_id).json()["id"]
        cover_construction_forecast(finance_client, project_id, version_id, cost_codes, hard="0.00")
        governed = govern_forecast(finance_client, cfo_client, project_id, version_id)
        assert governed.status_code == 200, governed.text
        return version_id

    @pytest.fixture
    def settled_cash_forecast(
        self, finance_client: TestClient, project_id: str, settled_build: str
    ) -> str:
        created = create_cashflow_forecast(finance_client, project_id)
        assert created.status_code == 201, created.text
        identifier: str = created.json()["id"]
        return identifier

    def test_a_code_with_nothing_left_still_has_to_be_written_down(
        self,
        finance_client: TestClient,
        project_id: str,
        settled_cash_forecast: str,
    ) -> None:
        """Nothing scheduled, nothing remaining, and it is still not covered.

        This is the case the old arithmetic could not see: every amount agrees at
        0.00 and every code is missing. It passed.
        """
        checks = finance_client.get(
            f"{cashflow_url(project_id)}/forecasts/{settled_cash_forecast}"
        ).json()["construction_reconciliation"]
        coverage = [
            check for check in checks if check["name"].startswith("construction_schedule_covers_")
        ]
        assert len(coverage) == 4, "every pinned cost code is asked about"
        assert all(check["passed"] is False for check in coverage)
        amounts = [
            check
            for check in checks
            if check["name"].startswith("construction_schedule_")
            and not check["name"].startswith("construction_schedule_covers_")
        ]
        assert all(check["passed"] is True for check in amounts), (
            "the amounts agree at zero, which is exactly why coverage is a separate question"
        )

    def test_a_forecast_of_a_settled_build_cannot_be_governed_until_it_says_so(
        self, finance_client: TestClient, project_id: str, settled_cash_forecast: str
    ) -> None:
        refused = finance_client.post(
            f"{cashflow_url(project_id)}/forecasts/{settled_cash_forecast}/submit", json={}
        )
        assert refused.status_code == 409, refused.text
        assert "no line for it at all" in refused.json()["detail"]

    def test_writing_the_zero_down_is_a_valid_schedule(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        settled_cash_forecast: str,
    ) -> None:
        """The distinction is a decision recorded, not an amount above zero."""
        for cost_code_id in cost_codes.values():
            assert (
                set_cashflow_line(
                    finance_client,
                    project_id,
                    settled_cash_forecast,
                    period_month=month_named(0),
                    source_kind="construction",
                    category="construction",
                    amount="0.00",
                    construction_cost_code_id=cost_code_id,
                ).status_code
                == 200
            )
        activated = govern_cashflow_forecast(
            finance_client, cfo_client, project_id, settled_cash_forecast
        )
        assert activated.status_code == 200, activated.text

    def test_a_code_with_cost_left_and_no_line_fails_both_questions(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """Coverage and amount are independent, and a missing code fails both."""
        assert (
            set_cashflow_line(
                finance_client,
                project_id,
                draft_forecast,
                period_month=month_named(1),
                source_kind="construction",
                category="construction",
                amount="1000000.00",
                construction_cost_code_id=cost_codes["hard"],
            ).status_code
            == 200
        )
        checks = {
            check["name"]: check
            for check in finance_client.get(
                f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
            ).json()["construction_reconciliation"]
        }
        assert checks["construction_schedule_covers_HRD-01"]["passed"] is True
        assert checks["construction_schedule_HRD-01"]["passed"] is True
        assert checks["construction_schedule_covers_SFT-01"]["passed"] is False
        assert checks["construction_schedule_SFT-01"]["passed"] is True, (
            "soft cost has nothing left to spend, so the amount agrees while the code is absent"
        )


class TestASourceThatMovesMakesItStale:
    def test_a_newer_construction_forecast_blocks_submission(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """Given / When / Then: the pin is checked again, not trusted from creation."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        second = create_forecast(finance_client, project_id, change_reason="Revised build cost")
        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        cover_construction_forecast(
            finance_client, project_id, second_id, cost_codes, hard="1200000.00"
        )
        assert govern_forecast(finance_client, cfo_client, project_id, second_id).status_code == 200

        refused = finance_client.post(
            f"{cashflow_url(project_id)}/forecasts/{draft_forecast}/submit", json={}
        )
        assert refused.status_code == 409, refused.text
        assert "no longer matches" in refused.json()["detail"]

    def test_the_forecast_file_says_it_is_stale(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        second_id = create_forecast(finance_client, project_id, change_reason="Revised").json()[
            "id"
        ]
        cover_construction_forecast(
            finance_client, project_id, second_id, cost_codes, hard="1200000.00"
        )
        govern_forecast(finance_client, cfo_client, project_id, second_id)

        detail = finance_client.get(f"{cashflow_url(project_id)}/forecasts/{draft_forecast}").json()
        assert detail["staleness"]["is_stale"] is True
        assert detail["staleness"]["construction_is_stale"] is True
        assert detail["staleness"]["pinned_construction_version_number"] == 1
        assert detail["staleness"]["active_construction_version_number"] == 2

    def test_a_governed_forecast_pinned_to_the_old_source_still_reads(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """History is never rewritten. The version says what it said."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, draft_forecast, cost_codes=cost_codes
            ).status_code
            == 200
        )

        second_id = create_forecast(finance_client, project_id, change_reason="Revised").json()[
            "id"
        ]
        cover_construction_forecast(
            finance_client, project_id, second_id, cost_codes, hard="1200000.00"
        )
        govern_forecast(finance_client, cfo_client, project_id, second_id)

        detail = finance_client.get(f"{cashflow_url(project_id)}/forecasts/{draft_forecast}").json()
        assert detail["status"] == "active"
        assert detail["construction_forecast_version_number"] == 1
        assert detail["staleness"]["construction_is_stale"] is True


class TestGovernance:
    def test_the_submitter_may_not_approve_their_own_forecast(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """Approval is the CFO's, and a Finance user is refused before identity."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        refused = finance_client.post(f"{base}/approve", json={"reason": "Fine by me"})
        assert refused.status_code == 403, refused.text

    def test_a_draft_forecast_is_not_in_force(
        self, finance_client: TestClient, project_id: str, draft_forecast: str
    ) -> None:
        summary = finance_client.get(f"{cashflow_url(project_id)}/summary").json()
        assert summary["has_active_forecast"] is False

    def test_activating_a_forecast_supersedes_the_one_before_it(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, draft_forecast, cost_codes=cost_codes
            ).status_code
            == 200
        )

        second = create_cashflow_forecast(finance_client, project_id, change_reason="Month end")
        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        cover_construction_months(
            finance_client,
            project_id,
            second_id,
            cost_codes,
            months=((month_named(2), "1000000.00"),),
        )
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, second_id, cost_codes=cost_codes
            ).status_code
            == 200
        )

        versions = finance_client.get(f"{cashflow_url(project_id)}/forecasts").json()
        by_id = {row["id"]: row for row in versions}
        assert by_id[draft_forecast]["status"] == "superseded"
        assert by_id[second_id]["status"] == "active"

    def test_a_governed_forecast_cannot_be_edited(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """Editing what somebody reviewed in place makes the review meaningless."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        govern_cashflow_forecast(
            finance_client, cfo_client, project_id, draft_forecast, cost_codes=cost_codes
        )
        refused = set_cashflow_line(
            finance_client,
            project_id,
            draft_forecast,
            period_month=month_named(1),
            source_kind="construction",
            category="construction",
            amount="1.00",
            construction_cost_code_id=cost_codes["hard"],
        )
        assert refused.status_code == 409, refused.text


class TestForecastLines:
    def test_a_month_outside_the_horizon_is_refused(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """A line nobody could ever see is worse than a refusal."""
        refused = set_cashflow_line(
            finance_client,
            project_id,
            draft_forecast,
            period_month=month_named(-6),
            source_kind="construction",
            category="construction",
            amount="1000.00",
            construction_cost_code_id=cost_codes["hard"],
        )
        assert refused.status_code == 422, refused.text

    def test_writing_the_same_cell_twice_replaces_rather_than_adds(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """A correction means "April is this now", never "April is this as well"."""
        for amount in ("400000.00", "1000000.00"):
            response = set_cashflow_line(
                finance_client,
                project_id,
                draft_forecast,
                period_month=month_named(1),
                source_kind="construction",
                category="construction",
                amount=amount,
                construction_cost_code_id=cost_codes["hard"],
            )
            assert response.status_code == 200, response.text

        detail = finance_client.get(f"{cashflow_url(project_id)}/forecasts/{draft_forecast}").json()
        construction_lines = [
            line for line in detail["lines"] if line["source_kind"] == "construction"
        ]
        assert len(construction_lines) == 1
        assert construction_lines[0]["amount"] == "1000000.00"

    def test_a_financing_line_takes_its_direction_from_its_type(
        self, finance_client: TestClient, project_id: str, draft_forecast: str
    ) -> None:
        """An equity contribution is cash in. That is a fact, not a form field."""
        response = set_cashflow_line(
            finance_client,
            project_id,
            draft_forecast,
            period_month=month_named(1),
            source_kind="financing",
            category="equity_contribution",
            amount="500000.00",
        )
        assert response.status_code == 200, response.text
        assert response.json()["flow_direction"] == "inflow"

    def test_a_financing_line_may_not_claim_the_wrong_direction(
        self, finance_client: TestClient, project_id: str, draft_forecast: str
    ) -> None:
        refused = set_cashflow_line(
            finance_client,
            project_id,
            draft_forecast,
            period_month=month_named(1),
            source_kind="financing",
            category="equity_contribution",
            amount="500000.00",
            flow_direction="outflow",
        )
        assert refused.status_code == 422, refused.text

    def test_a_construction_line_must_name_a_cost_code(
        self, finance_client: TestClient, project_id: str, draft_forecast: str
    ) -> None:
        """Without one the reconciliation has nothing to group by.

        Refused in words at the service boundary rather than left to the CHECK
        constraint behind it: a constraint violation reaches the caller as a 500
        naming a database object, which tells a preparer nothing about what to
        do next.
        """
        refused = set_cashflow_line(
            finance_client,
            project_id,
            draft_forecast,
            period_month=month_named(1),
            source_kind="construction",
            category="construction",
            amount="1000.00",
        )
        assert refused.status_code == 422, refused.text
        assert "cost code" in refused.json()["detail"]


UNDATED_SCHEDULE = [
    fixed_row(1, "0.500000", month_named(1)),
    {
        "sequence": 2,
        "label": "On structural completion",
        "trigger_type": "construction_milestone",
        "trigger_reference": "SLAB-L3",
        "principal_fraction": "0.500000",
    },
]


def govern_plan_version(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
    version_id: str,
) -> None:
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Terms reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate", json={}).status_code == 200


class TestBuyerCashWithNoTimingBlocksGovernance:
    """An instalment nobody can place in a month is not an instalment worth nothing.

    The snapshot cannot invent a month for it — putting money in a period on no
    evidence is worse than leaving it out — so it is left out, and the version is
    quietly short of contractually owed cash. Every figure taken from it then
    understates what the project is owed and overstates what it needs to raise,
    and the report gives no sign: the months add up, the bridge balances and the
    arithmetic is impeccable.

    So the count is a gate, not a note. An explicit dated zero is a decision;
    missing timing is an omission, and the difference is the whole rule.
    """

    @pytest.fixture
    def undated_plan(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        active_sale: str,
        plan_id: str,
    ) -> str:
        """A governing schedule half of which waits on a milestone nobody has dated."""
        version_id = current_version_id(collections_client, project_id, plan_id)
        written = write_schedule(
            collections_client, project_id, plan_id, version_id, UNDATED_SCHEDULE
        )
        assert written.status_code == 200, written.text
        govern_plan_version(collections_client, cfo_client, project_id, plan_id, version_id)
        return version_id

    @pytest.fixture
    def restructured_under_a_governed_forecast(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_plan: tuple[str, str],
        draft_forecast: str,
    ) -> str:
        """A forecast put in force on a placeable schedule, then the schedule moved.

        The ordinary case rather than a contrived one: a buyer renegotiates terms
        after Finance has signed a forecast off, and the new terms hang an
        instalment on a milestone nobody has forecast a date for yet.
        """
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, draft_forecast, cost_codes=cost_codes
            ).status_code
            == 200
        )
        plan_id, _ = active_plan
        revised = collections_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions",
            json={"change_reason": "Milestone terms agreed with the buyer"},
        )
        assert revised.status_code == 201, revised.text
        revised_id: str = revised.json()["version"]["id"]
        written = write_schedule(
            collections_client, project_id, plan_id, revised_id, UNDATED_SCHEDULE
        )
        assert written.status_code == 200, written.text
        govern_plan_version(collections_client, cfo_client, project_id, plan_id, revised_id)
        return draft_forecast

    def test_the_reconciliation_says_the_snapshot_is_incomplete(
        self,
        finance_client: TestClient,
        project_id: str,
        restructured_under_a_governed_forecast: str,
    ) -> None:
        """Counted and named, not dropped quietly into a total that looks right."""
        checks = finance_client.get(f"{cashflow_url(project_id)}/reconciliation").json()["checks"]
        completeness = next(
            check for check in checks if check["name"] == "customer_schedule_snapshot_complete"
        )
        assert completeness["passed"] is False
        assert completeness["actual"] == "1"

    def test_submission_is_refused_and_says_which_instalment(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        undated_plan: str,
        draft_forecast: str,
    ) -> None:
        """A count alone tells a preparer something is wrong and not where to go."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        refused = finance_client.post(
            f"{cashflow_url(project_id)}/forecasts/{draft_forecast}/submit", json={}
        )
        assert refused.status_code == 409, refused.text
        detail = refused.json()["detail"]
        assert "1 governing buyer instalment" in detail
        assert "On structural completion" in detail

    def _restructure_with_undated_instalments(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        active_plan: tuple[str, str],
    ) -> None:
        """Move the buyer schedule under a forecast, leaving one instalment undated."""
        plan_id, _ = active_plan
        revised = collections_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions",
            json={"change_reason": "Milestone terms agreed with the buyer"},
        )
        assert revised.status_code == 201, revised.text
        revised_id = revised.json()["version"]["id"]
        written = write_schedule(
            collections_client, project_id, plan_id, revised_id, UNDATED_SCHEDULE
        )
        assert written.status_code == 200, written.text
        govern_plan_version(collections_client, cfo_client, project_id, plan_id, revised_id)

    def test_approval_re_proves_it_after_the_schedule_moved(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_plan: tuple[str, str],
        draft_forecast: str,
    ) -> None:
        """A plan restructured while a forecast waits for a signature is the ordinary case.

        Submission is not a promise that the sources will hold still, and the
        refresh that clears the staleness refusal would carry the omission in
        with it. Submitted is the last point at which a schedule may be
        re-pinned, so it is the point this has to be caught — before a signature
        is attached to months that are short of contractually owed money.
        """
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        self._restructure_with_undated_instalments(
            collections_client, cfo_client, project_id, active_plan
        )
        refreshed = finance_client.post(f"{base}/refresh-customer-snapshot", json={})
        assert refreshed.status_code == 200, "a submitted version may still be re-pinned"

        refused = cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})
        assert refused.status_code == 409, refused.text
        assert "no date of any kind" in refused.json()["detail"]

    def test_an_approved_version_cannot_take_the_omission_in_at_all(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_plan: tuple[str, str],
        draft_forecast: str,
    ) -> None:
        """Past the signature the schedule is closed, so there is nothing to smuggle.

        This used to be reachable: an approved version could be refreshed, which
        pulled the restructured schedule — undated instalments and all — in
        underneath the approval, and only activation caught it. Closing the
        refresh closes the route, and the two refusals here say so in the order
        an operator meets them.
        """
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200

        self._restructure_with_undated_instalments(
            collections_client, cfo_client, project_id, active_plan
        )

        refused_refresh = finance_client.post(f"{base}/refresh-customer-snapshot", json={})
        assert refused_refresh.status_code == 409, refused_refresh.text
        assert "already been approved" in refused_refresh.json()["detail"]

        refused_activation = finance_client.post(f"{base}/activate", json={})
        assert refused_activation.status_code == 409, refused_activation.text
        assert "Withdraw the approval" in refused_activation.json()["detail"], (
            "the version is stranded, and the refusal has to name the way out"
        )


class TestAnApprovedForecastIsNotATrap:
    """The lifecycle needs a way out of *approved*, or a project can be stranded.

    Approval is not the last gate: activation re-proves the sources, so a
    construction forecast activated while a cashflow version waited for its
    signature makes that version unactivatable. Meanwhile the one-open-forecast
    rule counts it as the project's open version, and only a draft may be
    edited. Without a governed exit the version sits in the open slot with
    nothing able to move it, and cashflow forecasting stops for that
    development — no activation, no edit, no replacement.

    These prove the exit exists, that it is the CFO's to take, and that it does
    not quietly rewrite the approval it is undoing.
    """

    def test_the_deadlock_has_a_governed_way_out(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """The whole sequence, end to end, as an operator would hit it."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        approved = cfo_client.post(f"{base}/approve", json={"reason": "Reviewed with Finance"})
        assert approved.status_code == 200, approved.text

        # Construction moves on while the cashflow version waits.
        second = create_forecast(finance_client, project_id, change_reason="Revised build cost")
        second_id = second.json()["id"]
        cover_construction_forecast(
            finance_client, project_id, second_id, cost_codes, hard="1200000.00"
        )
        assert govern_forecast(finance_client, cfo_client, project_id, second_id).status_code == 200

        stranded = finance_client.post(f"{base}/activate", json={})
        assert stranded.status_code == 409, stranded.text
        assert "no longer matches" in stranded.json()["detail"]

        blocked = create_cashflow_forecast(finance_client, project_id)
        assert blocked.status_code == 409, "the approved version still holds the open slot"

        withdrawn = cfo_client.post(
            f"{base}/reject", json={"reason": "Construction forecast moved underneath it"}
        )
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["status"] == "rejected"

        replacement = create_cashflow_forecast(finance_client, project_id)
        assert replacement.status_code == 201, replacement.text
        assert replacement.json()["construction_forecast_version_id"] == second_id, (
            "the replacement must be measured against the construction forecast now "
            "in force, not the one that stranded its predecessor"
        )

    def test_a_stranded_forecast_is_told_to_withdraw_rather_than_rebase(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """Advice a reader cannot act on is worse than none.

        "Rebase this forecast" is right for a draft and impossible for an
        approved version, whose pin is fixed and whose lines are frozen.
        """
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        finance_client.post(f"{base}/submit", json={})
        cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})
        second_id = create_forecast(finance_client, project_id, change_reason="Revised").json()[
            "id"
        ]
        cover_construction_forecast(
            finance_client, project_id, second_id, cost_codes, hard="1200000.00"
        )
        govern_forecast(finance_client, cfo_client, project_id, second_id)

        refused = finance_client.post(f"{base}/activate", json={})
        assert refused.status_code == 409, refused.text
        assert "Withdraw the approval" in refused.json()["detail"]

    def test_the_approval_is_kept_on_the_record(
        self,
        db: Session,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """A withdrawal is written beside the approval, never over it.

        The CFO did approve it. Erasing that to make the row tidy would leave an
        auditor unable to see that a signature was given and later taken back,
        which is exactly the sequence worth seeing — so this is asserted against
        the stored row rather than the response, because keeping the record is
        the promise and the read model does not publish those columns.
        """
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        finance_client.post(f"{base}/submit", json={})
        assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
        approved_at, approved_by = db.execute(
            text(
                "SELECT approved_at, approved_by_user_id FROM cashflow_forecast_versions "
                "WHERE id = :id"
            ),
            {"id": draft_forecast},
        ).one()
        assert approved_at is not None and approved_by is not None

        withdrawn = cfo_client.post(f"{base}/reject", json={"reason": "Basis moved"})
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["status"] == "rejected"

        after = db.execute(
            text(
                "SELECT approved_at, approved_by_user_id, rejected_at, rejection_reason "
                "FROM cashflow_forecast_versions WHERE id = :id"
            ),
            {"id": draft_forecast},
        ).one()
        assert after.approved_at == approved_at, "the approval is not erased"
        assert after.approved_by_user_id == approved_by
        assert after.rejected_at is not None
        assert after.rejection_reason == "Basis moved"

    def test_only_the_approver_may_withdraw(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """Withdrawal is the same authority as approval, not a preparer's escape."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        finance_client.post(f"{base}/submit", json={})
        cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})

        refused = finance_client.post(f"{base}/reject", json={"reason": "Let me out"})
        assert refused.status_code == 403, refused.text

    def test_a_governed_version_still_cannot_be_rejected(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """Widening the exit must not reach what the company already reported."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, draft_forecast
            ).status_code
            == 200
        )
        refused = cfo_client.post(f"{base}/reject", json={"reason": "Changed my mind"})
        assert refused.status_code == 409, refused.text


class TestApprovalReprovesTheSources:
    """A signature may not be attached to a basis already known to have moved.

    The sources were proved at submission and again at activation, and not in
    between — so a construction forecast replaced while a version waited could
    be approved, and the problem surfaced only at activation, with the CFO's
    approval already recorded against something nobody could use.
    """

    def test_a_stale_construction_source_refuses_the_approval(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        second_id = create_forecast(finance_client, project_id, change_reason="Revised").json()[
            "id"
        ]
        cover_construction_forecast(
            finance_client, project_id, second_id, cost_codes, hard="1200000.00"
        )
        assert govern_forecast(finance_client, cfo_client, project_id, second_id).status_code == 200

        refused = cfo_client.post(f"{base}/approve", json={"reason": "Looks fine to me"})
        assert refused.status_code == 409, refused.text
        assert "no longer matches" in refused.json()["detail"]

    def test_an_unmoved_source_still_approves(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """The new gate must not refuse the ordinary case."""
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        finance_client.post(f"{base}/submit", json={})
        approved = cfo_client.post(f"{base}/approve", json={"reason": "Reviewed with Finance"})
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"


class TestAnApprovedScheduleDoesNotMoveUnderTheSignature:
    """Refreshing the buyer snapshot re-reads what the CFO approved.

    An approved version is structurally open — it holds the project's one open
    slot — and that is a different question from whether it may still be
    changed. Refreshing under the approval would alter the monthly inflows, the
    funding requirement and the returns that the approval was given for, with
    nobody approving the result.
    """

    def test_an_approved_version_refuses_the_refresh(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        finance_client.post(f"{base}/submit", json={})
        cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})

        refused = finance_client.post(f"{base}/refresh-customer-snapshot", json={})
        assert refused.status_code == 409, refused.text
        detail = refused.json()["detail"]
        assert "already been approved" in detail
        assert "Withdraw the approval" in detail, (
            "the refusal has to name the way out, not just say no"
        )

    def test_a_draft_and_a_submitted_version_may_still_refresh(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        """The gate closes on approval, not before it."""
        base = f"{cashflow_url(project_id)}/forecasts/{draft_forecast}"
        assert finance_client.post(f"{base}/refresh-customer-snapshot", json={}).status_code == 200

        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        finance_client.post(f"{base}/submit", json={})
        assert finance_client.post(f"{base}/refresh-customer-snapshot", json={}).status_code == 200

    def test_a_governed_version_refuses_it_as_history(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        draft_forecast: str,
    ) -> None:
        cover_construction_months(
            finance_client,
            project_id,
            draft_forecast,
            cost_codes,
            months=((month_named(1), "1000000.00"),),
        )
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, draft_forecast
            ).status_code
            == 200
        )
        refused = finance_client.post(
            f"{cashflow_url(project_id)}/forecasts/{draft_forecast}/refresh-customer-snapshot",
            json={},
        )
        assert refused.status_code == 409, refused.text
        assert "rejected version is a statement" in refused.json()["detail"]
