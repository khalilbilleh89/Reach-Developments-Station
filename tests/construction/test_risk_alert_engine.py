"""
Tests for the Construction Risk Alert Engine.

PR-CONSTR-044 — Contractor Performance & Procurement Risk Alerts

Validates:
- Unawarded package with active milestone triggers HIGH alert
- Stalled tendering/evaluation package triggers MEDIUM alert
- Cancelled/on-hold package linked to active milestone triggers HIGH alert
- Scope high uncommitted value triggers MEDIUM alert
- Contractor high delay ratio triggers HIGH alert
- Contractor high overrun ratio triggers MEDIUM alert
- Deterministic severity ordering (HIGH before MEDIUM)
- No false positives on clean data
- Threshold edge cases
"""

from decimal import Decimal

from app.modules.construction.risk_alert_engine import (
    ALERT_CANCELLED_PACKAGE_MILESTONE_LINK,
    ALERT_CONTRACTOR_HIGH_DELAY_RATIO,
    ALERT_CONTRACTOR_HIGH_OVERRUN_RATIO,
    ALERT_SCOPE_HIGH_UNCOMMITTED_VALUE,
    ALERT_STALLED_PACKAGE,
    ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    ContractorRiskData,
    MilestoneRiskData,
    PackageRiskData,
    ScopeRiskData,
    evaluate_contractor_performance,
    evaluate_procurement_risk,
    evaluate_scope_risk_alerts,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _milestone(
    mid: str = "M1",
    status: str = "pending",
    planned_cost: str | None = None,
    actual_cost: str | None = None,
) -> MilestoneRiskData:
    return MilestoneRiskData(
        milestone_id=mid,
        status=status,
        planned_cost=Decimal(planned_cost) if planned_cost is not None else None,
        actual_cost=Decimal(actual_cost) if actual_cost is not None else None,
    )


def _package(
    pkg_id: str = "PKG-1",
    scope_id: str = "SCOPE-1",
    status: str = "draft",
    planned_value: str | None = "100000",
    awarded_value: str | None = None,
    days_since_update: int = 0,
    milestones: list[MilestoneRiskData] | None = None,
    contractor_id: str | None = None,
) -> PackageRiskData:
    return PackageRiskData(
        package_id=pkg_id,
        scope_id=scope_id,
        contractor_id=contractor_id,
        status=status,
        planned_value=Decimal(planned_value) if planned_value is not None else None,
        awarded_value=Decimal(awarded_value) if awarded_value is not None else None,
        days_since_update=days_since_update,
        linked_milestones=milestones or [],
    )


def _scope(
    scope_id: str = "SCOPE-1",
    packages: list[PackageRiskData] | None = None,
) -> ScopeRiskData:
    return ScopeRiskData(scope_id=scope_id, packages=packages or [])


def _contractor(
    cid: str = "CTR-1",
    name: str = "Test Corp",
    milestones: list[MilestoneRiskData] | None = None,
) -> ContractorRiskData:
    return ContractorRiskData(
        contractor_id=cid,
        contractor_name=name,
        all_milestones=milestones or [],
    )


def _alert_codes(alerts: list) -> list[str]:
    return [a.alert_code for a in alerts]


# ---------------------------------------------------------------------------
# Empty / trivial cases
# ---------------------------------------------------------------------------


def test_empty_scope_no_alerts() -> None:
    alerts = evaluate_scope_risk_alerts(_scope())
    assert alerts == []


def test_scope_with_awarded_package_no_alerts() -> None:
    pkg = _package(status="awarded", planned_value="100000", awarded_value="100000")
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert alerts == []


def test_empty_contractor_no_alerts() -> None:
    summary = evaluate_contractor_performance(_contractor())
    assert summary.total_milestones == 0
    assert summary.delay_ratio is None
    assert summary.overrun_ratio is None
    assert summary.alerts == []


# ---------------------------------------------------------------------------
# UNAWARDED_PACKAGE_ACTIVE_MILESTONE
# ---------------------------------------------------------------------------


def test_draft_package_active_milestone_triggers_alert() -> None:
    ms = [_milestone("M1", status="in_progress")]
    pkg = _package(status="draft", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE in _alert_codes(alerts)


def test_tendering_package_delayed_milestone_triggers_alert() -> None:
    ms = [_milestone("M1", status="delayed")]
    pkg = _package(status="tendering", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE in _alert_codes(alerts)


def test_evaluation_package_active_milestone_triggers_alert() -> None:
    ms = [_milestone("M1", status="in_progress")]
    pkg = _package(status="evaluation", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE in _alert_codes(alerts)


def test_unawarded_package_pending_milestone_no_alert() -> None:
    ms = [_milestone("M1", status="pending")]
    pkg = _package(status="draft", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE not in _alert_codes(alerts)


def test_unawarded_package_completed_milestone_no_alert() -> None:
    ms = [_milestone("M1", status="completed")]
    pkg = _package(status="tendering", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE not in _alert_codes(alerts)


def test_awarded_package_active_milestone_no_unawarded_alert() -> None:
    ms = [_milestone("M1", status="in_progress")]
    pkg = _package(status="awarded", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE not in _alert_codes(alerts)


def test_unawarded_alert_severity_is_high() -> None:
    ms = [_milestone("M1", status="in_progress")]
    pkg = _package(status="draft", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    found = [a for a in alerts if a.alert_code == ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE]
    assert found
    assert found[0].severity == SEVERITY_HIGH


# ---------------------------------------------------------------------------
# STALLED_PACKAGE
# ---------------------------------------------------------------------------


def test_tendering_stalled_triggers_alert() -> None:
    pkg = _package(status="tendering", days_since_update=15)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_STALLED_PACKAGE in _alert_codes(alerts)


def test_evaluation_stalled_triggers_alert() -> None:
    pkg = _package(status="evaluation", days_since_update=20)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_STALLED_PACKAGE in _alert_codes(alerts)


def test_tendering_within_threshold_no_stalled_alert() -> None:
    pkg = _package(status="tendering", days_since_update=14)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_STALLED_PACKAGE not in _alert_codes(alerts)


def test_draft_stalled_no_alert() -> None:
    # draft is not in stalled statuses
    pkg = _package(status="draft", days_since_update=30)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_STALLED_PACKAGE not in _alert_codes(alerts)


def test_stalled_alert_severity_is_medium() -> None:
    pkg = _package(status="tendering", days_since_update=20)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    found = [a for a in alerts if a.alert_code == ALERT_STALLED_PACKAGE]
    assert found
    assert found[0].severity == SEVERITY_MEDIUM


def test_stalled_alert_metric_value() -> None:
    pkg = _package(status="tendering", days_since_update=20)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    found = [a for a in alerts if a.alert_code == ALERT_STALLED_PACKAGE]
    assert found
    assert found[0].metric_value == 20.0
    assert found[0].threshold == 14.0


# ---------------------------------------------------------------------------
# CANCELLED_PACKAGE_MILESTONE_LINK
# ---------------------------------------------------------------------------


def test_cancelled_package_active_milestone_triggers_alert() -> None:
    ms = [_milestone("M1", status="in_progress")]
    pkg = _package(status="cancelled", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_CANCELLED_PACKAGE_MILESTONE_LINK in _alert_codes(alerts)


def test_on_hold_package_delayed_milestone_triggers_alert() -> None:
    ms = [_milestone("M1", status="delayed")]
    pkg = _package(status="on_hold", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_CANCELLED_PACKAGE_MILESTONE_LINK in _alert_codes(alerts)


def test_cancelled_package_pending_milestone_no_alert() -> None:
    ms = [_milestone("M1", status="pending")]
    pkg = _package(status="cancelled", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_CANCELLED_PACKAGE_MILESTONE_LINK not in _alert_codes(alerts)


def test_cancelled_alert_severity_is_high() -> None:
    ms = [_milestone("M1", status="in_progress")]
    pkg = _package(status="cancelled", milestones=ms)
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    found = [a for a in alerts if a.alert_code == ALERT_CANCELLED_PACKAGE_MILESTONE_LINK]
    assert found
    assert found[0].severity == SEVERITY_HIGH


# ---------------------------------------------------------------------------
# SCOPE_HIGH_UNCOMMITTED_VALUE
# ---------------------------------------------------------------------------


def test_high_uncommitted_value_triggers_alert() -> None:
    # 70% uncommitted -> above 30% threshold
    pkg = _package(planned_value="100000", awarded_value="30000", status="awarded")
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_SCOPE_HIGH_UNCOMMITTED_VALUE in _alert_codes(alerts)


def test_low_uncommitted_value_no_alert() -> None:
    # 20% uncommitted -> below 30% threshold
    pkg = _package(planned_value="100000", awarded_value="80000", status="awarded")
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_SCOPE_HIGH_UNCOMMITTED_VALUE not in _alert_codes(alerts)


def test_exactly_at_threshold_no_alert() -> None:
    # Exactly 30% uncommitted — not strictly above threshold
    pkg = _package(planned_value="100000", awarded_value="70000", status="awarded")
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_SCOPE_HIGH_UNCOMMITTED_VALUE not in _alert_codes(alerts)


def test_zero_planned_value_no_uncommitted_alert() -> None:
    pkg = _package(planned_value=None, awarded_value=None, status="draft")
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    assert ALERT_SCOPE_HIGH_UNCOMMITTED_VALUE not in _alert_codes(alerts)


def test_uncommitted_alert_severity_is_medium() -> None:
    pkg = _package(planned_value="100000", awarded_value="30000", status="awarded")
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    found = [a for a in alerts if a.alert_code == ALERT_SCOPE_HIGH_UNCOMMITTED_VALUE]
    assert found
    assert found[0].severity == SEVERITY_MEDIUM


def test_uncommitted_metric_value_computed_correctly() -> None:
    # 70% uncommitted
    pkg = _package(planned_value="100000", awarded_value="30000", status="awarded")
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg]))
    found = [a for a in alerts if a.alert_code == ALERT_SCOPE_HIGH_UNCOMMITTED_VALUE]
    assert found
    assert abs(found[0].metric_value - 0.7) < 0.001


# ---------------------------------------------------------------------------
# CONTRACTOR_HIGH_DELAY_RATIO
# ---------------------------------------------------------------------------


def test_contractor_delay_ratio_above_threshold_triggers_alert() -> None:
    # 2 delayed out of 3 = 66.7% > 50%
    ms = [
        _milestone("M1", status="delayed"),
        _milestone("M2", status="delayed"),
        _milestone("M3", status="completed"),
    ]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    assert ALERT_CONTRACTOR_HIGH_DELAY_RATIO in [a.alert_code for a in summary.alerts]


def test_contractor_delay_ratio_below_threshold_no_alert() -> None:
    # 1 delayed out of 3 = 33.3% < 50%
    ms = [
        _milestone("M1", status="delayed"),
        _milestone("M2", status="completed"),
        _milestone("M3", status="completed"),
    ]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    assert ALERT_CONTRACTOR_HIGH_DELAY_RATIO not in [a.alert_code for a in summary.alerts]


def test_contractor_all_delayed_triggers_alert() -> None:
    ms = [_milestone("M1", status="delayed"), _milestone("M2", status="delayed")]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    assert ALERT_CONTRACTOR_HIGH_DELAY_RATIO in [a.alert_code for a in summary.alerts]


def test_contractor_delay_alert_severity_is_high() -> None:
    ms = [_milestone("M1", status="delayed"), _milestone("M2", status="delayed")]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    found = [a for a in summary.alerts if a.alert_code == ALERT_CONTRACTOR_HIGH_DELAY_RATIO]
    assert found
    assert found[0].severity == SEVERITY_HIGH


def test_contractor_performance_counts_are_correct() -> None:
    ms = [
        _milestone("M1", status="delayed"),
        _milestone("M2", status="in_progress"),
        _milestone("M3", status="completed"),
    ]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    assert summary.total_milestones == 3
    assert summary.delayed_milestones == 1
    assert abs(summary.delay_ratio - 1 / 3) < 0.001


def test_contractor_milestone_deduplication() -> None:
    # Same milestone ID appears twice (e.g. from multiple packages)
    ms = [
        _milestone("M1", status="delayed"),
        _milestone("M1", status="delayed"),  # duplicate
        _milestone("M2", status="completed"),
    ]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    # After dedup: 2 unique milestones (M1 delayed, M2 completed) → ratio 0.5
    assert summary.total_milestones == 2
    assert summary.delayed_milestones == 1


# ---------------------------------------------------------------------------
# CONTRACTOR_HIGH_OVERRUN_RATIO
# ---------------------------------------------------------------------------


def test_contractor_overrun_ratio_above_threshold_triggers_alert() -> None:
    # 2 over-budget out of 3 assessed = 66.7% > 50%
    ms = [
        _milestone("M1", planned_cost="1000", actual_cost="1200"),
        _milestone("M2", planned_cost="1000", actual_cost="1300"),
        _milestone("M3", planned_cost="1000", actual_cost="900"),
    ]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    assert ALERT_CONTRACTOR_HIGH_OVERRUN_RATIO in [a.alert_code for a in summary.alerts]


def test_contractor_overrun_ratio_below_threshold_no_alert() -> None:
    # 1 over-budget out of 3 = 33.3% < 50%
    ms = [
        _milestone("M1", planned_cost="1000", actual_cost="1200"),
        _milestone("M2", planned_cost="1000", actual_cost="900"),
        _milestone("M3", planned_cost="1000", actual_cost="950"),
    ]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    assert ALERT_CONTRACTOR_HIGH_OVERRUN_RATIO not in [a.alert_code for a in summary.alerts]


def test_contractor_overrun_alert_severity_is_medium() -> None:
    ms = [
        _milestone("M1", planned_cost="1000", actual_cost="1500"),
        _milestone("M2", planned_cost="1000", actual_cost="1500"),
    ]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    found = [a for a in summary.alerts if a.alert_code == ALERT_CONTRACTOR_HIGH_OVERRUN_RATIO]
    assert found
    assert found[0].severity == SEVERITY_MEDIUM


def test_contractor_missing_costs_not_counted_in_overrun() -> None:
    # Milestones without both costs don't contribute to overrun ratio
    ms = [
        _milestone("M1", planned_cost="1000", actual_cost="1500"),
        _milestone("M2"),  # no costs
        _milestone("M3"),  # no costs
    ]
    summary = evaluate_contractor_performance(_contractor(milestones=ms))
    # Only 1 assessable milestone, 1 over-budget → 100% > 50%
    assert ALERT_CONTRACTOR_HIGH_OVERRUN_RATIO in [a.alert_code for a in summary.alerts]
    assert summary.over_budget_milestones == 1


# ---------------------------------------------------------------------------
# Severity sorting
# ---------------------------------------------------------------------------


def test_high_alerts_come_before_medium() -> None:
    # Create a scope with both CANCELLED (HIGH) and STALLED (MEDIUM) alerts
    ms_active = [_milestone("M1", status="in_progress")]
    pkg_cancelled = _package(
        pkg_id="PKG-1", status="cancelled", milestones=ms_active, days_since_update=0
    )
    pkg_stalled = _package(
        pkg_id="PKG-2", status="tendering", milestones=[], days_since_update=20
    )
    alerts = evaluate_scope_risk_alerts(_scope(packages=[pkg_cancelled, pkg_stalled]))
    severities = [a.severity for a in alerts]
    high_indices = [i for i, s in enumerate(severities) if s == SEVERITY_HIGH]
    medium_indices = [i for i, s in enumerate(severities) if s == SEVERITY_MEDIUM]
    if high_indices and medium_indices:
        assert max(high_indices) < min(medium_indices)


# ---------------------------------------------------------------------------
# Procurement risk overview
# ---------------------------------------------------------------------------


def test_procurement_risk_counts_unawarded_packages() -> None:
    p1 = _package(pkg_id="P1", status="draft")
    p2 = _package(pkg_id="P2", status="tendering")
    p3 = _package(pkg_id="P3", status="awarded", planned_value="100", awarded_value="100")
    summary = evaluate_procurement_risk(_scope(packages=[p1, p2, p3]))
    assert summary.total_packages == 3
    assert summary.unawarded_packages == 2


def test_procurement_risk_counts_stalled_packages() -> None:
    p1 = _package(pkg_id="P1", status="tendering", days_since_update=20)
    p2 = _package(pkg_id="P2", status="evaluation", days_since_update=5)
    summary = evaluate_procurement_risk(_scope(packages=[p1, p2]))
    assert summary.stalled_packages == 1


def test_procurement_risk_counts_cancelled_on_hold() -> None:
    p1 = _package(pkg_id="P1", status="cancelled")
    p2 = _package(pkg_id="P2", status="on_hold")
    p3 = _package(pkg_id="P3", status="awarded", planned_value="100", awarded_value="100")
    summary = evaluate_procurement_risk(_scope(packages=[p1, p2, p3]))
    assert summary.cancelled_or_on_hold_packages == 2


def test_procurement_risk_value_totals() -> None:
    p1 = _package(pkg_id="P1", planned_value="50000", awarded_value="50000", status="awarded")
    p2 = _package(pkg_id="P2", planned_value="80000", awarded_value=None, status="tendering")
    summary = evaluate_procurement_risk(_scope(packages=[p1, p2]))
    assert summary.total_planned_value == Decimal("130000")
    assert summary.total_awarded_value == Decimal("50000")
    assert summary.uncommitted_value == Decimal("80000")


def test_procurement_risk_empty_scope() -> None:
    summary = evaluate_procurement_risk(_scope())
    assert summary.total_packages == 0
    assert summary.unawarded_packages == 0
    assert summary.stalled_packages == 0
    assert summary.cancelled_or_on_hold_packages == 0
    assert summary.total_planned_value == Decimal("0.00")
    assert summary.alerts == []
