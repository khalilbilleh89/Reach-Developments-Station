"""
collections.collections_alert_engine

Pure-function alert generation engine for overdue installments.

Alert rules
-----------
Condition              Alert Type          Severity
---------------------------------------------------
 7 days overdue        overdue_7_days      warning
30 days overdue        overdue_30_days     critical
90 days overdue        overdue_90_days     high_risk

Rules are *inclusive*: an installment qualifies for the highest-severity
tier it has crossed.  The engine never modifies database state; callers
are responsible for persisting the returned alert records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.shared.enums.finance import AlertSeverity, AlertType


# Day thresholds — inclusive.
THRESHOLD_WARNING: int = 7
THRESHOLD_CRITICAL: int = 30
THRESHOLD_HIGH_RISK: int = 90


@dataclass(frozen=True)
class AlertCandidate:
    """Value object describing an installment that requires an alert."""

    contract_id: str
    installment_id: str
    days_overdue: int
    outstanding_balance: float
    alert_type: AlertType
    severity: AlertSeverity


def classify_alert_severity(days_overdue: int) -> AlertSeverity | None:
    """Return the alert severity for a given days-overdue count.

    Returns ``None`` when the installment is not yet overdue enough to
    trigger any alert tier (i.e. ``days_overdue < THRESHOLD_WARNING``).

    The most severe tier that applies is returned:
      - >= 90 days → HIGH_RISK
      - >= 30 days → CRITICAL
      - >=  7 days → WARNING
    """
    if days_overdue >= THRESHOLD_HIGH_RISK:
        return AlertSeverity.HIGH_RISK
    if days_overdue >= THRESHOLD_CRITICAL:
        return AlertSeverity.CRITICAL
    if days_overdue >= THRESHOLD_WARNING:
        return AlertSeverity.WARNING
    return None


def _severity_to_alert_type(severity: AlertSeverity) -> AlertType:
    """Map a severity to its canonical alert-type constant."""
    return {
        AlertSeverity.WARNING: AlertType.OVERDUE_7_DAYS,
        AlertSeverity.CRITICAL: AlertType.OVERDUE_30_DAYS,
        AlertSeverity.HIGH_RISK: AlertType.OVERDUE_90_DAYS,
    }[severity]


@dataclass(frozen=True)
class InstallmentSnapshot:
    """Minimal installment data needed by the alert engine."""

    id: str
    contract_id: str
    due_date: date
    outstanding_balance: float


def generate_overdue_alerts(
    installments: list[InstallmentSnapshot],
    reference_date: date,
) -> list[AlertCandidate]:
    """Evaluate a batch of installments and return alert candidates.

    Parameters
    ----------
    installments:
        Outstanding installment snapshots to evaluate.  Only installments
        with ``due_date < reference_date`` can generate alerts.
    reference_date:
        The date used as "today".  Normally ``date.today()``.

    Returns
    -------
    list[AlertCandidate]
        One candidate per installment that crosses at least one alert
        threshold.  Installments below THRESHOLD_WARNING are omitted.
    """
    candidates: list[AlertCandidate] = []

    for inst in installments:
        days_overdue = (reference_date - inst.due_date).days
        severity = classify_alert_severity(days_overdue)
        if severity is None:
            continue
        alert_type = _severity_to_alert_type(severity)
        candidates.append(
            AlertCandidate(
                contract_id=inst.contract_id,
                installment_id=inst.id,
                days_overdue=days_overdue,
                outstanding_balance=inst.outstanding_balance,
                alert_type=alert_type,
                severity=severity,
            )
        )

    return candidates
