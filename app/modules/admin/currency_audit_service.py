"""
admin.currency_audit_service

Currency integrity audit service.

Scans all project-linked financial records and reports anomalies:
  - mismatch           — record.currency differs from project.base_currency
  - suspicious_default — record.currency is the platform default but
                         project.base_currency is not the platform default
                         (suggests the record was not initialised with the
                         project's governing currency)
  - null_currency      — record.currency is NULL or empty (should not occur
                         with current schema constraints, but checked for
                         defence-in-depth)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.constants.currency import DEFAULT_CURRENCY


def scan_currency_integrity(db: Session) -> list[dict[str, Any]]:
    """Scan all project-linked financial records for currency anomalies.

    Returns a list of issue dicts.  Each dict has the shape::

        {
            "type":             "mismatch" | "suspicious_default" | "null_currency",
            "project_id":       str,
            "project_currency": str | None,
            "record_type":      str,          # logical name of the table
            "record_id":        str,
            "currency":         str | None,   # the record's own currency value
        }

    An empty list means no anomalies were detected.
    """
    issues: list[dict[str, Any]] = []

    _scan_feasibility_runs(db, issues)
    _scan_construction_cost_records(db, issues)
    _scan_construction_cost_comparison_sets(db, issues)
    _scan_land_parcels(db, issues)
    _scan_financial_scenario_runs(db, issues)

    return issues


# ---------------------------------------------------------------------------
# Per-table scanners
# ---------------------------------------------------------------------------


def _add_issue(
    issues: list[dict[str, Any]],
    *,
    record_type: str,
    record_id: str,
    project_id: str,
    project_currency: str | None,
    record_currency: str | None,
) -> None:
    """Classify and append a currency issue to the issues list."""
    if not record_currency:
        issue_type = "null_currency"
    elif project_currency and record_currency != project_currency:
        if record_currency == DEFAULT_CURRENCY and project_currency != DEFAULT_CURRENCY:
            issue_type = "suspicious_default"
        else:
            issue_type = "mismatch"
    else:
        return

    issues.append(
        {
            "type": issue_type,
            "project_id": project_id,
            "project_currency": project_currency,
            "record_type": record_type,
            "record_id": record_id,
            "currency": record_currency,
        }
    )


def _scan_feasibility_runs(db: Session, issues: list[dict[str, Any]]) -> None:
    from app.modules.feasibility.models import FeasibilityRun, FeasibilityAssumptions
    from app.modules.projects.models import Project

    rows = (
        db.query(
            FeasibilityAssumptions.id,
            FeasibilityRun.project_id,
            FeasibilityAssumptions.currency,
            Project.base_currency,
        )
        .join(
            FeasibilityAssumptions,
            FeasibilityAssumptions.run_id == FeasibilityRun.id,
        )
        .join(Project, Project.id == FeasibilityRun.project_id)
        .filter(FeasibilityRun.project_id.isnot(None))
        .all()
    )

    for assumptions_id, project_id, currency, base_currency in rows:
        _add_issue(
            issues,
            record_type="feasibility_assumptions",
            record_id=assumptions_id,
            project_id=project_id,
            project_currency=base_currency,
            record_currency=currency,
        )


def _scan_construction_cost_records(db: Session, issues: list[dict[str, Any]]) -> None:
    from app.modules.construction_costs.models import ConstructionCostRecord
    from app.modules.projects.models import Project

    rows = (
        db.query(
            ConstructionCostRecord.id,
            ConstructionCostRecord.project_id,
            ConstructionCostRecord.currency,
            Project.base_currency,
        )
        .join(Project, Project.id == ConstructionCostRecord.project_id)
        .all()
    )

    for record_id, project_id, currency, base_currency in rows:
        _add_issue(
            issues,
            record_type="construction_cost_record",
            record_id=record_id,
            project_id=project_id,
            project_currency=base_currency,
            record_currency=currency,
        )


def _scan_construction_cost_comparison_sets(
    db: Session, issues: list[dict[str, Any]]
) -> None:
    from app.modules.tender_comparison.models import ConstructionCostComparisonSet
    from app.modules.projects.models import Project

    rows = (
        db.query(
            ConstructionCostComparisonSet.id,
            ConstructionCostComparisonSet.project_id,
            ConstructionCostComparisonSet.currency,
            Project.base_currency,
        )
        .join(Project, Project.id == ConstructionCostComparisonSet.project_id)
        .all()
    )

    for record_id, project_id, currency, base_currency in rows:
        _add_issue(
            issues,
            record_type="construction_cost_comparison_set",
            record_id=record_id,
            project_id=project_id,
            project_currency=base_currency,
            record_currency=currency,
        )


def _scan_land_parcels(db: Session, issues: list[dict[str, Any]]) -> None:
    from app.modules.land.models import LandParcel
    from app.modules.projects.models import Project

    rows = (
        db.query(
            LandParcel.id,
            LandParcel.project_id,
            LandParcel.currency,
            Project.base_currency,
        )
        .join(Project, Project.id == LandParcel.project_id)
        .filter(LandParcel.project_id.isnot(None))
        .all()
    )

    for record_id, project_id, currency, base_currency in rows:
        _add_issue(
            issues,
            record_type="land_parcel",
            record_id=record_id,
            project_id=project_id,
            project_currency=base_currency,
            record_currency=currency,
        )


def _scan_financial_scenario_runs(db: Session, issues: list[dict[str, Any]]) -> None:
    from app.modules.scenario.models import FinancialScenarioRun, Scenario
    from app.modules.projects.models import Project

    rows = (
        db.query(
            FinancialScenarioRun.id,
            Scenario.project_id,
            FinancialScenarioRun.currency,
            Project.base_currency,
        )
        .join(Scenario, Scenario.id == FinancialScenarioRun.scenario_id)
        .join(Project, Project.id == Scenario.project_id)
        .filter(Scenario.project_id.isnot(None))
        .all()
    )

    for record_id, project_id, currency, base_currency in rows:
        _add_issue(
            issues,
            record_type="financial_scenario_run",
            record_id=record_id,
            project_id=project_id,
            project_currency=base_currency,
            record_currency=currency,
        )
