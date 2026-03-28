"""
Tests for the Release Strategy Simulation Engine (PR-V7-04).

Validates:
  POST /projects/{id}/simulate-strategy
    - HTTP contract (200 on valid project, 404 on missing project)
    - Response schema shape — all required fields present
    - IRR recalculation correct (with feasibility baseline)
    - Fallback to default assumptions when no feasibility baseline
    - price_adjustment_pct increases / decreases simulated GDV correctly
    - phase_delay_months extends / compresses dev period correctly
    - release_strategy 'hold' extends period by 10%
    - release_strategy 'accelerate' compresses period by 10%
    - release_strategy 'maintain' leaves period unchanged
    - irr_delta computed correctly
    - risk_score classification: low / medium / high
    - cashflow_delay_months is correct
    - npv field is present and numeric
    - baseline values echoed in response
    - source record immutability (no feasibility data mutated)
    - Auth requirement (401 when unauthenticated)

  POST /projects/{id}/simulate-strategies
    - HTTP contract (200 on valid project, 404 on missing project)
    - Response schema shape
    - Results sorted by IRR descending
    - best_scenario_label is label of highest-IRR scenario
    - Multiple scenarios produce independent results
    - Auth requirement (401 when unauthenticated)
"""

import math
from typing import Optional

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _create_project(
    client: TestClient, code: str = "PRJ-SIM", name: str = "Simulation Project"
) -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_feasibility_run(
    client: TestClient,
    project_id: str,
    scenario_name: str = "Base Case",
    sellable_area: float = 1000.0,
    avg_price: float = 3000.0,
    construction_cost: float = 800.0,
    dev_period_months: int = 24,
) -> str:
    """Create a feasibility run and return its ID."""
    resp = client.post(
        "/api/v1/feasibility/runs",
        json={
            "project_id": project_id,
            "scenario_name": scenario_name,
            "scenario_type": "base",
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]

    # Define assumptions
    resp = client.post(
        f"/api/v1/feasibility/runs/{run_id}/assumptions",
        json={
            "sellable_area_sqm": sellable_area,
            "avg_sale_price_per_sqm": avg_price,
            "construction_cost_per_sqm": construction_cost,
            "soft_cost_ratio": 0.10,
            "finance_cost_ratio": 0.05,
            "sales_cost_ratio": 0.03,
            "development_period_months": dev_period_months,
        },
    )
    assert resp.status_code in (200, 201), resp.text

    # Calculate
    resp = client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")
    assert resp.status_code == 200, resp.text

    return run_id


def _base_scenario_input(
    price_pct: float = 0.0,
    delay_months: int = 0,
    strategy: str = "maintain",
    label: Optional[str] = None,
) -> dict:
    data: dict = {
        "price_adjustment_pct": price_pct,
        "phase_delay_months": delay_months,
        "release_strategy": strategy,
    }
    if label is not None:
        data["label"] = label
    return data


# ---------------------------------------------------------------------------
# POST /projects/{id}/simulate-strategy — HTTP contract
# ---------------------------------------------------------------------------


def test_simulate_strategy_returns_200_for_valid_project(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-200")
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200, resp.text


def test_simulate_strategy_returns_404_for_missing_project(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/projects/nonexistent-project-id/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 404


def test_simulate_strategy_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.post(
        "/api/v1/projects/any-project/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Response schema shape
# ---------------------------------------------------------------------------


def test_simulate_strategy_response_shape(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-SHAPE")
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "project_id" in data
    assert "project_name" in data
    assert "has_feasibility_baseline" in data
    assert "result" in data

    result = data["result"]
    for field in (
        "price_adjustment_pct",
        "phase_delay_months",
        "release_strategy",
        "simulated_gdv",
        "simulated_dev_period_months",
        "irr",
        "npv",
        "cashflow_delay_months",
        "risk_score",
    ):
        assert field in result, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# has_feasibility_baseline flag
# ---------------------------------------------------------------------------


def test_simulate_strategy_no_baseline_flag(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-NOFEAS")
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_feasibility_baseline"] is False


def test_simulate_strategy_with_baseline_flag(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-FEAS")
    _create_feasibility_run(client, project_id)
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_feasibility_baseline"] is True


# ---------------------------------------------------------------------------
# Price adjustment correctness
# ---------------------------------------------------------------------------


def test_price_increase_raises_simulated_gdv(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-PRICE-UP")
    _create_feasibility_run(client, project_id, avg_price=3000.0)

    resp_base = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=0.0)},
    )
    resp_up = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=5.0)},
    )
    assert resp_base.status_code == 200
    assert resp_up.status_code == 200

    base_gdv = resp_base.json()["result"]["simulated_gdv"]
    up_gdv = resp_up.json()["result"]["simulated_gdv"]
    assert up_gdv == pytest.approx(base_gdv * 1.05, rel=1e-4)


def test_price_decrease_lowers_simulated_gdv(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-PRICE-DN")
    _create_feasibility_run(client, project_id, avg_price=3000.0)

    resp_base = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=0.0)},
    )
    resp_dn = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=-8.0)},
    )
    assert resp_base.status_code == 200
    assert resp_dn.status_code == 200

    base_gdv = resp_base.json()["result"]["simulated_gdv"]
    dn_gdv = resp_dn.json()["result"]["simulated_gdv"]
    assert dn_gdv == pytest.approx(base_gdv * 0.92, rel=1e-4)


