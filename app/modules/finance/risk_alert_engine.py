"""
finance.risk_alert_engine

Financial Risk & Alerting Engine.

Responsibilities:
  - Scan project-level financial KPIs produced by the existing finance engines.
  - Detect structured risk conditions and return typed alerts.
  - Aggregate per-project alerts across the entire portfolio.

Alert rules (all thresholds configurable as module-level constants):

  OVERDUE_EXPOSURE
    Condition : overdue_percentage > OVERDUE_THRESHOLD (default 20 %)
    Severity  : HIGH

  COLLECTION_EFFICIENCY_COLLAPSE
    Condition : collection_efficiency < EFFICIENCY_THRESHOLD (default 0.60)
    Severity  : MEDIUM

  RECEIVABLES_SURGE
    Condition : most-recent receivables snapshot > previous snapshot × (1 + GROWTH_THRESHOLD)
    Severity  : HIGH

  LIQUIDITY_STRESS
    Condition : forecast_next_month < receivables_exposure × LIQUIDITY_THRESHOLD (default 0.25)
    Severity  : MEDIUM

All operations are read-only.  No background processing is introduced.
"""

from __future__ import annotations

from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.finance.models import FactReceivablesSnapshot
from app.modules.finance.project_financial_dashboard_service import (
    ProjectFinancialDashboardService,
)
from app.modules.finance.schemas import PortfolioRiskResponse, ProjectRiskAlert
from app.modules.projects.models import Project

# ---------------------------------------------------------------------------
# Alert thresholds (module-level constants for easy adjustment)
# ---------------------------------------------------------------------------

OVERDUE_THRESHOLD: float = 20.0       # overdue_percentage (0–100 scale)
EFFICIENCY_THRESHOLD: float = 0.60    # collection_efficiency (0–1 scale)
GROWTH_THRESHOLD: float = 0.30        # receivables growth fraction (0–1 scale)
LIQUIDITY_THRESHOLD: float = 0.25     # forecast / receivables ratio

# ---------------------------------------------------------------------------
# Alert type keys (string constants)
# ---------------------------------------------------------------------------

ALERT_OVERDUE_EXPOSURE = "OVERDUE_EXPOSURE"
ALERT_COLLECTION_EFFICIENCY = "COLLECTION_EFFICIENCY_COLLAPSE"
ALERT_RECEIVABLES_SURGE = "RECEIVABLES_SURGE"
ALERT_LIQUIDITY_STRESS = "LIQUIDITY_STRESS"


