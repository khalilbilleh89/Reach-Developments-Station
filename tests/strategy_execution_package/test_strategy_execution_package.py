"""
Tests for the Strategy Execution Package Generator (PR-V7-07).

Validates:
  GET /projects/{id}/strategy-execution-package
    - HTTP contract (200, 404, auth required)
    - Response schema shape — all required fields present
    - Execution readiness classification
    - Action sequence generation (step numbering, action types)
    - Dependency classification (cleared vs blocked)
    - Caution classification (severity and presence)
    - Missing baseline handling (blocked_by_dependency)
    - High-risk handling (caution_required)
    - Insufficient data handling (no strategy generated)
    - Read-only behavior — source records unchanged after call
    - Deterministic output (same inputs → same output)

  GET /portfolio/execution-packages
    - HTTP contract (200, auth required)
    - Response schema shape
    - Empty portfolio returns valid null-safe response
    - Summary counts accurate
    - top_ready_actions contains at most 5 entries
    - top_blocked_actions contains at most 5 entries
    - top_high_risk_packages contains at most 5 entries
    - Portfolio packages ordered by readiness priority
    - Read-only behavior

  Pure unit tests (no DB/HTTP):
    - _determine_execution_readiness classifications
    - _build_dependencies cleared vs blocked
    - _build_cautions severity levels
    - _build_actions sequence rules
    - _rank_portfolio_cards ordering
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.strategy_execution_package.service import (
    _build_actions,
    _build_cautions,
    _build_dependencies,
    _determine_execution_readiness,
    _rank_portfolio_cards,
)
from app.modules.strategy_execution_package.schemas import PortfolioPackagedInterventionCard
from app.modules.release_simulation.schemas import SimulationResult


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _create_project(
    client: TestClient,
    code: str = "SEP-001",
    name: str = "Execution Package Project",
) -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_feasibility_run(
    client: TestClient,
    project_id: str,
    sellable_area: float = 1000.0,
    avg_price: float = 3000.0,
    construction_cost: float = 800.0,
    dev_period_months: int = 24,
) -> str:
    resp = client.post(
        "/api/v1/feasibility/runs",
        json={
            "project_id": project_id,
            "scenario_name": "Base Case",
            "scenario_type": "base",
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]

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

    resp = client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")
    assert resp.status_code == 200, resp.text

    return run_id


def _make_sim_result(
    irr: float = 0.15,
    risk_score: str = "medium",
    price_adjustment_pct: float = 5.0,
    phase_delay_months: int = 3,
    release_strategy: str = "maintain",
) -> SimulationResult:
    """Create a minimal SimulationResult for unit tests."""
    return SimulationResult(
        irr=irr,
        npv=100000.0,
        risk_score=risk_score,
        price_adjustment_pct=price_adjustment_pct,
        phase_delay_months=phase_delay_months,
        release_strategy=release_strategy,
        cashflow_delay_months=phase_delay_months,
        irr_delta=0.01,
        label=f"{price_adjustment_pct:+.0f}% / {phase_delay_months}mo / {release_strategy}",
        total_revenue=1000000.0,
        total_cost=800000.0,
        simulated_gdv=1000000.0,
        simulated_dev_period_months=24,
    )


# ---------------------------------------------------------------------------
# Unit tests — _determine_execution_readiness
# ---------------------------------------------------------------------------


def test_readiness_insufficient_data_when_no_best() -> None:
    result = _determine_execution_readiness(None, has_feasibility_baseline=True)
    assert result == "insufficient_data"


def test_readiness_insufficient_data_no_best_no_baseline() -> None:
    result = _determine_execution_readiness(None, has_feasibility_baseline=False)
    assert result == "insufficient_data"


def test_readiness_blocked_when_no_baseline() -> None:
    best = _make_sim_result(risk_score="low")
    result = _determine_execution_readiness(best, has_feasibility_baseline=False)
    assert result == "blocked_by_dependency"


def test_readiness_caution_when_high_risk_with_baseline() -> None:
    best = _make_sim_result(risk_score="high")
    result = _determine_execution_readiness(best, has_feasibility_baseline=True)
    assert result == "caution_required"


def test_readiness_ready_when_low_risk_with_baseline() -> None:
    best = _make_sim_result(risk_score="low")
    result = _determine_execution_readiness(best, has_feasibility_baseline=True)
    assert result == "ready_for_review"


def test_readiness_ready_when_medium_risk_with_baseline() -> None:
    best = _make_sim_result(risk_score="medium")
    result = _determine_execution_readiness(best, has_feasibility_baseline=True)
    assert result == "ready_for_review"


def test_readiness_blocked_takes_priority_over_caution() -> None:
    # High risk + no baseline → blocked (baseline check comes first in hierarchy)
    best = _make_sim_result(risk_score="high")
    result = _determine_execution_readiness(best, has_feasibility_baseline=False)
    assert result == "blocked_by_dependency"


# ---------------------------------------------------------------------------
# Unit tests — _build_dependencies
# ---------------------------------------------------------------------------


def test_dependencies_both_cleared() -> None:
    best = _make_sim_result()
    deps = _build_dependencies(best, has_feasibility_baseline=True)
    assert len(deps) == 2
    for dep in deps:
        assert dep.dependency_status == "cleared"
        assert dep.blocking_reason is None


def test_dependencies_baseline_blocked() -> None:
    best = _make_sim_result()
    deps = _build_dependencies(best, has_feasibility_baseline=False)
    baseline_dep = next(d for d in deps if d.dependency_type == "feasibility_baseline")
    assert baseline_dep.dependency_status == "blocked"
    assert baseline_dep.blocking_reason is not None


def test_dependencies_strategy_blocked_when_no_best() -> None:
    deps = _build_dependencies(None, has_feasibility_baseline=True)
    strategy_dep = next(d for d in deps if d.dependency_type == "strategy_data")
    assert strategy_dep.dependency_status == "blocked"
    assert strategy_dep.blocking_reason is not None


def test_dependencies_both_blocked() -> None:
    deps = _build_dependencies(None, has_feasibility_baseline=False)
    assert all(d.dependency_status == "blocked" for d in deps)


# ---------------------------------------------------------------------------
# Unit tests — _build_cautions
# ---------------------------------------------------------------------------


def test_cautions_none_when_low_risk_with_baseline() -> None:
    best = _make_sim_result(risk_score="low", phase_delay_months=0)
    cautions = _build_cautions(best, has_feasibility_baseline=True)
    assert len(cautions) == 0


def test_cautions_high_risk_caution_present() -> None:
    best = _make_sim_result(risk_score="high")
    cautions = _build_cautions(best, has_feasibility_baseline=True)
    titles = [c.caution_title for c in cautions]
    assert any("High-Risk" in t for t in titles)
    assert all(c.severity in ("high", "medium", "low") for c in cautions)


def test_cautions_medium_risk_caution_present() -> None:
    best = _make_sim_result(risk_score="medium")
    cautions = _build_cautions(best, has_feasibility_baseline=True)
    titles = [c.caution_title for c in cautions]
    assert any("Medium-Risk" in t for t in titles)


def test_cautions_missing_baseline_caution_high_severity() -> None:
    best = _make_sim_result(risk_score="low")
    cautions = _build_cautions(best, has_feasibility_baseline=False)
    baseline_caution = next(c for c in cautions if "Baseline" in c.caution_title)
    assert baseline_caution.severity == "high"


def test_cautions_extended_delay_adds_medium_caution() -> None:
    best = _make_sim_result(risk_score="low", phase_delay_months=6)
    cautions = _build_cautions(best, has_feasibility_baseline=True)
    delay_caution = next((c for c in cautions if "Delay" in c.caution_title), None)
    assert delay_caution is not None
    assert delay_caution.severity == "medium"


def test_cautions_short_delay_no_extra_caution() -> None:
    best = _make_sim_result(risk_score="low", phase_delay_months=3)
    cautions = _build_cautions(best, has_feasibility_baseline=True)
    # delay <= 3 should not add a delay caution
    delay_caution = next((c for c in cautions if "Delay" in c.caution_title), None)
    assert delay_caution is None


def test_cautions_no_best_no_extra_cautions_beyond_baseline() -> None:
    cautions = _build_cautions(None, has_feasibility_baseline=False)
    # Only the missing baseline caution — no risk caution possible without best
    assert len(cautions) == 1
    assert cautions[0].severity == "high"


# ---------------------------------------------------------------------------
# Unit tests — _build_actions
# ---------------------------------------------------------------------------


def test_actions_insufficient_data_returns_single_resolution_step() -> None:
    actions = _build_actions(None, has_feasibility_baseline=True)
    assert len(actions) == 1
    assert actions[0].step_number == 1
    assert actions[0].action_type == "baseline_dependency_review"
    assert actions[0].review_required is True


def test_actions_minimal_strategy_includes_simulation_review() -> None:
    # Low risk, no price signal, no delay, maintain strategy
    best = _make_sim_result(
        risk_score="low",
        price_adjustment_pct=0.0,
        phase_delay_months=0,
        release_strategy="maintain",
    )
    actions = _build_actions(best, has_feasibility_baseline=True)
    types = [a.action_type for a in actions]
    assert "simulation_review" in types


def test_actions_step_numbers_sequential() -> None:
    best = _make_sim_result(
        risk_score="high",
        price_adjustment_pct=5.0,
        phase_delay_months=3,
        release_strategy="maintain",
    )
    actions = _build_actions(best, has_feasibility_baseline=True)
    for i, action in enumerate(actions, start=1):
        assert action.step_number == i


def test_actions_no_baseline_adds_dependency_review_first() -> None:
    best = _make_sim_result(risk_score="low", price_adjustment_pct=0.0, phase_delay_months=0)
    actions = _build_actions(best, has_feasibility_baseline=False)
    assert actions[0].action_type == "baseline_dependency_review"
    assert actions[0].step_number == 1


def test_actions_significant_price_adj_adds_pricing_step() -> None:
    best = _make_sim_result(
        risk_score="medium",
        price_adjustment_pct=8.0,
        phase_delay_months=0,
        release_strategy="maintain",
    )
    actions = _build_actions(best, has_feasibility_baseline=True)
    types = [a.action_type for a in actions]
    assert "pricing_update_preparation" in types


def test_actions_small_price_adj_no_pricing_step() -> None:
    best = _make_sim_result(
        risk_score="low",
        price_adjustment_pct=0.0,
        phase_delay_months=0,
        release_strategy="maintain",
    )
    actions = _build_actions(best, has_feasibility_baseline=True)
    types = [a.action_type for a in actions]
    assert "pricing_update_preparation" not in types


def test_actions_phase_delay_adds_phasing_step() -> None:
    best = _make_sim_result(
        risk_score="low",
        price_adjustment_pct=0.0,
        phase_delay_months=3,
        release_strategy="maintain",
    )
    actions = _build_actions(best, has_feasibility_baseline=True)
    types = [a.action_type for a in actions]
    assert "phase_release_preparation" in types


def test_actions_hold_strategy_adds_holdback_step() -> None:
    best = _make_sim_result(
        risk_score="low",
        price_adjustment_pct=0.0,
        phase_delay_months=0,
        release_strategy="hold",
    )
    actions = _build_actions(best, has_feasibility_baseline=True)
    types = [a.action_type for a in actions]
    assert "holdback_validation" in types


def test_actions_accelerate_strategy_adds_release_readiness_step() -> None:
    best = _make_sim_result(
        risk_score="low",
        price_adjustment_pct=0.0,
        phase_delay_months=0,
        release_strategy="accelerate",
    )
    actions = _build_actions(best, has_feasibility_baseline=True)
    # accelerate uses phase_release_preparation action_type with "Validate Release Readiness"
    readiness_steps = [a for a in actions if "Release Readiness" in a.action_title]
    assert len(readiness_steps) >= 1


def test_actions_high_risk_adds_executive_review_last() -> None:
    best = _make_sim_result(
        risk_score="high",
        price_adjustment_pct=5.0,
        phase_delay_months=3,
        release_strategy="maintain",
    )
    actions = _build_actions(best, has_feasibility_baseline=True)
    assert actions[-1].action_type == "executive_review"


def test_actions_no_executive_review_for_low_risk() -> None:
    best = _make_sim_result(
        risk_score="low",
        price_adjustment_pct=0.0,
        phase_delay_months=0,
        release_strategy="maintain",
    )
    actions = _build_actions(best, has_feasibility_baseline=True)
    types = [a.action_type for a in actions]
    assert "executive_review" not in types


# ---------------------------------------------------------------------------
# Unit tests — _rank_portfolio_cards
# ---------------------------------------------------------------------------


def _make_portfolio_card(
    project_id: str,
    project_name: str,
    execution_readiness: str,
    urgency_score: int,
) -> PortfolioPackagedInterventionCard:
    return PortfolioPackagedInterventionCard(
        project_id=project_id,
        project_name=project_name,
        recommended_strategy=None,
        intervention_priority="monitor_closely",
        intervention_type="monitor_only",
        execution_readiness=execution_readiness,
        has_feasibility_baseline=False,
        requires_manual_review=False,
        next_best_action=None,
        blockers=[],
        urgency_score=urgency_score,
        expected_impact="—",
    )


def test_rank_cards_ready_before_caution_before_blocked_before_no_data() -> None:
    cards = [
        _make_portfolio_card("d", "D", "insufficient_data", 90),
        _make_portfolio_card("c", "C", "blocked_by_dependency", 70),
        _make_portfolio_card("b", "B", "caution_required", 80),
        _make_portfolio_card("a", "A", "ready_for_review", 60),
    ]
    ranked = _rank_portfolio_cards(cards)
    assert ranked[0].project_id == "a"
    assert ranked[1].project_id == "b"
    assert ranked[2].project_id == "c"
    assert ranked[3].project_id == "d"


def test_rank_cards_urgency_score_desc_as_secondary_key() -> None:
    cards = [
        _make_portfolio_card("low", "Low", "ready_for_review", 20),
        _make_portfolio_card("high", "High", "ready_for_review", 80),
    ]
    ranked = _rank_portfolio_cards(cards)
    assert ranked[0].project_id == "high"
    assert ranked[1].project_id == "low"


def test_rank_cards_project_name_asc_as_tie_break() -> None:
    cards = [
        _make_portfolio_card("z", "Zebra", "ready_for_review", 50),
        _make_portfolio_card("a", "Apple", "ready_for_review", 50),
    ]
    ranked = _rank_portfolio_cards(cards)
    assert ranked[0].project_id == "a"
    assert ranked[1].project_id == "z"


# ---------------------------------------------------------------------------
# HTTP integration tests — project execution package
# ---------------------------------------------------------------------------


def test_project_execution_package_404_unknown_project(client: TestClient) -> None:
    resp = client.get("/api/v1/projects/nonexistent-id/strategy-execution-package")
    assert resp.status_code == 404


def test_project_execution_package_401_without_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/projects/some-id/strategy-execution-package")
    assert resp.status_code == 401


def test_project_execution_package_response_shape(client: TestClient) -> None:
    project_id = _create_project(client, code="SEP-SHAPE", name="Shape Test Project")
    resp = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    assert resp.status_code == 200

    data = resp.json()
    assert "project_id" in data
    assert "project_name" in data
    assert "has_feasibility_baseline" in data
    assert "execution_readiness" in data
    assert "summary" in data
    assert "actions" in data
    assert "dependencies" in data
    assert "cautions" in data
    assert "supporting_metrics" in data
    assert "expected_impact" in data
    assert "requires_manual_review" in data


def test_project_execution_package_no_baseline_is_blocked(client: TestClient) -> None:
    project_id = _create_project(client, code="SEP-NOBASE", name="No Baseline Project")
    resp = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    assert resp.status_code == 200

    data = resp.json()
    assert data["has_feasibility_baseline"] is False
    assert data["execution_readiness"] in ("insufficient_data", "blocked_by_dependency")


def test_project_execution_package_with_baseline_has_strategy(client: TestClient) -> None:
    project_id = _create_project(client, code="SEP-BASE", name="Baseline Project")
    _create_feasibility_run(client, project_id)

    resp = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    assert resp.status_code == 200

    data = resp.json()
    assert data["has_feasibility_baseline"] is True
    assert data["execution_readiness"] in (
        "ready_for_review",
        "caution_required",
        "blocked_by_dependency",
    )
    assert len(data["actions"]) >= 1


def test_project_execution_package_dependencies_present(client: TestClient) -> None:
    project_id = _create_project(client, code="SEP-DEPS", name="Deps Test Project")
    resp = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    assert resp.status_code == 200

    data = resp.json()
    dep_types = [d["dependency_type"] for d in data["dependencies"]]
    assert "feasibility_baseline" in dep_types
    assert "strategy_data" in dep_types


def test_project_execution_package_actions_sequential(client: TestClient) -> None:
    project_id = _create_project(client, code="SEP-SEQ", name="Sequence Test Project")
    _create_feasibility_run(client, project_id)

    resp = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    assert resp.status_code == 200

    data = resp.json()
    actions = data["actions"]
    assert len(actions) >= 1
    for i, action in enumerate(actions, start=1):
        assert action["step_number"] == i


def test_project_execution_package_action_fields_present(client: TestClient) -> None:
    project_id = _create_project(client, code="SEP-AFIELD", name="Action Fields Project")
    _create_feasibility_run(client, project_id)

    resp = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    assert resp.status_code == 200

    data = resp.json()
    for action in data["actions"]:
        assert "step_number" in action
        assert "action_type" in action
        assert "action_title" in action
        assert "action_description" in action
        assert "target_area" in action
        assert "urgency" in action
        assert "review_required" in action


def test_project_execution_package_cautions_have_severity(client: TestClient) -> None:
    project_id = _create_project(client, code="SEP-CAUT", name="Caution Test Project")
    resp = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    assert resp.status_code == 200

    data = resp.json()
    for caution in data["cautions"]:
        assert caution["severity"] in ("high", "medium", "low")
        assert "caution_title" in caution
        assert "caution_description" in caution


def test_project_execution_package_read_only(client: TestClient) -> None:
    """Source records must not be modified by the execution package endpoint."""
    project_id = _create_project(client, code="SEP-RO", name="Read Only Test")
    _create_feasibility_run(client, project_id)

    client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")

    # Feasibility run still accessible and unchanged.
    runs_resp = client.get(f"/api/v1/feasibility/runs?project_id={project_id}")
    assert runs_resp.status_code == 200


def test_project_execution_package_deterministic(client: TestClient) -> None:
    """Same project state must produce the same execution package on repeated calls."""
    project_id = _create_project(client, code="SEP-DET", name="Deterministic Test")
    _create_feasibility_run(client, project_id)

    resp1 = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    resp2 = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json()["execution_readiness"] == resp2.json()["execution_readiness"]
    assert len(resp1.json()["actions"]) == len(resp2.json()["actions"])


def test_project_execution_package_supporting_metrics_present(client: TestClient) -> None:
    project_id = _create_project(client, code="SEP-MET", name="Metrics Test")
    _create_feasibility_run(client, project_id)

    resp = client.get(f"/api/v1/projects/{project_id}/strategy-execution-package")
    assert resp.status_code == 200

    metrics = resp.json()["supporting_metrics"]
    assert "best_irr" in metrics
    assert "risk_score" in metrics
    assert "price_adjustment_pct" in metrics
    assert "phase_delay_months" in metrics
    assert "release_strategy" in metrics


# ---------------------------------------------------------------------------
# HTTP integration tests — portfolio execution packages
# ---------------------------------------------------------------------------


def test_portfolio_execution_packages_200(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200


def test_portfolio_execution_packages_401_without_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 401


def test_portfolio_execution_packages_schema_shape(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    data = resp.json()
    assert "summary" in data
    assert "top_ready_actions" in data
    assert "top_blocked_actions" in data
    assert "top_high_risk_packages" in data
    assert "packages" in data


def test_portfolio_execution_packages_summary_fields(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    summary = resp.json()["summary"]
    assert "total_projects" in summary
    assert "ready_for_review_count" in summary
    assert "blocked_count" in summary
    assert "caution_required_count" in summary
    assert "insufficient_data_count" in summary


def test_portfolio_execution_packages_empty_portfolio(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    data = resp.json()
    assert data["summary"]["total_projects"] == 0
    assert data["packages"] == []
    assert data["top_ready_actions"] == []
    assert data["top_blocked_actions"] == []
    assert data["top_high_risk_packages"] == []


def test_portfolio_execution_packages_all_projects_appear(client: TestClient) -> None:
    id1 = _create_project(client, code="PEP-001", name="Portfolio Pack 1")
    id2 = _create_project(client, code="PEP-002", name="Portfolio Pack 2")

    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    data = resp.json()
    project_ids = {p["project_id"] for p in data["packages"]}
    assert id1 in project_ids
    assert id2 in project_ids


def test_portfolio_execution_packages_summary_counts_match_packages(
    client: TestClient,
) -> None:
    _create_project(client, code="PEP-CNT1", name="Count Project 1")
    _create_project(client, code="PEP-CNT2", name="Count Project 2")

    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    data = resp.json()
    summary = data["summary"]
    packages = data["packages"]

    assert summary["total_projects"] == len(packages)
    assert (
        summary["ready_for_review_count"]
        + summary["blocked_count"]
        + summary["caution_required_count"]
        + summary["insufficient_data_count"]
        == summary["total_projects"]
    )


def test_portfolio_execution_packages_top_ready_at_most_5(client: TestClient) -> None:
    for i in range(7):
        project_id = _create_project(
            client, code=f"PEP-R{i:02d}", name=f"Ready Project {i:02d}"
        )
        _create_feasibility_run(client, project_id)

    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["top_ready_actions"]) <= 5


def test_portfolio_execution_packages_top_blocked_at_most_5(client: TestClient) -> None:
    for i in range(7):
        _create_project(client, code=f"PEP-B{i:02d}", name=f"Blocked Project {i:02d}")

    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["top_blocked_actions"]) <= 5


def test_portfolio_execution_packages_top_high_risk_at_most_5(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["top_high_risk_packages"]) <= 5


def test_portfolio_execution_packages_card_fields(client: TestClient) -> None:
    _create_project(client, code="PEP-CARD", name="Card Fields Project")

    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    data = resp.json()
    for card in data["packages"]:
        assert "project_id" in card
        assert "project_name" in card
        assert "execution_readiness" in card
        assert "intervention_priority" in card
        assert "urgency_score" in card
        assert "requires_manual_review" in card
        assert "expected_impact" in card


def test_portfolio_execution_packages_read_only(client: TestClient) -> None:
    project_id = _create_project(client, code="PEP-RO", name="Portfolio RO Test")
    _create_feasibility_run(client, project_id)

    client.get("/api/v1/portfolio/execution-packages")
    client.get("/api/v1/portfolio/execution-packages")

    # Project still accessible and unchanged.
    proj_resp = client.get(f"/api/v1/projects/{project_id}")
    assert proj_resp.status_code == 200


def test_portfolio_execution_packages_respects_project_cap(client: TestClient) -> None:
    """Portfolio endpoint must not return more than _PORTFOLIO_PROJECT_LIMIT packages."""
    from app.modules.strategy_execution_package.service import _PORTFOLIO_PROJECT_LIMIT

    resp = client.get("/api/v1/portfolio/execution-packages")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["packages"]) <= _PORTFOLIO_PROJECT_LIMIT


def test_portfolio_execution_packages_cap_value_is_50() -> None:
    """Portfolio cap constant must equal 50 to align with strategy generator."""
    from app.modules.strategy_execution_package.service import _PORTFOLIO_PROJECT_LIMIT

    assert _PORTFOLIO_PROJECT_LIMIT == 50
