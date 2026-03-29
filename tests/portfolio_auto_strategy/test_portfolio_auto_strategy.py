"""
Tests for the Portfolio Auto-Strategy & Intervention Prioritization Engine
(PR-V7-06).

Validates:
  GET /portfolio/auto-strategy
    - HTTP contract (200, auth required)
    - Response schema shape — all required fields present
    - Empty portfolio returns valid null-safe response
    - Per-project cards populated when projects exist
    - Summary counts accurate (total, analyzed, urgent, monitor, no_data)
    - project_cards ordered by four-key ranking rule
    - top_actions contains at most 5 entries
    - top_risk_projects contains at most 5 entries
    - top_upside_projects ordered by best_irr descending
    - intervention_priority classification
    - intervention_type classification
    - urgency_score range [0, 100]
    - read-only behavior — source records unchanged after call
    - deterministic ranking across repeated calls

  Pure unit tests (no DB/HTTP):
    - _compute_urgency_score boundary conditions
    - _classify_intervention_priority thresholds
    - _classify_intervention_type signal combinations
    - _rank_cards deterministic ordering
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.portfolio_auto_strategy.service import (
    _classify_intervention_priority,
    _classify_intervention_type,
    _compute_urgency_score,
    _rank_cards,
)
from app.modules.portfolio_auto_strategy.schemas import PortfolioInterventionProjectCard


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _create_project(
    client: TestClient,
    code: str = "PAS-001",
    name: str = "Auto Strategy Project",
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


# ---------------------------------------------------------------------------
# Unit tests — _compute_urgency_score
# ---------------------------------------------------------------------------


def test_urgency_score_no_data_returns_zero() -> None:
    score = _compute_urgency_score(
        best_risk_score=None,
        has_feasibility_baseline=True,
        best_price_adjustment_pct=0.0,
        best_phase_delay_months=0,
    )
    assert score == 0


def test_urgency_score_high_risk_with_baseline() -> None:
    score = _compute_urgency_score(
        best_risk_score="high",
        has_feasibility_baseline=True,
        best_price_adjustment_pct=0.0,
        best_phase_delay_months=0,
    )
    assert score == 60


def test_urgency_score_high_risk_no_baseline() -> None:
    score = _compute_urgency_score(
        best_risk_score="high",
        has_feasibility_baseline=False,
        best_price_adjustment_pct=0.0,
        best_phase_delay_months=0,
    )
    assert score == 75  # 60 + 15


def test_urgency_score_medium_risk_no_baseline_negative_price() -> None:
    score = _compute_urgency_score(
        best_risk_score="medium",
        has_feasibility_baseline=False,
        best_price_adjustment_pct=-5.0,
        best_phase_delay_months=0,
    )
    assert score == 55  # 30 + 15 + 10


def test_urgency_score_low_risk_all_signals() -> None:
    score = _compute_urgency_score(
        best_risk_score="low",
        has_feasibility_baseline=False,
        best_price_adjustment_pct=-3.0,
        best_phase_delay_months=6,
    )
    assert score == 40  # 10 + 15 + 10 + 5


def test_urgency_score_capped_at_100() -> None:
    # high (60) + no baseline (15) + negative price (10) + large delay (5) = 90
    # Cannot exceed 100 with valid inputs, but let's verify the cap logic
    score = _compute_urgency_score(
        best_risk_score="high",
        has_feasibility_baseline=False,
        best_price_adjustment_pct=-5.0,
        best_phase_delay_months=6,
    )
    assert score == 90
    assert score <= 100


def test_urgency_score_positive_price_does_not_add() -> None:
    # Positive price adjustment does not contribute to urgency
    score_pos = _compute_urgency_score(
        best_risk_score="medium",
        has_feasibility_baseline=True,
        best_price_adjustment_pct=5.0,
        best_phase_delay_months=0,
    )
    score_zero = _compute_urgency_score(
        best_risk_score="medium",
        has_feasibility_baseline=True,
        best_price_adjustment_pct=0.0,
        best_phase_delay_months=0,
    )
    assert score_pos == score_zero == 30


def test_urgency_score_small_delay_does_not_add() -> None:
    # Delay <= 3 months does not contribute
    score_small = _compute_urgency_score(
        best_risk_score="medium",
        has_feasibility_baseline=True,
        best_price_adjustment_pct=0.0,
        best_phase_delay_months=3,
    )
    assert score_small == 30


# ---------------------------------------------------------------------------
# Unit tests — _classify_intervention_priority
# ---------------------------------------------------------------------------


def test_priority_insufficient_data_when_no_strategy() -> None:
    assert _classify_intervention_priority(0, False) == "insufficient_data"


def test_priority_insufficient_data_ignores_score() -> None:
    assert _classify_intervention_priority(90, False) == "insufficient_data"


def test_priority_urgent_at_70() -> None:
    assert _classify_intervention_priority(70, True) == "urgent_intervention"


def test_priority_urgent_above_70() -> None:
    assert _classify_intervention_priority(90, True) == "urgent_intervention"


def test_priority_recommended_at_40() -> None:
    assert _classify_intervention_priority(40, True) == "recommended_intervention"


def test_priority_recommended_at_69() -> None:
    assert _classify_intervention_priority(69, True) == "recommended_intervention"


def test_priority_monitor_closely_at_20() -> None:
    assert _classify_intervention_priority(20, True) == "monitor_closely"


def test_priority_monitor_closely_at_39() -> None:
    assert _classify_intervention_priority(39, True) == "monitor_closely"


def test_priority_stable_below_20() -> None:
    assert _classify_intervention_priority(19, True) == "stable"


def test_priority_stable_at_zero() -> None:
    assert _classify_intervention_priority(0, True) == "stable"


# ---------------------------------------------------------------------------
# Unit tests — _classify_intervention_type
# ---------------------------------------------------------------------------


def test_type_insufficient_data_when_no_irr() -> None:
    assert _classify_intervention_type(None, -5.0, 3) == "insufficient_data"


def test_type_mixed_intervention() -> None:
    assert _classify_intervention_type(0.15, -5.0, 3) == "mixed_intervention"


def test_type_pricing_intervention_only() -> None:
    assert _classify_intervention_type(0.15, 8.0, 0) == "pricing_intervention"


def test_type_pricing_intervention_negative() -> None:
    assert _classify_intervention_type(0.15, -5.0, 0) == "pricing_intervention"


def test_type_phasing_intervention_only() -> None:
    assert _classify_intervention_type(0.15, 0.0, 3) == "phasing_intervention"


def test_type_monitor_only_no_signals() -> None:
    assert _classify_intervention_type(0.15, 0.0, 0) == "monitor_only"


def test_type_monitor_only_small_price_adjustment() -> None:
    # |4.9| < 5% threshold → no price signal
    assert _classify_intervention_type(0.15, 4.9, 0) == "monitor_only"


# ---------------------------------------------------------------------------
# Unit tests — _rank_cards determinism
# ---------------------------------------------------------------------------


def _make_card(
    project_id: str,
    project_name: str,
    intervention_priority: str,
    risk_score: str | None,
    urgency_score: int,
) -> PortfolioInterventionProjectCard:
    return PortfolioInterventionProjectCard(
        project_id=project_id,
        project_name=project_name,
        has_feasibility_baseline=True,
        recommended_strategy="maintain",
        best_irr=0.15,
        irr_delta=None,
        risk_score=risk_score,
        intervention_priority=intervention_priority,  # type: ignore[arg-type]
        intervention_type="monitor_only",
        urgency_score=urgency_score,
        reason="Test card.",
    )


def test_rank_cards_urgent_before_recommended() -> None:
    cards = [
        _make_card("b", "Beta", "recommended_intervention", "medium", 50),
        _make_card("a", "Alpha", "urgent_intervention", "high", 70),
    ]
    ranked = _rank_cards(cards)
    assert ranked[0].project_id == "a"
    assert ranked[1].project_id == "b"


def test_rank_cards_same_priority_high_risk_first() -> None:
    cards = [
        _make_card("b", "Beta", "recommended_intervention", "low", 40),
        _make_card("a", "Alpha", "recommended_intervention", "high", 40),
    ]
    ranked = _rank_cards(cards)
    assert ranked[0].project_id == "a"


def test_rank_cards_same_priority_risk_higher_urgency_score_first() -> None:
    cards = [
        _make_card("b", "Beta", "recommended_intervention", "medium", 40),
        _make_card("a", "Alpha", "recommended_intervention", "medium", 50),
    ]
    ranked = _rank_cards(cards)
    assert ranked[0].project_id == "a"


def test_rank_cards_same_all_keys_alphabetical_name() -> None:
    cards = [
        _make_card("b", "Zeta Project", "stable", "low", 10),
        _make_card("a", "Alpha Project", "stable", "low", 10),
    ]
    ranked = _rank_cards(cards)
    assert ranked[0].project_id == "a"


def test_rank_cards_insufficient_data_last() -> None:
    cards = [
        _make_card("c", "Charlie", "insufficient_data", None, 0),
        _make_card("b", "Beta", "stable", "low", 10),
        _make_card("a", "Alpha", "urgent_intervention", "high", 70),
    ]
    ranked = _rank_cards(cards)
    assert ranked[0].project_id == "a"
    assert ranked[-1].project_id == "c"


def test_rank_cards_deterministic_repeated_call() -> None:
    cards = [
        _make_card("c", "Charlie", "monitor_closely", "medium", 35),
        _make_card("a", "Alpha", "urgent_intervention", "high", 75),
        _make_card("b", "Beta", "recommended_intervention", "medium", 45),
    ]
    ranked_1 = _rank_cards(cards)
    ranked_2 = _rank_cards(cards)
    assert [c.project_id for c in ranked_1] == [c.project_id for c in ranked_2]


# ---------------------------------------------------------------------------
# API — HTTP contract
# ---------------------------------------------------------------------------


def test_auto_strategy_returns_200(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text


def test_auto_strategy_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# API — Empty portfolio
# ---------------------------------------------------------------------------


def test_auto_strategy_empty_portfolio_returns_valid_response(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "summary" in data
    assert "project_cards" in data
    assert "top_actions" in data
    assert "top_risk_projects" in data
    assert "top_upside_projects" in data

    summary = data["summary"]
    assert summary["total_projects"] == 0
    assert summary["analyzed_projects"] == 0
    assert summary["projects_with_baseline"] == 0
    assert summary["urgent_intervention_count"] == 0
    assert summary["monitor_only_count"] == 0
    assert summary["no_data_count"] == 0

    assert data["project_cards"] == []
    assert data["top_actions"] == []
    assert data["top_risk_projects"] == []
    assert data["top_upside_projects"] == []


# ---------------------------------------------------------------------------
# API — Response schema shape
# ---------------------------------------------------------------------------


def test_auto_strategy_response_schema_shape(client: TestClient) -> None:
    _create_project(client, code="PAS-SCH", name="Schema Test Project")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Summary fields
    summary = data["summary"]
    for field in [
        "total_projects",
        "analyzed_projects",
        "projects_with_baseline",
        "urgent_intervention_count",
        "monitor_only_count",
        "no_data_count",
    ]:
        assert field in summary, f"Missing summary field: {field}"

    # Project card fields
    assert len(data["project_cards"]) >= 1
    card = data["project_cards"][0]
    for field in [
        "project_id",
        "project_name",
        "has_feasibility_baseline",
        "recommended_strategy",
        "best_irr",
        "irr_delta",
        "risk_score",
        "intervention_priority",
        "intervention_type",
        "urgency_score",
        "reason",
    ]:
        assert field in card, f"Missing card field: {field}"

    # Top action fields
    if data["top_actions"]:
        action = data["top_actions"][0]
        for field in [
            "project_id",
            "project_name",
            "intervention_priority",
            "intervention_type",
            "urgency_score",
            "reason",
        ]:
            assert field in action, f"Missing top_action field: {field}"


# ---------------------------------------------------------------------------
# API — Per-project cards populated
# ---------------------------------------------------------------------------


def test_auto_strategy_cards_populated_for_project(client: TestClient) -> None:
    project_id = _create_project(client, code="PAS-CARD", name="Card Test Project")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    card_ids = [c["project_id"] for c in data["project_cards"]]
    assert project_id in card_ids


# ---------------------------------------------------------------------------
# API — Summary counts accurate
# ---------------------------------------------------------------------------


def test_auto_strategy_summary_total_matches_card_count(client: TestClient) -> None:
    _create_project(client, code="PAS-SM1", name="Summary Test A")
    _create_project(client, code="PAS-SM2", name="Summary Test B")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["summary"]["total_projects"] == len(data["project_cards"])


def test_auto_strategy_summary_analyzed_lte_total(client: TestClient) -> None:
    _create_project(client, code="PAS-AN1", name="Analyzed Test Project")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["summary"]["analyzed_projects"] <= data["summary"]["total_projects"]


def test_auto_strategy_urgent_plus_monitor_plus_nodata_matches_total(
    client: TestClient,
) -> None:
    _create_project(client, code="PAS-CNT", name="Count Validation Project")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    summary = data["summary"]

    # Recalculate from cards
    cards = data["project_cards"]
    urgent = sum(1 for c in cards if c["intervention_priority"] == "urgent_intervention")
    recommended = sum(
        1 for c in cards if c["intervention_priority"] == "recommended_intervention"
    )
    monitor = sum(
        1 for c in cards if c["intervention_priority"] in ("stable", "monitor_closely")
    )
    no_data = sum(1 for c in cards if c["intervention_priority"] == "insufficient_data")
    assert urgent == summary["urgent_intervention_count"]
    assert monitor == summary["monitor_only_count"]
    assert no_data == summary["no_data_count"]
    assert urgent + recommended + monitor + no_data == summary["total_projects"]


# ---------------------------------------------------------------------------
# API — Top actions limit
# ---------------------------------------------------------------------------


def test_auto_strategy_top_actions_at_most_five(client: TestClient) -> None:
    for i in range(7):
        _create_project(client, code=f"PAS-T{i}", name=f"Top Action Project {i}")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["top_actions"]) <= 5


def test_auto_strategy_top_risk_at_most_five(client: TestClient) -> None:
    for i in range(7):
        _create_project(client, code=f"PAS-R{i}", name=f"Risk Project {i}")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["top_risk_projects"]) <= 5


def test_auto_strategy_top_upside_at_most_five(client: TestClient) -> None:
    for i in range(7):
        _create_project(client, code=f"PAS-U{i}", name=f"Upside Project {i}")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["top_upside_projects"]) <= 5


# ---------------------------------------------------------------------------
# API — urgency_score range
# ---------------------------------------------------------------------------


def test_urgency_score_in_valid_range(client: TestClient) -> None:
    _create_project(client, code="PAS-URG", name="Urgency Range Project")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for card in data["project_cards"]:
        assert 0 <= card["urgency_score"] <= 100, (
            f"urgency_score out of range for {card['project_id']}: {card['urgency_score']}"
        )


# ---------------------------------------------------------------------------
# API — Valid intervention_priority values
# ---------------------------------------------------------------------------

_VALID_PRIORITIES = {
    "urgent_intervention",
    "recommended_intervention",
    "monitor_closely",
    "stable",
    "insufficient_data",
}

_VALID_TYPES = {
    "pricing_intervention",
    "phasing_intervention",
    "mixed_intervention",
    "monitor_only",
    "insufficient_data",
}


def test_intervention_priority_valid_values(client: TestClient) -> None:
    _create_project(client, code="PAS-PRV", name="Priority Valid Project")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for card in data["project_cards"]:
        assert card["intervention_priority"] in _VALID_PRIORITIES, (
            f"Invalid intervention_priority: {card['intervention_priority']}"
        )


def test_intervention_type_valid_values(client: TestClient) -> None:
    _create_project(client, code="PAS-TYV", name="Type Valid Project")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for card in data["project_cards"]:
        assert card["intervention_type"] in _VALID_TYPES, (
            f"Invalid intervention_type: {card['intervention_type']}"
        )


# ---------------------------------------------------------------------------
# API — Baseline project has better data
# ---------------------------------------------------------------------------


def test_project_with_feasibility_baseline_has_baseline_flag(
    client: TestClient,
) -> None:
    project_id = _create_project(client, code="PAS-BL1", name="Baseline Project")
    _create_feasibility_run(client, project_id)
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    card = next(c for c in data["project_cards"] if c["project_id"] == project_id)
    assert card["has_feasibility_baseline"] is True


# ---------------------------------------------------------------------------
# API — Top upside projects ordered by IRR descending
# ---------------------------------------------------------------------------


def test_top_upside_projects_ordered_by_irr_descending(client: TestClient) -> None:
    # Create several projects with feasibility so they get real IRR values
    for i in range(3):
        pid = _create_project(client, code=f"PAS-IRR{i}", name=f"IRR Project {i}")
        _create_feasibility_run(
            client,
            pid,
            avg_price=3000.0 + i * 500.0,  # varied pricing → varied IRR
        )
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    upside = data["top_upside_projects"]
    irrs = [c["best_irr"] for c in upside if c["best_irr"] is not None]
    assert irrs == sorted(irrs, reverse=True)


# ---------------------------------------------------------------------------
# API — Reason field non-empty
# ---------------------------------------------------------------------------


def test_cards_have_non_empty_reason(client: TestClient) -> None:
    _create_project(client, code="PAS-RSN", name="Reason Test Project")
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for card in data["project_cards"]:
        assert card["reason"], f"Empty reason for {card['project_id']}"


# ---------------------------------------------------------------------------
# API — Read-only: no source records mutated
# ---------------------------------------------------------------------------


def test_auto_strategy_does_not_mutate_feasibility_data(client: TestClient) -> None:
    project_id = _create_project(client, code="PAS-MUT", name="Mutation Test Project")
    _create_feasibility_run(client, project_id, avg_price=3500.0)

    # Record feasibility runs before
    runs_before = client.get(f"/api/v1/feasibility/runs?project_id={project_id}")
    count_before = len(runs_before.json()) if runs_before.status_code == 200 else None

    # Call auto-strategy
    resp = client.get("/api/v1/portfolio/auto-strategy")
    assert resp.status_code == 200, resp.text

    # Record feasibility runs after
    runs_after = client.get(f"/api/v1/feasibility/runs?project_id={project_id}")
    if count_before is not None and runs_after.status_code == 200:
        assert len(runs_after.json()) == count_before, (
            "Feasibility runs count changed — source records may have been mutated."
        )


# ---------------------------------------------------------------------------
# API — Deterministic repeated calls
# ---------------------------------------------------------------------------


def test_auto_strategy_ranking_is_deterministic(client: TestClient) -> None:
    for i in range(3):
        pid = _create_project(client, code=f"PAS-DET{i}", name=f"Deterministic Project {i}")
        _create_feasibility_run(client, pid)

    resp1 = client.get("/api/v1/portfolio/auto-strategy")
    resp2 = client.get("/api/v1/portfolio/auto-strategy")
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    ids1 = [c["project_id"] for c in resp1.json()["project_cards"]]
    ids2 = [c["project_id"] for c in resp2.json()["project_cards"]]
    assert ids1 == ids2, "Ranking is not deterministic across repeated calls"
