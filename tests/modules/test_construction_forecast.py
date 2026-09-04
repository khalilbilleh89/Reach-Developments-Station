"""Forecast: what the project now expects to spend, and how far off budget it is.

The sign convention is the point of this file. A positive variance at completion
means **over budget** — an overrun — and it never reverses between screens. The
other property is reproducibility: a forecast fixes an as-of date and a budget
version, so a superseded forecast can still be read a year later rather than
quietly re-deriving itself from today's certificates.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    construction_url,
    create_forecast,
    govern_forecast,
    set_forecast_line,
)


def cover_forecast(
    client: TestClient,
    project_id: str,
    version_id: str,
    cost_codes: dict[str, str],
    *,
    hard: str = "0.00",
    soft: str = "0.00",
    contingency: str = "0.00",
    other: str = "0.00",
) -> None:
    for category, amount in (
        ("hard", hard),
        ("soft", soft),
        ("contingency", contingency),
        ("other", other),
    ):
        response = set_forecast_line(
            client,
            project_id,
            version_id,
            cost_code_id=cost_codes[category],
            forecast_remaining_amount_ex_tax=amount,
        )
        assert response.status_code == 200, response.text


class TestTheSignConvention:
    def test_a_forecast_above_the_control_budget_reports_a_positive_variance(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """Given / When / Then: over budget is positive, on every surface.

        Hard control budget is 10,000,000. 200,000 is certified and 10,300,000
        is forecast to come, so the estimate at completion is 10,500,000 and the
        line's variance is +500,000. Every other code is forecast at exactly its
        authorisation, so the project total carries the same +500,000 rather
        than a different number on a different screen.
        """
        version_id = create_forecast(finance_client, project_id).json()["id"]
        cover_forecast(
            finance_client,
            project_id,
            version_id,
            cost_codes,
            hard="10300000.00",
            soft="1000000.00",
            contingency="500000.00",
            other="250000.00",
        )
        assert (
            govern_forecast(finance_client, cfo_client, project_id, version_id).status_code == 200
        )

        detail = finance_client.get(f"{construction_url(project_id)}/forecasts/{version_id}").json()
        hard_line = next(line for line in detail["lines"] if line["cost_code"] == "HRD-01")
        assert hard_line["certified_to_date"] == "200000.00"
        assert hard_line["forecast_remaining_amount_ex_tax"] == "10300000.00"
        assert hard_line["estimate_at_completion"] == "10500000.00"
        assert hard_line["variance_at_completion"] == "500000.00"

        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["cost_control"]["variance_at_completion"] == "500000.00"

    def test_a_forecast_below_the_control_budget_reports_a_negative_variance(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        """Under budget is negative. The convention does not flip for good news."""
        version_id = create_forecast(finance_client, project_id).json()["id"]
        cover_forecast(finance_client, project_id, version_id, cost_codes, hard="9000000.00")
        assert (
            govern_forecast(finance_client, cfo_client, project_id, version_id).status_code == 200
        )

        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["cost_control"]["variance_at_completion"] == "-2750000.00"


class TestForecastBelowCommitment:
    def test_forecasting_less_than_is_committed_is_flagged_not_refused(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        """A judgement Finance is allowed to make, and the system must surface.

        1,000,000 is committed and nothing certified, so a forecast of 400,000
        remaining says the company expects to spend less than it has signed for.
        That may be right — a claim under negotiation, a descope in progress —
        but it is never something to leave unlabelled.
        """
        version_id = create_forecast(finance_client, project_id).json()["id"]
        cover_forecast(finance_client, project_id, version_id, cost_codes, hard="400000.00")
        assert (
            govern_forecast(finance_client, cfo_client, project_id, version_id).status_code == 200
        )

        detail = finance_client.get(f"{construction_url(project_id)}/forecasts/{version_id}").json()
        hard_line = next(line for line in detail["lines"] if line["cost_code"] == "HRD-01")
        assert hard_line["forecast_below_commitment"] is True
        assert hard_line["uncovered_commitment"] == "600000.00"

        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["controls"]["forecast_below_commitment_cost_codes"] == 1


class TestCoverage:
    def test_a_forecast_missing_a_cost_code_cannot_be_submitted(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        """An omitted line is not a forecast of zero."""
        version_id = create_forecast(finance_client, project_id).json()["id"]
        assert (
            set_forecast_line(
                finance_client,
                project_id,
                version_id,
                cost_code_id=cost_codes["hard"],
                forecast_remaining_amount_ex_tax="1000.00",
            ).status_code
            == 200
        )
        refused = finance_client.post(
            f"{construction_url(project_id)}/forecasts/{version_id}/submit", json={}
        )
        assert refused.status_code == 422, refused.text


class TestReproducibility:
    def test_a_forecast_cannot_be_taken_as_at_a_future_date(
        self, finance_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        refused = create_forecast(finance_client, project_id, as_of_date=tomorrow)
        assert refused.status_code == 422, refused.text

    def test_a_forecast_names_the_budget_its_variance_is_measured_against(
        self, finance_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        """Over budget means over an authorisation somebody can point at."""
        created = create_forecast(finance_client, project_id)
        assert created.status_code == 201, created.text
        assert created.json()["budget_version_id"] == active_budget
        assert created.json()["budget_version_number"] == 1

    def test_only_one_forecast_is_ever_being_prepared(
        self, finance_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        assert create_forecast(finance_client, project_id).status_code == 201
        second = create_forecast(finance_client, project_id, change_reason="Another go")
        assert second.status_code == 409, second.text

    def test_a_forecast_needs_a_budget_in_force(
        self, finance_client: TestClient, project_id: str, cost_codes: dict[str, str]
    ) -> None:
        """A variance measured against nothing is not a variance."""
        refused = create_forecast(finance_client, project_id)
        assert refused.status_code == 409, refused.text


class TestGovernance:
    def test_the_submitter_may_not_approve_their_own_forecast(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        version_id = create_forecast(finance_client, project_id).json()["id"]
        cover_forecast(finance_client, project_id, version_id, cost_codes, hard="1000.00")
        base = f"{construction_url(project_id)}/forecasts/{version_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        refused = finance_client.post(f"{base}/approve", json={"reason": "Fine by me"})
        assert refused.status_code == 403, refused.text

    def test_a_draft_forecast_is_not_in_force(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        version_id = create_forecast(finance_client, project_id).json()["id"]
        cover_forecast(finance_client, project_id, version_id, cost_codes, hard="9000000.00")
        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["controls"]["has_active_forecast"] is False
        assert summary["cost_control"]["forecast_remaining"] is None
        assert summary["cost_control"]["estimate_at_completion"] is None
        assert summary["cost_control"]["variance_at_completion"] is None

    def test_activating_a_forecast_supersedes_the_one_before_it(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        first = create_forecast(finance_client, project_id).json()["id"]
        cover_forecast(finance_client, project_id, first, cost_codes, hard="9000000.00")
        governed = govern_forecast(finance_client, cfo_client, project_id, first)
        assert governed.status_code == 200, governed.text

        second = create_forecast(
            finance_client, project_id, change_reason="Revised after month end"
        )
        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        cover_forecast(finance_client, project_id, second_id, cost_codes, hard="9500000.00")
        governed_second = govern_forecast(finance_client, cfo_client, project_id, second_id)
        assert governed_second.status_code == 200, governed_second.text

        versions = finance_client.get(f"{construction_url(project_id)}/forecasts").json()
        by_id = {row["id"]: row for row in versions}
        assert by_id[first]["status"] == "superseded"
        assert by_id[second_id]["status"] == "active"