def test_price_increase_raises_irr(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-IRR-UP")
    _create_feasibility_run(client, project_id, avg_price=3000.0)

    resp_base = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=0.0)},
    )
    resp_up = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=10.0)},
    )
    base_irr = resp_base.json()["result"]["irr"]
    up_irr = resp_up.json()["result"]["irr"]
    assert up_irr > base_irr


# ---------------------------------------------------------------------------
# Phase delay correctness
# ---------------------------------------------------------------------------


def test_phase_delay_extends_dev_period(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-DELAY")
    _create_feasibility_run(client, project_id, dev_period_months=24)

    resp_base = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(delay_months=0)},
    )
    resp_delayed = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(delay_months=6)},
    )
    assert resp_base.status_code == 200
    assert resp_delayed.status_code == 200

    base_period = resp_base.json()["result"]["simulated_dev_period_months"]
    delayed_period = resp_delayed.json()["result"]["simulated_dev_period_months"]
    assert delayed_period == base_period + 6


def test_phase_delay_increases_cashflow_delay_months(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-CF-DELAY")
    _create_feasibility_run(client, project_id, dev_period_months=24)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(delay_months=3)},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["cashflow_delay_months"] == 3


def test_no_delay_gives_zero_cashflow_delay(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-CF-ZERO")
    _create_feasibility_run(client, project_id, dev_period_months=24)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(delay_months=0, strategy="maintain")},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["cashflow_delay_months"] == 0


# ---------------------------------------------------------------------------
# Release strategy modifiers
# ---------------------------------------------------------------------------


def test_hold_strategy_extends_dev_period(client: TestClient) -> None:
    """hold adds +10% to the (base + delay) period."""
    project_id = _create_project(client, code="SIM-HOLD")
    _create_feasibility_run(client, project_id, dev_period_months=20)

    resp_maintain = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(delay_months=0, strategy="maintain")},
    )
    resp_hold = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(delay_months=0, strategy="hold")},
    )
    maintain_period = resp_maintain.json()["result"]["simulated_dev_period_months"]
    hold_period = resp_hold.json()["result"]["simulated_dev_period_months"]
    # 20 * 1.10 = 22
    assert hold_period == math.ceil(maintain_period * 1.10)


def test_accelerate_strategy_compresses_dev_period(client: TestClient) -> None:
    """accelerate reduces by 10% of the (base + delay) period."""
    project_id = _create_project(client, code="SIM-ACCEL")
    _create_feasibility_run(client, project_id, dev_period_months=20)

    resp_maintain = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(delay_months=0, strategy="maintain")},
    )
    resp_accel = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(delay_months=0, strategy="accelerate")},
    )
    maintain_period = resp_maintain.json()["result"]["simulated_dev_period_months"]
    accel_period = resp_accel.json()["result"]["simulated_dev_period_months"]
    # 20 * 0.90 = 18
    assert accel_period == math.ceil(maintain_period * 0.90)


