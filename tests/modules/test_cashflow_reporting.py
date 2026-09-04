"""One management view, and every figure named with the module that owns it.

Nothing here is recalculated. Construction's control position comes from
construction, collections' from collections, unit economics' contribution from
unit economics — each through the reader that module already publishes.
Restating another module's arithmetic would produce a second definition of
"certified to date" that agrees today and drifts the first time the original
changes, and the drift would be found by an executive comparing two screens.

A tile with no traceable owner is a tile nobody can check, so every metric
carries its source module and, where the transactions exist, the drill-down that
opens it.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    cashflow_url,
    confirm_receipt,
    construction_url,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    record_receipt,
)


def metrics_of(client: TestClient, project_id: str) -> dict[str, dict[str, object]]:
    response = client.get(f"{cashflow_url(project_id)}/management")
    assert response.status_code == 200, response.text
    body = response.json()
    return {metric["key"]: metric for group in body["groups"] for metric in group["metrics"]}


@pytest.fixture
def reported_project(
    finance_client: TestClient,
    cfo_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    collecting_sale: str,
    active_construction_forecast: str,
    cost_codes: dict[str, str],
) -> str:
    """A project with a governed cashflow forecast and some real cash in it."""
    from tests.modules.conftest import set_cashflow_line

    created = create_cashflow_forecast(
        finance_client,
        project_id,
        opening_unrestricted_cash="2000.00",
        forecast_start_month=month_named(0),
        forecast_end_month=month_named(3),
    )
    identifier: str = created.json()["id"]
    assert (
        set_cashflow_line(
            finance_client,
            project_id,
            identifier,
            period_month=month_named(1),
            source_kind="construction",
            category="construction",
            amount="1000000.00",
            construction_cost_code_id=cost_codes["hard"],
        ).status_code
        == 200
    )
    assert (
        govern_cashflow_forecast(
            finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
        ).status_code
        == 200
    )
    receipt = record_receipt(
        collections_client,
        project_id,
        collecting_sale,
        "500.00",
        receipt_date=date.today().isoformat(),
    )
    confirm_receipt(finance_client, project_id, receipt.json()["id"])
    return identifier


class TestTheBasisIsAlwaysStated:
    def test_every_reporting_response_says_when_and_in_what(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        """A dashboard total without its basis lets two people both be right."""
        for path in ("/summary", "/monthly", "/management", "/reconciliation"):
            basis = finance_client.get(f"{cashflow_url(project_id)}{path}").json()["basis"]
            assert basis["project_id"], path
            assert basis["as_of_date"], path
            assert basis["currency_code"], path
            assert basis["forecast_version_number"] == 1, path


class TestEveryFigureNamesItsOwner:
    def test_construction_figures_come_from_construction(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        metrics = metrics_of(finance_client, project_id)
        for key in (
            "control_budget",
            "revised_commitment",
            "certified_to_date",
            "estimate_at_completion",
            "variance_at_completion",
        ):
            assert metrics[key]["source_module"] == "construction", key

    def test_collections_figures_come_from_collections(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        metrics = metrics_of(finance_client, project_id)
        for key in ("due_to_date", "confirmed_collected", "overdue", "unapplied_cash"):
            assert metrics[key]["source_module"] == "collections", key

    def test_unit_economics_figures_come_from_unit_economics(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        metrics = metrics_of(finance_client, project_id)
        for key in ("revenue_total", "contribution_profit_total", "margin_fraction"):
            assert metrics[key]["source_module"] == "unit_economics", key

    def test_cashflow_owns_only_the_cross_module_time_based_figures(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        metrics = metrics_of(finance_client, project_id)
        for key in (
            "unrestricted_cash",
            "peak_funding_deficit",
            "net_present_value",
            "forecast_collection_coverage",
        ):
            assert metrics[key]["source_module"] == "cashflow", key


class TestTheFiguresAgreeWithTheirOwners:
    def test_the_construction_position_is_not_restated(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        """Read from construction's own summary, so the two cannot drift."""
        construction = finance_client.get(f"{construction_url(project_id)}/summary").json()
        metrics = metrics_of(finance_client, project_id)
        assert metrics["control_budget"]["value"] == construction["cost_control"]["control_budget"]
        assert (
            metrics["certified_to_date"]["value"]
            == construction["cost_control"]["certified_to_date"]
        )

    def test_the_cash_position_matches_the_summary_endpoint(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        summary = finance_client.get(f"{cashflow_url(project_id)}/summary").json()
        metrics = metrics_of(finance_client, project_id)
        assert metrics["unrestricted_cash"]["value"] == summary["position"]["unrestricted_cash"]
        assert metrics["net_present_value"]["value"] == summary["returns"]["net_present_value"]


class TestTilesOpenIntoTheirSources:
    def test_a_cash_figure_names_the_drilldown_that_explains_it(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        metrics = metrics_of(finance_client, project_id)
        assert metrics["confirmed_collected"]["drilldown_source_type"] == "collection_receipt"
        assert metrics["construction_paid"]["drilldown_source_type"] == "construction_payment"

    def test_the_named_drilldown_actually_returns_rows(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        """A traceability field that leads nowhere is worse than none."""
        metrics = metrics_of(finance_client, project_id)
        source_type = metrics["confirmed_collected"]["drilldown_source_type"]
        rows = finance_client.get(
            f"{cashflow_url(project_id)}/drilldown", params={"source_type": source_type}
        ).json()["rows"]
        assert rows
        assert all(row["source_type"] == source_type for row in rows)


class TestIrrIsNeverAlone:
    def test_the_return_group_carries_absolute_figures_beside_the_rate(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        """A percentage with no cash behind it is a number nobody can check."""
        body = finance_client.get(f"{cashflow_url(project_id)}/management").json()
        returns = next(group for group in body["groups"] if group["group"] == "Returns")
        keys = {metric["key"] for metric in returns["metrics"]}
        assert "equity_irr_per_period" in keys
        assert "net_present_value" in keys
        assert "net_project_cashflow" in keys
        assert "equity_net" in keys

    def test_an_unavailable_irr_states_its_reason_on_the_dashboard(
        self, finance_client: TestClient, project_id: str, reported_project: str
    ) -> None:
        metrics = metrics_of(finance_client, project_id)
        assert metrics["equity_irr_per_period"]["value"] is None
        assert metrics["equity_irr_unavailable_reason"]["value"] is not None
