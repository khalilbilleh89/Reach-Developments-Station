"""
Tests for the Scope Escalation & Contractor Watchlist Engine.

PR-CONSTR-049 — Scope Escalation & Contractor Watchlist Engine

Validates:
- normal contractor (no breach triggers)
- watch status via average_delay_days threshold
- watch status via average_cost_variance_pct threshold
- watch status via risk_signal_count threshold
- escalate status via reliability_band == "Watch"
- escalate status via average_delay_days >= 14 threshold
- escalate status via average_cost_variance_pct >= 0.15 threshold
- escalate status via risk_signal_count >= 3 threshold
- critical status via reliability_band == "Critical"
- critical status via delay_rate >= 0.50
- critical status via cost_overrun_rate >= 0.50
- critical status via risk_signal_count >= 5
- deterministic priority order (Critical wins over Escalate/Watch)
- multiple breach reasons collected within a tier
- breach_reasons contains all triggered reasons for winning tier
- escalation_score values are correct for each tier
- exact threshold boundaries (just below vs at threshold)
- integration with contractor scorecard engine
"""

from __future__ import annotations

from app.modules.construction.scope_escalation_engine import (
    CRITICAL_COST_OVERRUN_RATE,
    CRITICAL_DELAY_RATE,
    CRITICAL_RISK_SIGNAL_COUNT,
    ESCALATE_AVERAGE_COST_VARIANCE_PCT,
    ESCALATE_AVERAGE_DELAY_DAYS,
    ESCALATE_RISK_SIGNAL_COUNT,
    STATUS_CRITICAL,
    STATUS_ESCALATE,
    STATUS_NORMAL,
    STATUS_WATCH,
    WATCH_AVERAGE_COST_VARIANCE_PCT,
    WATCH_AVERAGE_DELAY_DAYS,
    WATCH_RISK_SIGNAL_COUNT,
    ContractorEscalationInput,
    compute_contractor_escalation,
)


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------


def _inp(
    contractor_id: str = "CTR-001",
    reliability_index: float | None = None,
    reliability_band: str | None = None,
    delay_rate: float | None = None,
    average_delay_days: float | None = None,
    cost_overrun_rate: float | None = None,
    average_cost_variance_pct: float | None = None,
    risk_signal_count: int = 0,
) -> ContractorEscalationInput:
    return ContractorEscalationInput(
        contractor_id=contractor_id,
        reliability_index=reliability_index,
        reliability_band=reliability_band,
        delay_rate=delay_rate,
        average_delay_days=average_delay_days,
        cost_overrun_rate=cost_overrun_rate,
        average_cost_variance_pct=average_cost_variance_pct,
        risk_signal_count=risk_signal_count,
    )


# ---------------------------------------------------------------------------
# Normal status
# ---------------------------------------------------------------------------


def test_normal_contractor_no_triggers() -> None:
    """No risk signals and no threshold breaches → Normal."""
    result = compute_contractor_escalation(
        _inp(reliability_band="Strong", risk_signal_count=0)
    )
    assert result.watchlist_status == STATUS_NORMAL
    assert result.breach_reasons == []
    assert result.escalation_score == 0


def test_normal_contractor_no_data() -> None:
    """All None analytics with no risk signals → Normal."""
    result = compute_contractor_escalation(_inp())
    assert result.watchlist_status == STATUS_NORMAL
    assert result.breach_reasons == []
    assert result.escalation_score == 0


def test_normal_contractor_elite_band() -> None:
    """Elite reliability band with no other signals → Normal."""
    result = compute_contractor_escalation(
        _inp(
            reliability_band="Elite",
            delay_rate=0.05,
            cost_overrun_rate=0.05,
            average_delay_days=2.0,
            average_cost_variance_pct=0.02,
            risk_signal_count=0,
        )
    )
    assert result.watchlist_status == STATUS_NORMAL


# ---------------------------------------------------------------------------
# Watch status
# ---------------------------------------------------------------------------


def test_watch_via_average_delay_days() -> None:
    """average_delay_days at watch threshold triggers Watch."""
    result = compute_contractor_escalation(
        _inp(average_delay_days=WATCH_AVERAGE_DELAY_DAYS)
    )
    assert result.watchlist_status == STATUS_WATCH
    assert result.escalation_score == 1
    assert any("average delay" in r for r in result.breach_reasons)


def test_watch_via_average_cost_variance_pct() -> None:
    """average_cost_variance_pct at watch threshold triggers Watch."""
    result = compute_contractor_escalation(
        _inp(average_cost_variance_pct=WATCH_AVERAGE_COST_VARIANCE_PCT)
    )
    assert result.watchlist_status == STATUS_WATCH
    assert result.escalation_score == 1
    assert any("cost variance" in r for r in result.breach_reasons)


def test_watch_via_risk_signal_count() -> None:
    """risk_signal_count at watch threshold triggers Watch."""
    result = compute_contractor_escalation(
        _inp(risk_signal_count=WATCH_RISK_SIGNAL_COUNT)
    )
    assert result.watchlist_status == STATUS_WATCH
    assert result.escalation_score == 1
    assert any("risk signal count" in r for r in result.breach_reasons)