def test_maintain_strategy_does_not_change_period(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-MAINT")
    _create_feasibility_run(client, project_id, dev_period_months=24)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(delay_months=0, strategy="maintain")},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["simulated_dev_period_months"] == 24


# ---------------------------------------------------------------------------
# IRR delta and risk score
# ---------------------------------------------------------------------------


def test_irr_delta_positive_when_price_increased(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-DELTA-POS")
    _create_feasibility_run(client, project_id, avg_price=3000.0, dev_period_months=24)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=10.0)},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["irr_delta"] is not None
    assert result["irr_delta"] > 0


def test_irr_delta_negative_when_price_decreased(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-DELTA-NEG")
    _create_feasibility_run(client, project_id, avg_price=3000.0, dev_period_months=24)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=-20.0)},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["irr_delta"] is not None
    assert result["irr_delta"] < 0


def test_risk_score_high_when_irr_drops(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-RISK-HIGH")
    _create_feasibility_run(client, project_id, avg_price=3000.0, dev_period_months=24)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=-30.0)},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    # Large price drop → large negative irr_delta → high risk
    assert result["risk_score"] == "high"


def test_risk_score_low_when_irr_improves_significantly(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-RISK-LOW")
    _create_feasibility_run(
        client, project_id, avg_price=3000.0, dev_period_months=24, sellable_area=1000.0
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=20.0)},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    # Large price increase → large positive irr_delta → low risk
    assert result["risk_score"] == "low"


def test_risk_score_medium_when_no_baseline(client: TestClient) -> None:
    """Without a feasibility baseline, irr_delta is None → medium risk."""
    project_id = _create_project(client, code="SIM-RISK-MED")

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["irr_delta"] is None
    assert result["risk_score"] == "medium"


# ---------------------------------------------------------------------------
# Baseline values echoed
# ---------------------------------------------------------------------------


def test_baseline_values_echoed_in_result(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-ECHO")
    _create_feasibility_run(
        client, project_id, avg_price=3000.0, dev_period_months=24, sellable_area=500.0
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]

    assert result["baseline_gdv"] is not None
    assert result["baseline_total_cost"] is not None
    assert result["baseline_dev_period_months"] == 24
    assert result["baseline_irr"] is not None


def test_baseline_values_none_when_no_feasibility_run(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-NO-BASELINE")

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]

    assert result["baseline_gdv"] is None
    assert result["baseline_total_cost"] is None
    assert result["baseline_dev_period_months"] is None
    assert result["baseline_irr"] is None


# ---------------------------------------------------------------------------
# NPV field
# ---------------------------------------------------------------------------


def test_npv_is_numeric(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-NPV")
    _create_feasibility_run(client, project_id)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert isinstance(result["npv"], (int, float))


def test_npv_positive_for_profitable_project(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-NPV-POS")
    # High avg price → profitable → positive NPV
    _create_feasibility_run(client, project_id, avg_price=5000.0, dev_period_months=12)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["npv"] > 0


# ---------------------------------------------------------------------------
# Source record immutability
# ---------------------------------------------------------------------------


def test_simulate_strategy_does_not_mutate_feasibility_run(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-IMMUT")
    run_id = _create_feasibility_run(client, project_id, avg_price=3000.0)

    # Get original feasibility result
    resp_before = client.get(f"/api/v1/feasibility/runs/{run_id}")
    assert resp_before.status_code == 200
    data_before = resp_before.json()

    # Run simulation with price change
    client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=20.0)},
    )

    # Verify feasibility run is unchanged
    resp_after = client.get(f"/api/v1/feasibility/runs/{run_id}")
    assert resp_after.status_code == 200
    data_after = resp_after.json()

    assert data_before["id"] == data_after["id"]
    assert data_before["status"] == data_after["status"]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_price_pct_out_of_range_returns_422(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-VAL")
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(price_pct=99.0)},  # > 50 → invalid
    )
    assert resp.status_code == 422


