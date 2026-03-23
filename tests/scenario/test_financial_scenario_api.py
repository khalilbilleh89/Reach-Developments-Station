"""
Tests for the Financial Scenario Modeling API endpoints.

Validates HTTP behaviour, request/response contracts, create/list/get/delete
operations, scenario comparison, and 404/422 error handling.
"""

import pytest
from fastapi.testclient import TestClient


_SCENARIOS_BASE = "/api/v1/scenarios"

_VALID_SCENARIO = {
    "name": "Financial Model",
    "source_type": "feasibility",
    "notes": "For financial scenario testing",
}

_VALID_ASSUMPTIONS = {
    "gdv": 10_000_000.0,
    "total_cost": 7_000_000.0,
    "equity_invested": 2_450_000.0,
    "sellable_area_sqm": 5_000.0,
    "avg_sale_price_per_sqm": 2_000.0,
    "development_period_months": 24,
    "annual_discount_rate": 0.10,
    "label": "Base Case",
}

_VALID_RUN_PAYLOAD = {
    "assumptions": _VALID_ASSUMPTIONS,
    "is_baseline": True,
}


def _create_scenario(client: TestClient) -> str:
    resp = client.post(_SCENARIOS_BASE, json=_VALID_SCENARIO)
    assert resp.status_code == 201
    return resp.json()["id"]


def _runs_url(scenario_id: str) -> str:
    return f"{_SCENARIOS_BASE}/{scenario_id}/financial-runs"


# ---------------------------------------------------------------------------
# Create financial run
# ---------------------------------------------------------------------------


def test_create_financial_run(client: TestClient):
    scenario_id = _create_scenario(client)
    resp = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["scenario_id"] == scenario_id
    assert data["label"] == "Base Case"
    assert data["is_baseline"] is True
    assert "irr" in data
    assert "npv" in data
    assert "roi" in data
    assert "developer_margin" in data
    assert "gross_profit" in data
    assert data["irr"] is not None and data["irr"] > 0.0
    assert data["gross_profit"] is not None
    assert abs(data["gross_profit"] - 3_000_000.0) < 1.0


def test_create_financial_run_results_json_present(client: TestClient):
    scenario_id = _create_scenario(client)
    resp = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["results_json"] is not None
    results = data["results_json"]
    assert "returns" in results
    assert "cashflows" in results
    assert "effective_gdv" in results
    assert len(results["cashflows"]) == 24