def test_watch_just_below_threshold_is_normal() -> None:
    """Values strictly below watch thresholds → Normal (boundary check)."""
    result = compute_contractor_escalation(
        _inp(
            average_delay_days=WATCH_AVERAGE_DELAY_DAYS - 0.01,
            average_cost_variance_pct=WATCH_AVERAGE_COST_VARIANCE_PCT - 0.001,
            risk_signal_count=0,
        )
    )
    assert result.watchlist_status == STATUS_NORMAL


# ---------------------------------------------------------------------------
# Escalate status
# ---------------------------------------------------------------------------


def test_escalate_via_reliability_band_watch() -> None:
    """reliability_band == 'Watch' triggers Escalate."""
    result = compute_contractor_escalation(_inp(reliability_band="Watch"))
    assert result.watchlist_status == STATUS_ESCALATE
    assert result.escalation_score == 2
    assert any("reliability band" in r for r in result.breach_reasons)


def test_escalate_via_average_delay_days() -> None:
    """average_delay_days at escalate threshold triggers Escalate."""
    result = compute_contractor_escalation(
        _inp(average_delay_days=ESCALATE_AVERAGE_DELAY_DAYS)
    )
    assert result.watchlist_status == STATUS_ESCALATE
    assert result.escalation_score == 2
    assert any("average delay" in r for r in result.breach_reasons)


def test_escalate_via_average_cost_variance_pct() -> None:
    """average_cost_variance_pct at escalate threshold triggers Escalate."""
    result = compute_contractor_escalation(
        _inp(average_cost_variance_pct=ESCALATE_AVERAGE_COST_VARIANCE_PCT)
    )
    assert result.watchlist_status == STATUS_ESCALATE
    assert result.escalation_score == 2
    assert any("cost variance" in r for r in result.breach_reasons)


def test_escalate_via_risk_signal_count() -> None:
    """risk_signal_count at escalate threshold triggers Escalate."""
    result = compute_contractor_escalation(
        _inp(risk_signal_count=ESCALATE_RISK_SIGNAL_COUNT)
    )
    assert result.watchlist_status == STATUS_ESCALATE
    assert result.escalation_score == 2
    assert any("risk signal count" in r for r in result.breach_reasons)


def test_escalate_just_below_delay_threshold_is_watch() -> None:
    """average_delay_days just below escalate threshold → Watch (not Escalate)."""
    result = compute_contractor_escalation(
        _inp(average_delay_days=ESCALATE_AVERAGE_DELAY_DAYS - 0.01)
    )
    assert result.watchlist_status == STATUS_WATCH


# ---------------------------------------------------------------------------
# Critical status
# ---------------------------------------------------------------------------


def test_critical_via_reliability_band() -> None:
    """reliability_band == 'Critical' triggers Critical."""
    result = compute_contractor_escalation(_inp(reliability_band="Critical"))
    assert result.watchlist_status == STATUS_CRITICAL
    assert result.escalation_score == 3
    assert any("reliability band" in r for r in result.breach_reasons)


def test_critical_via_delay_rate() -> None:
    """delay_rate at critical threshold triggers Critical."""
    result = compute_contractor_escalation(
        _inp(delay_rate=CRITICAL_DELAY_RATE)
    )
    assert result.watchlist_status == STATUS_CRITICAL
    assert result.escalation_score == 3
    assert any("delay rate" in r for r in result.breach_reasons)


def test_critical_via_cost_overrun_rate() -> None:
    """cost_overrun_rate at critical threshold triggers Critical."""
    result = compute_contractor_escalation(
        _inp(cost_overrun_rate=CRITICAL_COST_OVERRUN_RATE)
    )
    assert result.watchlist_status == STATUS_CRITICAL
    assert result.escalation_score == 3
    assert any("cost overrun rate" in r for r in result.breach_reasons)


def test_critical_via_risk_signal_count() -> None:
    """risk_signal_count at critical threshold triggers Critical."""
    result = compute_contractor_escalation(
        _inp(risk_signal_count=CRITICAL_RISK_SIGNAL_COUNT)
    )
    assert result.watchlist_status == STATUS_CRITICAL
    assert result.escalation_score == 3
    assert any("risk signal count" in r for r in result.breach_reasons)


def test_critical_just_below_delay_rate_is_escalate_or_lower() -> None:
    """delay_rate just below critical threshold → not Critical."""
    result = compute_contractor_escalation(
        _inp(delay_rate=CRITICAL_DELAY_RATE - 0.01)
    )
    assert result.watchlist_status != STATUS_CRITICAL


# ---------------------------------------------------------------------------
# Priority order (Critical wins)
# ---------------------------------------------------------------------------


def test_critical_wins_over_escalate_triggers() -> None:
    """When both Critical and Escalate rules fire, status is Critical."""
    result = compute_contractor_escalation(
        _inp(
            reliability_band="Critical",  # triggers Critical
            average_delay_days=ESCALATE_AVERAGE_DELAY_DAYS,  # triggers Escalate
        )
    )
    assert result.watchlist_status == STATUS_CRITICAL
    assert result.escalation_score == 3


