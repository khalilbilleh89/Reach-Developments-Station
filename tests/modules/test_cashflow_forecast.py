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

from tests.modules.conftest import (
    cashflow_url,
    cover_construction_forecast,
    create_cashflow_forecast,
    create_forecast,
    govern_cashflow_forecast,
    govern_forecast,
    month_named,
    set_cashflow_line,
)


def cover_construction_months(
    client: TestClient,
    project_id: str,
    version_id: str,
    cost_codes_by_category: dict[str, str],
    *,
    months: tuple[tuple[str, str], ...],
) -> None:
    """Schedule the hard cost code across months, in the shape a test states."""
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


@pytest.fixture
def draft_forecast(
    finance_client: TestClient,
    project_id: str,
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
        activated = govern_cashflow_forecast(finance_client, cfo_client, project_id, draft_forecast)
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
                finance_client, cfo_client, project_id, draft_forecast
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
                finance_client, cfo_client, project_id, draft_forecast
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
            govern_cashflow_forecast(finance_client, cfo_client, project_id, second_id).status_code
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
        govern_cashflow_forecast(finance_client, cfo_client, project_id, draft_forecast)
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