def test_create_financial_run_with_price_uplift(client: TestClient):
    scenario_id = _create_scenario(client)
    payload = {
        "assumptions": {**_VALID_ASSUMPTIONS, "pricing_uplift_pct": 0.10, "label": "Price +10%"},
        "is_baseline": False,
    }
    resp = client.post(_runs_url(scenario_id), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Price +10%"
    # effective_gdv should be 11_000_000
    assert abs(data["results_json"]["effective_gdv"] - 11_000_000.0) < 1.0


def test_create_financial_run_with_cost_inflation(client: TestClient):
    scenario_id = _create_scenario(client)
    payload = {
        "assumptions": {**_VALID_ASSUMPTIONS, "cost_inflation_pct": 0.10, "label": "Cost +10%"},
        "is_baseline": False,
    }
    resp = client.post(_runs_url(scenario_id), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    # effective_total_cost should be 7_700_000
    assert abs(data["results_json"]["effective_total_cost"] - 7_700_000.0) < 1.0


def test_create_financial_run_with_slower_sales(client: TestClient):
    scenario_id = _create_scenario(client)
    payload = {
        "assumptions": {
            **_VALID_ASSUMPTIONS,
            "sales_pace_months_override": 36,
            "label": "Slow Sales",
        },
        "is_baseline": False,
    }
    resp = client.post(_runs_url(scenario_id), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["results_json"]["cashflows"]) == 36


def test_create_financial_run_with_overrides(client: TestClient):
    scenario_id = _create_scenario(client)
    payload = {
        "assumptions": _VALID_ASSUMPTIONS,
        "overrides": {"pricing_uplift_pct": 0.05, "label": "Override Label"},
        "is_baseline": False,
    }
    resp = client.post(_runs_url(scenario_id), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Override Label"


def test_create_financial_run_scenario_not_found(client: TestClient):
    resp = client.post(
        _runs_url("no-such-scenario"),
        json=_VALID_RUN_PAYLOAD,
    )
    assert resp.status_code == 404


def test_create_financial_run_missing_gdv(client: TestClient):
    scenario_id = _create_scenario(client)
    bad_payload = {
        "assumptions": {k: v for k, v in _VALID_ASSUMPTIONS.items() if k != "gdv"},
        "is_baseline": False,
    }
    resp = client.post(_runs_url(scenario_id), json=bad_payload)
    assert resp.status_code == 422


def test_create_financial_run_negative_period(client: TestClient):
    scenario_id = _create_scenario(client)
    bad_payload = {
        "assumptions": {**_VALID_ASSUMPTIONS, "development_period_months": -1},
        "is_baseline": False,
    }
    resp = client.post(_runs_url(scenario_id), json=bad_payload)
    assert resp.status_code == 422


def test_create_financial_run_discount_rate_gte_one_rejected(client: TestClient):
    scenario_id = _create_scenario(client)
    bad_payload = {
        "assumptions": {**_VALID_ASSUMPTIONS, "annual_discount_rate": 1.5},
        "is_baseline": False,
    }
    resp = client.post(_runs_url(scenario_id), json=bad_payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List financial runs
# ---------------------------------------------------------------------------


def test_list_financial_runs_empty(client: TestClient):
    scenario_id = _create_scenario(client)
    resp = client.get(_runs_url(scenario_id))
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_financial_runs(client: TestClient):
    scenario_id = _create_scenario(client)
    client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD)
    client.post(
        _runs_url(scenario_id),
        json={
            "assumptions": {**_VALID_ASSUMPTIONS, "label": "Alt Case"},
            "is_baseline": False,
        },
    )
    resp = client.get(_runs_url(scenario_id))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_financial_runs_pagination(client: TestClient):
    scenario_id = _create_scenario(client)
    for i in range(5):
        client.post(
            _runs_url(scenario_id),
            json={"assumptions": {**_VALID_ASSUMPTIONS, "label": f"Run {i}"}, "is_baseline": False},
        )
    resp = client.get(_runs_url(scenario_id), params={"skip": 2, "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_list_financial_runs_scenario_not_found(client: TestClient):
    resp = client.get(_runs_url("no-such-scenario"))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Get financial run
# ---------------------------------------------------------------------------


def test_get_financial_run(client: TestClient):
    scenario_id = _create_scenario(client)
    run_id = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD).json()["id"]
    resp = client.get(f"{_runs_url(scenario_id)}/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run_id
    assert data["scenario_id"] == scenario_id


def test_get_financial_run_not_found(client: TestClient):
    scenario_id = _create_scenario(client)
    resp = client.get(f"{_runs_url(scenario_id)}/no-such-run")
    assert resp.status_code == 404


def test_get_financial_run_wrong_scenario(client: TestClient):
    """Getting a run by a different scenario's ID returns 404."""
    s1 = _create_scenario(client)
    s2_resp = client.post(
        _SCENARIOS_BASE, json={**_VALID_SCENARIO, "name": "Scenario 2"}
    )
    s2 = s2_resp.json()["id"]
    run_id = client.post(_runs_url(s1), json=_VALID_RUN_PAYLOAD).json()["id"]
    resp = client.get(f"{_runs_url(s2)}/{run_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete financial run
# ---------------------------------------------------------------------------


def test_delete_financial_run(client: TestClient):
    scenario_id = _create_scenario(client)
    run_id = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD).json()["id"]
    resp = client.delete(f"{_runs_url(scenario_id)}/{run_id}")
    assert resp.status_code == 204
    # Confirm deleted
    assert client.get(f"{_runs_url(scenario_id)}/{run_id}").status_code == 404


def test_delete_financial_run_not_found(client: TestClient):
    scenario_id = _create_scenario(client)
    resp = client.delete(f"{_runs_url(scenario_id)}/no-such-run")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Compare financial runs
# ---------------------------------------------------------------------------

_COMPARE_URL = f"{_SCENARIOS_BASE}/financial-runs/compare"


def test_compare_financial_runs_basic(client: TestClient):
    scenario_id = _create_scenario(client)
    run1_id = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD).json()["id"]
    run2_id = client.post(
        _runs_url(scenario_id),
        json={
            "assumptions": {**_VALID_ASSUMPTIONS, "pricing_uplift_pct": 0.10, "label": "Alt"},
            "is_baseline": False,
        },
    ).json()["id"]
    resp = client.post(_COMPARE_URL, json={"run_ids": [run1_id, run2_id]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["baseline_run_id"] == run1_id
    assert data["baseline_label"] == "Base Case"
    assert len(data["runs"]) == 2
    assert len(data["deltas"]) == 2


def test_compare_financial_runs_baseline_deltas_zero(client: TestClient):
    scenario_id = _create_scenario(client)
    run1_id = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD).json()["id"]
    run2_id = client.post(
        _runs_url(scenario_id),
        json={
            "assumptions": {**_VALID_ASSUMPTIONS, "pricing_uplift_pct": 0.10, "label": "Alt"},
            "is_baseline": False,
        },
    ).json()["id"]
    resp = client.post(_COMPARE_URL, json={"run_ids": [run1_id, run2_id]})
    assert resp.status_code == 200
    baseline_delta = resp.json()["deltas"][0]
    assert abs(baseline_delta["irr_delta"]) < 1e-8
    assert abs(baseline_delta["gross_profit_delta"]) < 1e-8
    assert abs(baseline_delta["roi_delta"]) < 1e-8


def test_compare_financial_runs_irr_delta_positive_for_price_uplift(client: TestClient):
    scenario_id = _create_scenario(client)
    run1_id = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD).json()["id"]
    run2_id = client.post(
        _runs_url(scenario_id),
        json={
            "assumptions": {**_VALID_ASSUMPTIONS, "pricing_uplift_pct": 0.20, "label": "High Price"},
            "is_baseline": False,
        },
    ).json()["id"]
    resp = client.post(_COMPARE_URL, json={"run_ids": [run1_id, run2_id]})
    assert resp.status_code == 200
    alt_delta = resp.json()["deltas"][1]
    assert alt_delta["irr_delta"] > 0


def test_compare_financial_runs_irr_delta_negative_for_cost_inflation(client: TestClient):
    scenario_id = _create_scenario(client)
    run1_id = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD).json()["id"]
    run2_id = client.post(
        _runs_url(scenario_id),
        json={
            "assumptions": {
                **_VALID_ASSUMPTIONS,
                "cost_inflation_pct": 0.25,
                "label": "High Cost",
            },
            "is_baseline": False,
        },
    ).json()["id"]
    resp = client.post(_COMPARE_URL, json={"run_ids": [run1_id, run2_id]})
    assert resp.status_code == 200
    alt_delta = resp.json()["deltas"][1]
    assert alt_delta["irr_delta"] < 0


def test_compare_financial_runs_three_scenarios(client: TestClient):
    scenario_id = _create_scenario(client)
    run1_id = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD).json()["id"]
    run2_id = client.post(
        _runs_url(scenario_id),
        json={
            "assumptions": {**_VALID_ASSUMPTIONS, "pricing_uplift_pct": 0.05, "label": "Price +5%"},
            "is_baseline": False,
        },
    ).json()["id"]
    run3_id = client.post(
        _runs_url(scenario_id),
        json={
            "assumptions": {**_VALID_ASSUMPTIONS, "cost_inflation_pct": 0.10, "label": "Cost +10%"},
            "is_baseline": False,
        },
    ).json()["id"]
    resp = client.post(_COMPARE_URL, json={"run_ids": [run1_id, run2_id, run3_id]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["runs"]) == 3
    assert len(data["deltas"]) == 3


def test_compare_financial_runs_missing_run_id(client: TestClient):
    scenario_id = _create_scenario(client)
    run1_id = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD).json()["id"]
    resp = client.post(_COMPARE_URL, json={"run_ids": [run1_id, "no-such-run"]})
    assert resp.status_code == 404


def test_compare_financial_runs_requires_at_least_two(client: TestClient):
    scenario_id = _create_scenario(client)
    run1_id = client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD).json()["id"]
    resp = client.post(_COMPARE_URL, json={"run_ids": [run1_id]})
    assert resp.status_code == 422


def test_compare_financial_runs_empty_list(client: TestClient):
    resp = client.post(_COMPARE_URL, json={"run_ids": []})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Regression: existing scenario endpoints unaffected
# ---------------------------------------------------------------------------


def test_existing_scenario_endpoints_still_work(client: TestClient):
    """Creating financial runs must not break existing scenario operations."""
    scenario_id = _create_scenario(client)
    # Create a financial run
    client.post(_runs_url(scenario_id), json=_VALID_RUN_PAYLOAD)
    # Existing endpoints must still work correctly
    get_resp = client.get(f"{_SCENARIOS_BASE}/{scenario_id}")
    assert get_resp.status_code == 200
    list_resp = client.get(_SCENARIOS_BASE)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