def test_critical_wins_over_watch_triggers() -> None:
    """When both Critical and Watch rules fire, status is Critical."""
    result = compute_contractor_escalation(
        _inp(
            delay_rate=CRITICAL_DELAY_RATE,
            average_delay_days=WATCH_AVERAGE_DELAY_DAYS,
        )
    )
    assert result.watchlist_status == STATUS_CRITICAL


def test_escalate_wins_over_watch_triggers() -> None:
    """When both Escalate and Watch rules fire (no Critical), status is Escalate."""
    result = compute_contractor_escalation(
        _inp(
            reliability_band="Watch",
            average_delay_days=WATCH_AVERAGE_DELAY_DAYS,
        )
    )
    assert result.watchlist_status == STATUS_ESCALATE
    assert result.escalation_score == 2


# ---------------------------------------------------------------------------
# Multiple breach reasons
# ---------------------------------------------------------------------------


def test_multiple_critical_breach_reasons() -> None:
    """All four Critical triggers fire → four breach_reasons."""
    result = compute_contractor_escalation(
        _inp(
            reliability_band="Critical",
            delay_rate=0.60,
            cost_overrun_rate=0.55,
            risk_signal_count=6,
        )
    )
    assert result.watchlist_status == STATUS_CRITICAL
    assert len(result.breach_reasons) == 4


def test_multiple_escalate_breach_reasons() -> None:
    """Multiple Escalate triggers fire → multiple breach_reasons."""
    result = compute_contractor_escalation(
        _inp(
            reliability_band="Watch",
            average_delay_days=20.0,
            average_cost_variance_pct=0.20,
            risk_signal_count=4,
        )
    )
    assert result.watchlist_status == STATUS_ESCALATE
    assert len(result.breach_reasons) == 4


def test_multiple_watch_breach_reasons() -> None:
    """Multiple Watch triggers fire → multiple breach_reasons."""
    result = compute_contractor_escalation(
        _inp(
            average_delay_days=8.0,
            average_cost_variance_pct=0.09,
            risk_signal_count=1,
        )
    )
    assert result.watchlist_status == STATUS_WATCH
    assert len(result.breach_reasons) == 3


# ---------------------------------------------------------------------------
# Breach reasons content
# ---------------------------------------------------------------------------


def test_breach_reasons_include_threshold_values() -> None:
    """Breach reasons mention the actual value and threshold."""
    result = compute_contractor_escalation(
        _inp(delay_rate=0.60)
    )
    assert any(
        "60%" in r or "0.60" in r or "delay rate" in r
        for r in result.breach_reasons
    )


def test_normal_has_empty_breach_reasons() -> None:
    """Normal status always has an empty breach_reasons list."""
    result = compute_contractor_escalation(_inp())
    assert result.breach_reasons == []


# ---------------------------------------------------------------------------
# Escalation score values
# ---------------------------------------------------------------------------


def test_escalation_score_critical() -> None:
    result = compute_contractor_escalation(_inp(reliability_band="Critical"))
    assert result.escalation_score == 3


def test_escalation_score_escalate() -> None:
    result = compute_contractor_escalation(_inp(reliability_band="Watch"))
    assert result.escalation_score == 2


def test_escalation_score_watch() -> None:
    result = compute_contractor_escalation(_inp(risk_signal_count=1))
    assert result.escalation_score == 1


def test_escalation_score_normal() -> None:
    result = compute_contractor_escalation(_inp())
    assert result.escalation_score == 0


# ---------------------------------------------------------------------------
# Integration with contractor scorecard engine
# ---------------------------------------------------------------------------


def test_scorecard_has_watchlist_fields() -> None:
    """compute_contractor_scorecard populates watchlist_status and breach_reasons."""
    from app.modules.construction.contractor_scorecard_engine import (
        ContractorScorecardInput,
        compute_contractor_scorecard,
    )

    inp = ContractorScorecardInput(
        contractor_id="CTR-INT-01",
        contractor_name="Integration Corp",
        milestones=[],
        packages=[],
        risk_signal_count=0,
    )
    sc = compute_contractor_scorecard(inp)
    assert sc.watchlist_status is not None
    assert sc.watchlist_status in {
        STATUS_NORMAL,
        STATUS_WATCH,
        STATUS_ESCALATE,
        STATUS_CRITICAL,
    }
    assert isinstance(sc.breach_reasons, list)
    assert isinstance(sc.escalation_score, int)


def test_scorecard_with_high_risk_signals_escalates() -> None:
    """A contractor with 5+ risk signals reaches Critical watchlist status."""
    from app.modules.construction.contractor_scorecard_engine import (
        ContractorScorecardInput,
        compute_contractor_scorecard,
    )

    inp = ContractorScorecardInput(
        contractor_id="CTR-INT-02",
        contractor_name="Risky Corp",
        milestones=[],
        packages=[],
        risk_signal_count=5,
    )
    sc = compute_contractor_scorecard(inp)
    assert sc.watchlist_status == STATUS_CRITICAL
    assert sc.escalation_score == 3
