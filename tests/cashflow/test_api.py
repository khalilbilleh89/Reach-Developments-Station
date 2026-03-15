"""
Tests for the Cashflow Forecasting module API endpoints.

Validates HTTP behaviour, request/response contracts, and the core
forecast generation logic across different forecast bases.
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _create_hierarchy(client: TestClient, proj_code: str) -> tuple[str, str]:
    """Create Project → Phase → Building → Floor → Unit; return (project_id, unit_id)."""
    resp = client.post(
        "/api/v1/projects", json={"name": "CF Project", "code": proj_code}
    )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    assert resp.status_code == 201, resp.text
    phase_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": f"BLK-{proj_code}"},
    )
    assert resp.status_code == 201, resp.text
    building_id = resp.json()["id"]

    resp = client.post(
        "/api/v1/floors", json={"building_id": building_id, "level": 1}
    )
    assert resp.status_code == 201, resp.text
    floor_id = resp.json()["id"]

    resp = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    )
    assert resp.status_code == 201, resp.text
    unit_id = resp.json()["id"]

    return project_id, unit_id


def _create_payment_plan_template(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/payment-plans/templates",
        json={
            "name": "Monthly 12",
            "plan_type": "standard_installments",
            "down_payment_percent": 10.0,
            "number_of_installments": 12,
            "installment_frequency": "monthly",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_buyer(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Test Buyer", "email": email, "phone": "+9620000001"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_contract(
    client: TestClient,
    unit_id: str,
    buyer_id: str,
    contract_number: str,
    contract_price: float = 120_000.0,
) -> str:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-01-01",
            "contract_price": contract_price,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _apply_payment_plan(
    client: TestClient, contract_id: str, template_id: str
) -> None:
    resp = client.post(
        "/api/v1/payment-plans/generate",
        json={
            "contract_id": contract_id,
            "template_id": template_id,
            "start_date": "2026-01-01",
        },
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateForecast:
    def test_create_forecast_scheduled_collections(self, client: TestClient) -> None:
        project_id, unit_id = _create_hierarchy(client, "CF001")

        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "2026 Forecast",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
                "opening_balance": 0.0,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["project_id"] == project_id
        assert body["forecast_name"] == "2026 Forecast"
        assert body["forecast_basis"] == "scheduled_collections"
        assert body["status"] == "generated"
        assert body["id"] is not None

    def test_create_forecast_actual_plus_scheduled(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF002")

        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Blended Forecast",
                "start_date": "2026-01-01",
                "end_date": "2026-07-01",
                "period_type": "monthly",
                "forecast_basis": "actual_plus_scheduled",
                "opening_balance": 50_000.0,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["opening_balance"] == 50_000.0
        assert body["forecast_basis"] == "actual_plus_scheduled"

    def test_create_forecast_blended_requires_collection_factor(
        self, client: TestClient
    ) -> None:
        project_id, _ = _create_hierarchy(client, "CF003")

        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Blended no factor",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "blended",
                # collection_factor omitted intentionally
            },
        )
        assert resp.status_code == 422, resp.text

    def test_create_forecast_blended_with_factor(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF004")

        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Blended 80%",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "blended",
                "collection_factor": 0.8,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["collection_factor"] == 0.8

    def test_create_forecast_project_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": "nonexistent-id",
                "forecast_name": "Ghost Forecast",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )
        assert resp.status_code == 404, resp.text

    def test_create_forecast_invalid_dates(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF005")

        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Bad dates",
                "start_date": "2026-04-01",
                "end_date": "2026-01-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )
        assert resp.status_code == 422, resp.text

    def test_create_forecast_with_outflow_schedule(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF006")

        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "With Outflows",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
                "expected_outflows_schedule": {
                    "2026-01-01": 10_000.0,
                    "2026-02-01": 15_000.0,
                },
            },
        )
        assert resp.status_code == 201, resp.text


class TestGetForecast:
    def test_get_forecast_by_id(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF010")

        create_resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Q1 2026",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )
        assert create_resp.status_code == 201
        forecast_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/cashflow/forecasts/{forecast_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == forecast_id
        assert body["project_id"] == project_id

    def test_get_forecast_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cashflow/forecasts/nonexistent")
        assert resp.status_code == 404


class TestListForecastPeriods:
    def test_periods_generated_for_monthly_window(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF020")

        create_resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "3 months",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )
        assert create_resp.status_code == 201
        forecast_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/cashflow/forecasts/{forecast_id}/periods")
        assert resp.status_code == 200, resp.text
        periods = resp.json()
        # Jan, Feb, Mar = 3 periods
        assert len(periods) == 3
        assert periods[0]["sequence"] == 1
        assert periods[0]["period_start"] == "2026-01-01"
        assert periods[1]["period_start"] == "2026-02-01"
        assert periods[2]["period_start"] == "2026-03-01"

    def test_periods_balance_accumulation(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF021")

        create_resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Balance check",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
                "opening_balance": 100_000.0,
                "expected_outflows_schedule": {
                    "2026-01-01": 20_000.0,
                    "2026-02-01": 20_000.0,
                    "2026-03-01": 20_000.0,
                },
            },
        )
        assert create_resp.status_code == 201
        forecast_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/cashflow/forecasts/{forecast_id}/periods")
        assert resp.status_code == 200
        periods = resp.json()
        # First period opening should match forecast opening_balance
        assert float(periods[0]["opening_balance"]) == 100_000.0
        # Each subsequent period opening = previous closing
        for i in range(1, len(periods)):
            assert float(periods[i]["opening_balance"]) == pytest.approx(
                float(periods[i - 1]["closing_balance"]), rel=1e-4
            )

    def test_quarterly_periods(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF022")

        create_resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Quarterly",
                "start_date": "2026-01-01",
                "end_date": "2027-01-01",
                "period_type": "quarterly",
                "forecast_basis": "scheduled_collections",
            },
        )
        assert create_resp.status_code == 201
        forecast_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/cashflow/forecasts/{forecast_id}/periods")
        assert resp.status_code == 200
        periods = resp.json()
        # 4 quarters in a year
        assert len(periods) == 4

    def test_periods_for_unknown_forecast(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cashflow/forecasts/bad-id/periods")
        assert resp.status_code == 404


class TestListProjectForecasts:
    def test_list_forecasts_empty(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF030")

        resp = client.get(f"/api/v1/cashflow/projects/{project_id}/forecasts")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_list_forecasts_after_create(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF031")

        client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "First",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )
        client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Second",
                "start_date": "2026-04-01",
                "end_date": "2026-07-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )

        resp = client.get(f"/api/v1/cashflow/projects/{project_id}/forecasts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_list_forecasts_project_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cashflow/projects/no-such-project/forecasts")
        assert resp.status_code == 404


class TestProjectCashflowSummary:
    def test_summary_empty_project(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF040")

        resp = client.get(
            f"/api/v1/cashflow/projects/{project_id}/cashflow-summary"
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["project_id"] == project_id
        assert body["total_forecasts"] == 0
        assert body["latest_forecast_id"] is None
        assert body["total_expected_inflows"] == 0.0
        assert body["closing_balance"] == 0.0

    def test_summary_after_forecast(self, client: TestClient) -> None:
        project_id, _ = _create_hierarchy(client, "CF041")

        client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Summary Test",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
                "opening_balance": 10_000.0,
            },
        )

        resp = client.get(
            f"/api/v1/cashflow/projects/{project_id}/cashflow-summary"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_forecasts"] == 1
        assert body["latest_forecast_id"] is not None
        assert body["latest_forecast_name"] == "Summary Test"

    def test_summary_project_not_found(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/cashflow/projects/no-such/cashflow-summary"
        )
        assert resp.status_code == 404


class TestForecastWithPaymentData:
    def test_forecast_reflects_scheduled_installments(
        self, client: TestClient
    ) -> None:
        """Scheduled-collections forecast should reflect payment plan due amounts."""
        project_id, unit_id = _create_hierarchy(client, "CF050")
        template_id = _create_payment_plan_template(client)
        buyer_id = _create_buyer(client, "buyer050@test.com")
        contract_id = _create_contract(client, unit_id, buyer_id, "CTR-050")
        _apply_payment_plan(client, contract_id, template_id)

        # Forecast for Q1 2026 (installments start 2026-01-01)
        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "With schedule",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )
        assert resp.status_code == 201
        forecast_id = resp.json()["id"]

        periods_resp = client.get(
            f"/api/v1/cashflow/forecasts/{forecast_id}/periods"
        )
        assert periods_resp.status_code == 200
        periods = periods_resp.json()
        assert len(periods) == 3
        # Each period should have receivables_due reflecting scheduled amounts.
        # Contract = 120_000; down_payment 10% = 12_000 on 2026-01-01
        # followed by monthly installments = 108_000 / 12 = 9_000 each.
        # Period 1 (Jan): down-payment + first installment scheduled = 12_000 + 9_000 = 21_000
        # (exact split depends on template_engine logic, but total over Q1 should be > 0)
        total_receivables = sum(float(p["receivables_due"]) for p in periods)
        assert total_receivables > 0.0, (
            "Expected non-zero receivables_due reflecting payment plan installments"
        )

    def test_scheduled_collections_preserves_actual_inflows(
        self, client: TestClient
    ) -> None:
        """scheduled_collections basis must NOT zero out actual_inflows.

        actual_inflows should always reflect real recorded receipts so the
        API is truthful even when the expected basis is schedule-driven.
        """
        project_id, unit_id = _create_hierarchy(client, "CF051")
        template_id = _create_payment_plan_template(client)
        buyer_id = _create_buyer(client, "buyer051@test.com")
        contract_id = _create_contract(client, unit_id, buyer_id, "CTR-051")
        _apply_payment_plan(client, contract_id, template_id)

        # Fetch the first schedule line so we can record a receipt against it
        sched_resp = client.get(
            f"/api/v1/payment-plans/contracts/{contract_id}/schedule"
        )
        assert sched_resp.status_code == 200, sched_resp.text
        schedules = sched_resp.json()["items"]
        assert len(schedules) > 0
        first_line = schedules[0]

        # Record a receipt for the first installment (due 2026-01-01)
        receipt_resp = client.post(
            "/api/v1/collections/receipts",
            json={
                "contract_id": contract_id,
                "payment_schedule_id": first_line["id"],
                "receipt_date": "2026-01-10",
                "amount_received": 5000.0,
                "payment_method": "bank_transfer",
            },
        )
        assert receipt_resp.status_code == 201, receipt_resp.text

        # Generate a scheduled_collections forecast for January
        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Scheduled basis with actuals",
                "start_date": "2026-01-01",
                "end_date": "2026-02-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )
        assert resp.status_code == 201
        forecast_id = resp.json()["id"]

        periods_resp = client.get(f"/api/v1/cashflow/forecasts/{forecast_id}/periods")
        assert periods_resp.status_code == 200
        periods = periods_resp.json()
        assert len(periods) == 1

        # actual_inflows must reflect the 5_000 receipt, not be zeroed out
        assert float(periods[0]["actual_inflows"]) == pytest.approx(5000.0), (
            "actual_inflows should be truthful even in scheduled_collections mode"
        )


class TestForecastAtomicity:
    def test_successful_forecast_persists_header_and_periods_together(
        self, client: TestClient
    ) -> None:
        """Verify that a successful forecast creates both header and period rows."""
        project_id, _ = _create_hierarchy(client, "CF060")

        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Atomic test",
                "start_date": "2026-01-01",
                "end_date": "2026-04-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )
        assert resp.status_code == 201
        forecast_id = resp.json()["id"]

        # Header is retrievable
        assert client.get(f"/api/v1/cashflow/forecasts/{forecast_id}").status_code == 200

        # Period rows are also present
        periods = client.get(
            f"/api/v1/cashflow/forecasts/{forecast_id}/periods"
        ).json()
        assert len(periods) == 3


class TestForecastPeriodSequenceUniqueness:
    def test_periods_have_unique_sequential_order(self, client: TestClient) -> None:
        """Each period within a forecast must have a unique sequence number."""
        project_id, _ = _create_hierarchy(client, "CF070")

        resp = client.post(
            "/api/v1/cashflow/forecasts",
            json={
                "project_id": project_id,
                "forecast_name": "Sequence test",
                "start_date": "2026-01-01",
                "end_date": "2026-07-01",
                "period_type": "monthly",
                "forecast_basis": "scheduled_collections",
            },
        )
        assert resp.status_code == 201
        forecast_id = resp.json()["id"]

        periods = client.get(
            f"/api/v1/cashflow/forecasts/{forecast_id}/periods"
        ).json()
        assert len(periods) == 6

        sequences = [p["sequence"] for p in periods]
        assert sequences == list(range(1, 7)), (
            "Periods must have contiguous unique sequence numbers starting at 1"
        )
        assert len(set(sequences)) == len(sequences), "Sequence numbers must be unique"
