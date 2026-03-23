"""
construction.risk_alert_engine

Pure Construction Risk Alert Engine.

Detects execution risk conditions from contractor performance and procurement
package data.  No database access, no HTTP concerns.

Alert rules (all thresholds configurable as module-level constants):

  UNAWARDED_PACKAGE_ACTIVE_MILESTONE
    Condition : package is not yet awarded (draft/tendering/evaluation/on_hold)
                AND at least one linked milestone is in_progress or delayed
    Severity  : HIGH

  STALLED_PACKAGE
    Condition : package status is tendering or evaluation
                AND days_since_update > STALLED_DAYS_THRESHOLD (default 14)
    Severity  : MEDIUM

  CONTRACTOR_HIGH_DELAY_RATIO
    Condition : fraction of contractor's linked milestones with status delayed
                > DELAY_RATIO_THRESHOLD (default 0.50)
    Requires  : at least MIN_MILESTONES_FOR_RATIO milestones (default 1)
    Severity  : HIGH

  CONTRACTOR_HIGH_OVERRUN_RATIO
    Condition : fraction of contractor's linked milestones that are over budget
                (actual_cost > planned_cost, both set)
                > OVERRUN_RATIO_THRESHOLD (default 0.50)
    Requires  : at least MIN_MILESTONES_FOR_RATIO milestones (default 1)
    Severity  : MEDIUM

  SCOPE_HIGH_UNCOMMITTED_VALUE
    Condition : (total_planned_value - total_awarded_value) / total_planned_value
                > UNCOMMITTED_RATIO_THRESHOLD (default 0.30)
                AND total_planned_value > 0
    Severity  : MEDIUM

  CANCELLED_PACKAGE_MILESTONE_LINK
    Condition : package status is cancelled or on_hold
                AND at least one linked milestone is in_progress or delayed
    Severity  : HIGH

All inputs/outputs use plain Python dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional


# ---------------------------------------------------------------------------
# Alert thresholds (module-level constants for easy adjustment)
# ---------------------------------------------------------------------------

STALLED_DAYS_THRESHOLD: int = 14
DELAY_RATIO_THRESHOLD: float = 0.50
OVERRUN_RATIO_THRESHOLD: float = 0.50
UNCOMMITTED_RATIO_THRESHOLD: float = 0.30
MIN_MILESTONES_FOR_RATIO: int = 1

# ---------------------------------------------------------------------------
# Alert code constants
# ---------------------------------------------------------------------------

ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE = "UNAWARDED_PACKAGE_ACTIVE_MILESTONE"
ALERT_STALLED_PACKAGE = "STALLED_PACKAGE"
ALERT_CONTRACTOR_HIGH_DELAY_RATIO = "CONTRACTOR_HIGH_DELAY_RATIO"
ALERT_CONTRACTOR_HIGH_OVERRUN_RATIO = "CONTRACTOR_HIGH_OVERRUN_RATIO"
ALERT_SCOPE_HIGH_UNCOMMITTED_VALUE = "SCOPE_HIGH_UNCOMMITTED_VALUE"
ALERT_CANCELLED_PACKAGE_MILESTONE_LINK = "CANCELLED_PACKAGE_MILESTONE_LINK"

# Alert severity levels
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

# Statuses that count as "active" for a milestone
_ACTIVE_MILESTONE_STATUSES = {"in_progress", "delayed"}

# Package statuses where award has not yet occurred (mutually exclusive with _BLOCKED)
_UNAWARDED_PACKAGE_STATUSES = {"draft", "tendering", "evaluation"}

# Package statuses treated as stalled candidates
_STALLED_PACKAGE_STATUSES = {"tendering", "evaluation"}

# Package statuses treated as cancelled/blocked
_BLOCKED_PACKAGE_STATUSES = {"cancelled", "on_hold"}


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MilestoneRiskData:
    """Risk-relevant data for a single milestone linked to a package.

    Parameters
    ----------
    milestone_id:
        Matches ConstructionMilestone.id.
    status:
        MilestoneStatus value string (e.g. "in_progress", "delayed").
    planned_cost:
        The budgeted cost for the milestone.  None if not set.
    actual_cost:
        The recorded actual cost.  None if not recorded.
    """

    milestone_id: str
    status: str
    planned_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None


@dataclass
class PackageRiskData:
    """Risk-relevant data for a single procurement package.

    Parameters
    ----------
    package_id:
        Matches ConstructionProcurementPackage.id.
    scope_id:
        The construction scope this package belongs to.
    contractor_id:
        ID of the assigned contractor, or None if unassigned.
    status:
        ProcurementPackageStatus value string.
    planned_value:
        Planned contract value.  None if not set.
    awarded_value:
        Awarded contract value.  None if not yet awarded.
    days_since_update:
        Number of days since the package was last updated (from updated_at).
    linked_milestones:
        Milestones linked to this package.
    """

    package_id: str
    scope_id: str
    contractor_id: Optional[str]
    status: str
    planned_value: Optional[Decimal]
    awarded_value: Optional[Decimal]
    days_since_update: int
    linked_milestones: List[MilestoneRiskData] = field(default_factory=list)


@dataclass
class ContractorRiskData:
    """Risk-relevant data for a single contractor.

    Parameters
    ----------
    contractor_id:
        Matches ConstructionContractor.id.
    contractor_name:
        Human-readable contractor name.
    all_milestones:
        All milestones from all packages assigned to this contractor
        (may include duplicates if a milestone is in multiple packages,
        but the engine deduplicates by milestone_id before ratio computation).
    """

    contractor_id: str
    contractor_name: str
    all_milestones: List[MilestoneRiskData] = field(default_factory=list)


@dataclass
class ScopeRiskData:
    """Risk-relevant data for an entire construction scope.

    Parameters
    ----------
    scope_id:
        Matches ConstructionScope.id.
    packages:
        All procurement packages within this scope.
    """

    scope_id: str
    packages: List[PackageRiskData] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ConstructionRiskAlert:
    """A single construction risk alert produced by the engine.

    Parameters
    ----------
    alert_code:
        One of the ALERT_* constants defined in this module.
    severity:
        One of HIGH / MEDIUM / LOW.
    scope_id:
        The scope affected by this alert.  None for contractor-level alerts
        where a single scope cannot be determined.
    contractor_id:
        Contractor affected, if applicable.
    package_id:
        Package affected, if applicable.
    milestone_id:
        Specific milestone affected, if applicable.
    message:
        Human-readable description of the risk condition.
    metric_value:
        Numeric value that triggered the rule.  None if not applicable.
    threshold:
        The threshold the metric exceeded.  None if not applicable.
    """

    alert_code: str
    severity: str
    scope_id: Optional[str] = None
    contractor_id: Optional[str] = None
    package_id: Optional[str] = None
    milestone_id: Optional[str] = None
    message: str = ""
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class ContractorPerformanceSummary:
    """Derived performance summary for a single contractor.

    Parameters
    ----------
    contractor_id:
        Matches ConstructionContractor.id.
    contractor_name:
        Human-readable contractor name.
    total_milestones:
        Total number of unique milestones linked via contractor's packages.
    delayed_milestones:
        Count of milestones with status ``delayed``.
    over_budget_milestones:
        Count of milestones where actual_cost > planned_cost (both set).
    delay_ratio:
        delayed_milestones / total_milestones.  None if total_milestones == 0.
    overrun_ratio:
        over_budget_milestones / assessed_milestones where both cost fields
        are set.  None if no milestones have both cost fields.
    alerts:
        Risk alerts generated for this contractor.
    """

    contractor_id: str
    contractor_name: str
    total_milestones: int
    delayed_milestones: int
    over_budget_milestones: int
    delay_ratio: Optional[float]
    overrun_ratio: Optional[float]
    alerts: List[ConstructionRiskAlert] = field(default_factory=list)


@dataclass
class ProcurementRiskSummary:
    """Aggregated procurement risk overview for a construction scope.

    Parameters
    ----------
    scope_id:
        Matches ConstructionScope.id.
    total_packages:
        Total number of packages in the scope.
    unawarded_packages:
        Packages that are not yet in awarded/completed status.
    stalled_packages:
        Packages stuck in tendering/evaluation beyond the stalled threshold.
    cancelled_or_on_hold_packages:
        Packages with status cancelled or on_hold.
    total_planned_value:
        Sum of planned_value across all packages.
    total_awarded_value:
        Sum of awarded_value across all awarded packages.
    uncommitted_value:
        total_planned_value - total_awarded_value.
    alerts:
        Risk alerts generated for this scope's packages.
    """

    scope_id: str
    total_packages: int
    unawarded_packages: int
    stalled_packages: int
    cancelled_or_on_hold_packages: int
    total_planned_value: Decimal
    total_awarded_value: Decimal
    uncommitted_value: Decimal
    alerts: List[ConstructionRiskAlert] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _has_active_milestone(milestones: List[MilestoneRiskData]) -> bool:
    """Return True if any linked milestone is in_progress or delayed."""
    return any(m.status in _ACTIVE_MILESTONE_STATUSES for m in milestones)


def _is_over_budget(m: MilestoneRiskData) -> bool:
    """Return True if the milestone has both costs set and is over budget."""
    return (
        m.planned_cost is not None
        and m.actual_cost is not None
        and m.actual_cost > m.planned_cost
    )


def _deduplicate_milestones(
    milestones: List[MilestoneRiskData],
) -> List[MilestoneRiskData]:
    """Return unique milestones by milestone_id (first occurrence wins)."""
    seen: set[str] = set()
    result: List[MilestoneRiskData] = []
    for m in milestones:
        if m.milestone_id not in seen:
            seen.add(m.milestone_id)
            result.append(m)
    return result


# ---------------------------------------------------------------------------
# Package-level alert rules
# ---------------------------------------------------------------------------


def _check_unawarded_package_active_milestone(
    pkg: PackageRiskData,
) -> Optional[ConstructionRiskAlert]:
    """Rule: unawarded package with active linked milestone."""
    if pkg.status not in _UNAWARDED_PACKAGE_STATUSES:
        return None
    active = [m for m in pkg.linked_milestones if m.status in _ACTIVE_MILESTONE_STATUSES]
    if not active:
        return None
    example_mid = active[0].milestone_id
    return ConstructionRiskAlert(
        alert_code=ALERT_UNAWARDED_PACKAGE_ACTIVE_MILESTONE,
        severity=SEVERITY_HIGH,
        scope_id=pkg.scope_id,
        contractor_id=pkg.contractor_id,
        package_id=pkg.package_id,
        milestone_id=example_mid,
        message=(
            f"Package '{pkg.package_id}' is not yet awarded (status: {pkg.status}) "
            f"but {len(active)} linked milestone(s) are active. "
            f"Award delay threatens milestone delivery."
        ),
        metric_value=float(len(active)),
        threshold=0.0,
    )


def _check_stalled_package(
    pkg: PackageRiskData,
) -> Optional[ConstructionRiskAlert]:
    """Rule: package stalled in tendering/evaluation too long."""
    if pkg.status not in _STALLED_PACKAGE_STATUSES:
        return None
    if pkg.days_since_update <= STALLED_DAYS_THRESHOLD:
        return None
    return ConstructionRiskAlert(
        alert_code=ALERT_STALLED_PACKAGE,
        severity=SEVERITY_MEDIUM,
        scope_id=pkg.scope_id,
        contractor_id=pkg.contractor_id,
        package_id=pkg.package_id,
        message=(
            f"Package '{pkg.package_id}' has been in '{pkg.status}' status "
            f"for {pkg.days_since_update} days, exceeding the "
            f"{STALLED_DAYS_THRESHOLD}-day threshold."
        ),
        metric_value=float(pkg.days_since_update),
        threshold=float(STALLED_DAYS_THRESHOLD),
    )


def _check_cancelled_package_milestone_link(
    pkg: PackageRiskData,
) -> Optional[ConstructionRiskAlert]:
    """Rule: cancelled/on-hold package still linked to active milestones."""
    if pkg.status not in _BLOCKED_PACKAGE_STATUSES:
        return None
    active = [m for m in pkg.linked_milestones if m.status in _ACTIVE_MILESTONE_STATUSES]
    if not active:
        return None
    example_mid = active[0].milestone_id
    return ConstructionRiskAlert(
        alert_code=ALERT_CANCELLED_PACKAGE_MILESTONE_LINK,
        severity=SEVERITY_HIGH,
        scope_id=pkg.scope_id,
        contractor_id=pkg.contractor_id,
        package_id=pkg.package_id,
        milestone_id=example_mid,
        message=(
            f"Package '{pkg.package_id}' is '{pkg.status}' but "
            f"{len(active)} linked milestone(s) are still active. "
            f"Milestone delivery is at risk."
        ),
        metric_value=float(len(active)),
        threshold=0.0,
    )


# ---------------------------------------------------------------------------
# Scope-level alert rules
# ---------------------------------------------------------------------------


def _check_scope_high_uncommitted_value(
    scope: ScopeRiskData,
) -> Optional[ConstructionRiskAlert]:
    """Rule: scope has high proportion of uncommitted procurement value."""
    total_planned = sum(
        (p.planned_value or Decimal("0.00")) for p in scope.packages
    )
    total_awarded = sum(
        (p.awarded_value or Decimal("0.00")) for p in scope.packages
    )
    if total_planned <= Decimal("0.00"):
        return None

    uncommitted = total_planned - total_awarded
    ratio = float(uncommitted / total_planned)

    if ratio <= UNCOMMITTED_RATIO_THRESHOLD:
        return None

    return ConstructionRiskAlert(
        alert_code=ALERT_SCOPE_HIGH_UNCOMMITTED_VALUE,
        severity=SEVERITY_MEDIUM,
        scope_id=scope.scope_id,
        message=(
            f"Scope '{scope.scope_id}' has {round(ratio * 100, 1)}% of planned "
            f"procurement value uncommitted ({uncommitted:.2f} of {total_planned:.2f}), "
            f"exceeding the {int(UNCOMMITTED_RATIO_THRESHOLD * 100)}% threshold."
        ),
        metric_value=round(ratio, 4),
        threshold=UNCOMMITTED_RATIO_THRESHOLD,
    )


# ---------------------------------------------------------------------------
# Contractor-level alert rules
# ---------------------------------------------------------------------------


def _compute_contractor_performance(
    data: ContractorRiskData,
) -> ContractorPerformanceSummary:
    """Compute performance metrics and alerts for a single contractor."""
    milestones = _deduplicate_milestones(data.all_milestones)
    total = len(milestones)
    delayed = sum(1 for m in milestones if m.status == "delayed")
    costed = [m for m in milestones if m.planned_cost is not None and m.actual_cost is not None]
    over_budget = sum(1 for m in costed if _is_over_budget(m))

    delay_ratio: Optional[float] = (
        delayed / total if total >= MIN_MILESTONES_FOR_RATIO else None
    )
    overrun_ratio: Optional[float] = (
        over_budget / len(costed) if len(costed) >= MIN_MILESTONES_FOR_RATIO else None
    )

    alerts: List[ConstructionRiskAlert] = []

    if delay_ratio is not None and delay_ratio > DELAY_RATIO_THRESHOLD:
        alerts.append(
            ConstructionRiskAlert(
                alert_code=ALERT_CONTRACTOR_HIGH_DELAY_RATIO,
                severity=SEVERITY_HIGH,
                contractor_id=data.contractor_id,
                message=(
                    f"Contractor '{data.contractor_name}' has a delay ratio of "
                    f"{round(delay_ratio * 100, 1)}% ({delayed}/{total} milestones delayed), "
                    f"exceeding the {int(DELAY_RATIO_THRESHOLD * 100)}% threshold."
                ),
                metric_value=round(delay_ratio, 4),
                threshold=DELAY_RATIO_THRESHOLD,
            )
        )

    if overrun_ratio is not None and overrun_ratio > OVERRUN_RATIO_THRESHOLD:
        alerts.append(
            ConstructionRiskAlert(
                alert_code=ALERT_CONTRACTOR_HIGH_OVERRUN_RATIO,
                severity=SEVERITY_MEDIUM,
                contractor_id=data.contractor_id,
                message=(
                    f"Contractor '{data.contractor_name}' has an overrun ratio of "
                    f"{round(overrun_ratio * 100, 1)}% ({over_budget}/{len(costed)} "
                    f"milestones over budget), exceeding the "
                    f"{int(OVERRUN_RATIO_THRESHOLD * 100)}% threshold."
                ),
                metric_value=round(overrun_ratio, 4),
                threshold=OVERRUN_RATIO_THRESHOLD,
            )
        )

    return ContractorPerformanceSummary(
        contractor_id=data.contractor_id,
        contractor_name=data.contractor_name,
        total_milestones=total,
        delayed_milestones=delayed,
        over_budget_milestones=over_budget,
        delay_ratio=delay_ratio,
        overrun_ratio=overrun_ratio,
        alerts=alerts,
    )


# ---------------------------------------------------------------------------
# Scope-level entry points
# ---------------------------------------------------------------------------


def evaluate_scope_risk_alerts(scope: ScopeRiskData) -> List[ConstructionRiskAlert]:
    """Evaluate all risk rules for packages within a construction scope.

    Parameters
    ----------
    scope:
        Scope data including all packages and their linked milestones.

    Returns
    -------
    List[ConstructionRiskAlert]
        All alerts triggered by the scope's packages, ordered by severity
        (HIGH first, then MEDIUM, then LOW) and by package_id within each
        severity group.
    """
    alerts: List[ConstructionRiskAlert] = []

    # Per-package rules
    for pkg in scope.packages:
        for rule in (
            _check_unawarded_package_active_milestone,
            _check_stalled_package,
            _check_cancelled_package_milestone_link,
        ):
            alert = rule(pkg)
            if alert is not None:
                alerts.append(alert)

    # Scope-level uncommitted-value rule
    scope_alert = _check_scope_high_uncommitted_value(scope)
    if scope_alert is not None:
        alerts.append(scope_alert)

    return _sort_alerts(alerts)


def evaluate_procurement_risk(scope: ScopeRiskData) -> ProcurementRiskSummary:
    """Compute procurement risk overview for a construction scope.

    Parameters
    ----------
    scope:
        Scope data including all packages and their linked milestones.

    Returns
    -------
    ProcurementRiskSummary
        Aggregated procurement risk summary with counts and alerts.
    """
    total_planned = sum(
        (p.planned_value or Decimal("0.00")) for p in scope.packages
    )
    total_awarded = sum(
        (p.awarded_value or Decimal("0.00")) for p in scope.packages
    )

    unawarded = sum(1 for p in scope.packages if p.status in _UNAWARDED_PACKAGE_STATUSES)
    stalled = sum(
        1
        for p in scope.packages
        if p.status in _STALLED_PACKAGE_STATUSES
        and p.days_since_update > STALLED_DAYS_THRESHOLD
    )
    cancelled_or_on_hold = sum(
        1 for p in scope.packages if p.status in _BLOCKED_PACKAGE_STATUSES
    )

    alerts = evaluate_scope_risk_alerts(scope)

    return ProcurementRiskSummary(
        scope_id=scope.scope_id,
        total_packages=len(scope.packages),
        unawarded_packages=unawarded,
        stalled_packages=stalled,
        cancelled_or_on_hold_packages=cancelled_or_on_hold,
        total_planned_value=total_planned,
        total_awarded_value=total_awarded,
        uncommitted_value=total_planned - total_awarded,
        alerts=alerts,
    )


def evaluate_contractor_performance(
    data: ContractorRiskData,
) -> ContractorPerformanceSummary:
    """Compute performance summary and risk alerts for a single contractor.

    Parameters
    ----------
    data:
        Contractor risk data including all milestones from linked packages.

    Returns
    -------
    ContractorPerformanceSummary
        Performance metrics and generated risk alerts for the contractor.
    """
    return _compute_contractor_performance(data)


# ---------------------------------------------------------------------------
# Sorting helper
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 2}


def _sort_alerts(alerts: List[ConstructionRiskAlert]) -> List[ConstructionRiskAlert]:
    """Sort alerts by severity (HIGH first) then by package_id."""
    return sorted(
        alerts,
        key=lambda a: (
            _SEVERITY_ORDER.get(a.severity, 99),
            a.package_id or "",
            a.alert_code,
        ),
    )