class FinancialRiskAlertEngine:
    """Scans project financial metrics and produces structured risk alerts.

    Internally delegates to ProjectFinancialDashboardService for per-project
    KPIs and queries the fact_receivables_snapshot table directly for
    receivables growth detection.

    All operations are read-only.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._dashboard_svc = ProjectFinancialDashboardService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_project_risks(self, project_id: str) -> List[ProjectRiskAlert]:
        """Return risk alerts for a single project.

        Raises HTTP 404 if the project does not exist.
        """
        # Validate project exists before computing KPIs.
        project = (
            self.db.query(Project).filter(Project.id == project_id).first()
        )
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found.",
            )

        kpis = self._dashboard_svc.get_project_financial_kpis(project_id)
        alerts: List[ProjectRiskAlert] = []

        # --- Rule 1: Overdue Exposure ---
        if kpis.overdue_percentage > OVERDUE_THRESHOLD:
            alerts.append(
                ProjectRiskAlert(
                    project_id=project_id,
                    alert_type=ALERT_OVERDUE_EXPOSURE,
                    severity="HIGH",
                    message=(
                        f"Overdue receivables represent "
                        f"{round(kpis.overdue_percentage, 2)}% of total exposure, "
                        f"exceeding the {OVERDUE_THRESHOLD}% threshold."
                    ),
                    metric_value=round(kpis.overdue_percentage, 4),
                    threshold=OVERDUE_THRESHOLD,
                )
            )

        # --- Rule 2: Collection Efficiency Collapse ---
        if kpis.collection_efficiency < EFFICIENCY_THRESHOLD:
            alerts.append(
                ProjectRiskAlert(
                    project_id=project_id,
                    alert_type=ALERT_COLLECTION_EFFICIENCY,
                    severity="MEDIUM",
                    message=(
                        f"Collection efficiency is "
                        f"{round(kpis.collection_efficiency * 100, 2)}%, "
                        f"below the {int(EFFICIENCY_THRESHOLD * 100)}% threshold."
                    ),
                    metric_value=round(kpis.collection_efficiency, 4),
                    threshold=EFFICIENCY_THRESHOLD,
                )
            )

        # --- Rule 3: Receivables Surge ---
        growth = self._receivables_growth(project_id)
        if growth is not None and growth > GROWTH_THRESHOLD:
            alerts.append(
                ProjectRiskAlert(
                    project_id=project_id,
                    alert_type=ALERT_RECEIVABLES_SURGE,
                    severity="HIGH",
                    message=(
                        f"Receivables grew by {round(growth * 100, 2)}% "
                        f"compared to the previous snapshot, exceeding the "
                        f"{int(GROWTH_THRESHOLD * 100)}% threshold."
                    ),
                    metric_value=round(growth, 4),
                    threshold=GROWTH_THRESHOLD,
                )
            )

        # --- Rule 4: Liquidity Stress ---
        if kpis.receivables_exposure > 0:
            liquidity_ratio = (
                kpis.forecast_next_month / kpis.receivables_exposure
            )
            if liquidity_ratio < LIQUIDITY_THRESHOLD:
                alerts.append(
                    ProjectRiskAlert(
                        project_id=project_id,
                        alert_type=ALERT_LIQUIDITY_STRESS,
                        severity="MEDIUM",
                        message=(
                            f"Next-month forecast ({round(kpis.forecast_next_month, 2)}) "
                            f"is only {round(liquidity_ratio * 100, 2)}% of receivables "
                            f"exposure ({round(kpis.receivables_exposure, 2)}), "
                            f"below the {int(LIQUIDITY_THRESHOLD * 100)}% threshold."
                        ),
                        metric_value=round(liquidity_ratio, 4),
                        threshold=LIQUIDITY_THRESHOLD,
                    )
                )

        return alerts

    def scan_portfolio_risks(self) -> PortfolioRiskResponse:
        """Run risk analysis across all projects.

        Returns a PortfolioRiskResponse whose ``alerts`` list is the
        concatenation of all per-project alerts, sorted by project_id.
        Projects with no alerts contribute nothing to the list.
        """
        project_ids = self._all_project_ids()
        all_alerts: List[ProjectRiskAlert] = []
        for pid in project_ids:
            all_alerts.extend(self.scan_project_risks(pid))
        return PortfolioRiskResponse(alerts=all_alerts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _receivables_growth(self, project_id: str) -> float | None:
        """Return the fractional growth in receivables from the penultimate to
        the most recent snapshot for the given project.

        Returns ``None`` if fewer than two snapshots exist (growth cannot be
        determined) or if the penultimate snapshot has zero receivables.
        """
        rows = (
            self.db.query(FactReceivablesSnapshot.total_receivables)
            .filter(FactReceivablesSnapshot.project_id == project_id)
            .order_by(FactReceivablesSnapshot.snapshot_date.desc())
            .limit(2)
            .all()
        )

        if len(rows) < 2:
            return None

        latest = float(rows[0].total_receivables)
        previous = float(rows[1].total_receivables)

        if previous == 0.0:
            return None

        return (latest - previous) / previous

    def _all_project_ids(self) -> List[str]:
        """Return IDs of all projects ordered by ID for deterministic output."""
        rows = self.db.query(Project.id).order_by(Project.id).all()
        return [str(row.id) for row in rows]