def test_invalid_release_strategy_returns_422(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-VAL2")
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={
            "scenario": {
                "price_adjustment_pct": 0.0,
                "phase_delay_months": 0,
                "release_strategy": "unknown_strategy",
            }
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /projects/{id}/simulate-strategies — HTTP contract
# ---------------------------------------------------------------------------


def test_simulate_strategies_returns_200(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-MULTI-200")
    _create_feasibility_run(client, project_id)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategies",
        json={
            "scenarios": [
                _base_scenario_input(price_pct=0.0, label="Base"),
                _base_scenario_input(price_pct=5.0, label="Optimistic"),
            ]
        },
    )
    assert resp.status_code == 200, resp.text


def test_simulate_strategies_returns_404_for_missing_project(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/projects/nonexistent/simulate-strategies",
        json={"scenarios": [_base_scenario_input()]},
    )
    assert resp.status_code == 404


def test_simulate_strategies_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.post(
        "/api/v1/projects/any-project/simulate-strategies",
        json={"scenarios": [_base_scenario_input()]},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Multi-scenario response schema
# ---------------------------------------------------------------------------


def test_simulate_strategies_response_shape(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-MULTI-SHAPE")
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategies",
        json={
            "scenarios": [
                _base_scenario_input(label="A"),
                _base_scenario_input(price_pct=5.0, label="B"),
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "project_id" in data
    assert "project_name" in data
    assert "has_feasibility_baseline" in data
    assert "results" in data
    assert len(data["results"]) == 2


# ---------------------------------------------------------------------------
# Results sorted by IRR descending
# ---------------------------------------------------------------------------


def test_simulate_strategies_sorted_by_irr_descending(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-SORTED")
    _create_feasibility_run(client, project_id, avg_price=3000.0, dev_period_months=24)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategies",
        json={
            "scenarios": [
                _base_scenario_input(price_pct=-10.0, label="Pessimistic"),
                _base_scenario_input(price_pct=0.0, label="Base"),
                _base_scenario_input(price_pct=10.0, label="Optimistic"),
            ]
        },
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    irrs = [r["irr"] for r in results]
    assert irrs == sorted(irrs, reverse=True), "Results should be sorted by IRR descending"


def test_simulate_strategies_best_scenario_label(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-BEST")
    _create_feasibility_run(client, project_id, avg_price=3000.0, dev_period_months=24)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategies",
        json={
            "scenarios": [
                _base_scenario_input(price_pct=-5.0, label="Low"),
                _base_scenario_input(price_pct=10.0, label="High"),
                _base_scenario_input(price_pct=0.0, label="Mid"),
            ]
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Highest-IRR scenario is the one with +10% price
    assert data["best_scenario_label"] == "High"


def test_simulate_strategies_independent_results(client: TestClient) -> None:
    """Each scenario should produce an independent result."""
    project_id = _create_project(client, code="SIM-INDEP")
    _create_feasibility_run(client, project_id, avg_price=3000.0, dev_period_months=24)

    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategies",
        json={
            "scenarios": [
                _base_scenario_input(price_pct=0.0),
                _base_scenario_input(price_pct=5.0),
                _base_scenario_input(price_pct=10.0),
            ]
        },
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    # All GDV values should be distinct
    gdvs = [r["simulated_gdv"] for r in results]
    assert len(set(gdvs)) == 3, "Each scenario should have a distinct simulated GDV"


def test_simulate_strategies_empty_list_returns_422(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-EMPTY")
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategies",
        json={"scenarios": []},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Label passthrough
# ---------------------------------------------------------------------------


def test_scenario_label_echoed_in_result(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-LABEL")
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input(label="My Scenario")},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["label"] == "My Scenario"


def test_scenario_label_none_when_not_provided(client: TestClient) -> None:
    project_id = _create_project(client, code="SIM-NOLABEL")
    resp = client.post(
        f"/api/v1/projects/{project_id}/simulate-strategy",
        json={"scenario": _base_scenario_input()},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["label"] is None
