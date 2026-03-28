"""
construction_costs.analytics_service

Construction Analytics & Project Scorecard service (PR-V6-14).

Responsibility
--------------
Compute project-level construction health metrics by reading:
  - the project's approved tender baseline (ConstructionCostComparisonSet with
    is_approved_baseline=True and its lines)
  - the project's active construction cost records (ConstructionCostRecord)

All scoring and classification logic is centralised here.  The frontend
renders the provided status values — no re-scoring is performed in the UI.

Classification thresholds
--------------------------
cost_status
  healthy   → cost_variance_pct ≤ 5 % (or negative)
  warning   → 5 % < cost_variance_pct ≤ 15 %
  critical  → cost_variance_pct > 15 %
  incomplete → no approved baseline

contingency_status
  healthy   → contingency_pressure_pct ≤ 10 %
  warning   → 10 % < contingency_pressure_pct ≤ 25 %
  critical  → contingency_pressure_pct > 25 %
  incomplete → no approved baseline

overall_health_status
  incomplete → has_approved_baseline is False
  critical   → any component is critical
  warning    → any component is warning
  healthy    → all components are healthy
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.construction_costs.analytics_schemas import (
    ConstructionPortfolioScorecardItem,
    ConstructionPortfolioScorecardSummary,
    ConstructionPortfolioScorecardsResponse,
    ConstructionProjectScorecardResponse,
)
from app.modules.construction_costs.models import ConstructionCostRecord
from app.modules.projects.models import Project
from app.modules.tender_comparison.models import (
    ConstructionCostComparisonLine,
    ConstructionCostComparisonSet,
)

# ---------------------------------------------------------------------------
# Classification thresholds
# ---------------------------------------------------------------------------

_COST_WARNING_PCT = Decimal("5.00")
_COST_CRITICAL_PCT = Decimal("15.00")
_CONTINGENCY_WARNING_PCT = Decimal("10.00")
_CONTINGENCY_CRITICAL_PCT = Decimal("25.00")

# Severity ordering for portfolio sort (lower index = higher severity first)
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "incomplete": 2, "healthy": 3}

# Number of top-risk projects to include in the portfolio response
_TOP_RISK_LIMIT = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _classify_cost_status(
    variance_pct: Optional[Decimal],
    has_baseline: bool,
) -> str:
    """Classify cost health status from variance percentage."""
    if not has_baseline:
        return "incomplete"
    if variance_pct is None:
        # baseline is zero — treat as healthy (no budget drift possible)
        return "healthy"
    if variance_pct > _COST_CRITICAL_PCT:
        return "critical"
    if variance_pct > _COST_WARNING_PCT:
        return "warning"
    return "healthy"


def _classify_contingency_status(
    contingency_pct: Optional[Decimal],
    has_baseline: bool,
) -> str:
    """Classify contingency pressure status."""
    if not has_baseline:
        return "incomplete"
    if contingency_pct is None:
        return "healthy"
    if contingency_pct > _CONTINGENCY_CRITICAL_PCT:
        return "critical"
    if contingency_pct > _CONTINGENCY_WARNING_PCT:
        return "warning"
    return "healthy"


def _overall_health(
    cost_status: str,
    contingency_status: str,
    has_baseline: bool,
) -> str:
    """Derive the single overall health status from component statuses."""
    if not has_baseline:
        return "incomplete"
    components = [cost_status, contingency_status]
    if "critical" in components:
        return "critical"
    if "warning" in components:
        return "warning"
    return "healthy"


def _latest_ts(*timestamps: Optional[datetime]) -> Optional[datetime]:
    """Return the most recent non-None timestamp, or None if all are None."""
    candidates = [ts for ts in timestamps if ts is not None]
    return max(candidates) if candidates else None


# ---------------------------------------------------------------------------
# Construction Analytics Service
# ---------------------------------------------------------------------------


class ConstructionAnalyticsService:
    """Service that builds construction health scorecards from governed data."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── helpers ───────────────────────────────────────────────────────────────

    def _require_project(self, project_id: str) -> Project:
        project = self.db.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return project

    def _get_active_baseline(
        self, project_id: str
    ) -> Optional[ConstructionCostComparisonSet]:
        """Return the currently approved baseline set, or None."""
        return (
            self.db.query(ConstructionCostComparisonSet)
            .filter(
                ConstructionCostComparisonSet.project_id == project_id,
                ConstructionCostComparisonSet.is_approved_baseline.is_(True),
            )
            .order_by(ConstructionCostComparisonSet.approved_at.desc())
            .first()
        )

    def _get_baseline_total(self, baseline_set: ConstructionCostComparisonSet) -> Decimal:
        """Sum the comparison_amount for all lines of the approved baseline set."""
        result = (
            self.db.query(
                func.coalesce(
                    func.sum(ConstructionCostComparisonLine.comparison_amount), 0
                )
            )
            .filter(
                ConstructionCostComparisonLine.comparison_set_id == baseline_set.id
            )
            .scalar()
        )
        return Decimal(str(result))

    def _get_forecast_total(self, project_id: str) -> Decimal:
        """Sum all active construction cost record amounts for the project."""
        result = (
            self.db.query(
                func.coalesce(
                    func.sum(ConstructionCostRecord.amount), 0
                )
            )
            .filter(
                ConstructionCostRecord.project_id == project_id,
                ConstructionCostRecord.is_active.is_(True),
            )
            .scalar()
        )
        return Decimal(str(result))

    def _get_contingency_total(self, project_id: str) -> Decimal:
        """Sum active construction cost records with category 'contingency'."""
        result = (
            self.db.query(
                func.coalesce(
                    func.sum(ConstructionCostRecord.amount), 0
                )
            )
            .filter(
                ConstructionCostRecord.project_id == project_id,
                ConstructionCostRecord.is_active.is_(True),
                ConstructionCostRecord.cost_category == "contingency",
            )
            .scalar()
        )
        return Decimal(str(result))

    def _get_latest_record_ts(self, project_id: str) -> Optional[datetime]:
        """Return the most recent updated_at from active cost records, or None."""
        result = (
            self.db.query(func.max(ConstructionCostRecord.updated_at))
            .filter(
                ConstructionCostRecord.project_id == project_id,
                ConstructionCostRecord.is_active.is_(True),
            )
            .scalar()
        )
        return result  # type: ignore[return-value]

    # ── Core scorecard builder ────────────────────────────────────────────────

    def _build_scorecard(
        self, project: Project
    ) -> ConstructionProjectScorecardResponse:
        """Compute and return the full scorecard for one project.

        This is the single source of all scoring logic for the project.
        """
        baseline_set = self._get_active_baseline(project.id)
        has_baseline = baseline_set is not None

        # ── Baseline fields ──────────────────────────────────────────────────
        approved_baseline_set_id: Optional[str] = None
        approved_baseline_amount: Optional[Decimal] = None
        approved_at: Optional[datetime] = None

        if has_baseline and baseline_set is not None:
            approved_baseline_set_id = baseline_set.id
            approved_baseline_amount = self._get_baseline_total(baseline_set)
            approved_at = baseline_set.approved_at

        # ── Current forecast ─────────────────────────────────────────────────
        current_forecast_amount = self._get_forecast_total(project.id)

        # ── Cost variance ────────────────────────────────────────────────────
        cost_variance_amount: Optional[Decimal] = None
        cost_variance_pct: Optional[Decimal] = None

        if has_baseline and approved_baseline_amount is not None:
            cost_variance_amount = current_forecast_amount - approved_baseline_amount
            if approved_baseline_amount != Decimal("0"):
                cost_variance_pct = (
                    cost_variance_amount / approved_baseline_amount
                ) * Decimal("100")

        # ── Contingency ──────────────────────────────────────────────────────
        contingency_amount = self._get_contingency_total(project.id)
        contingency_pressure_pct: Optional[Decimal] = None

        if (
            has_baseline
            and approved_baseline_amount is not None
            and approved_baseline_amount != Decimal("0")
        ):
            contingency_pressure_pct = (
                contingency_amount / approved_baseline_amount
            ) * Decimal("100")

        # ── Status classification ─────────────────────────────────────────────
        cost_status = _classify_cost_status(cost_variance_pct, has_baseline)
        contingency_status = _classify_contingency_status(
            contingency_pressure_pct, has_baseline
        )
        overall_health_status = _overall_health(
            cost_status, contingency_status, has_baseline
        )

        # ── Metadata ─────────────────────────────────────────────────────────
        latest_record_ts = self._get_latest_record_ts(project.id)
        last_updated_at = _latest_ts(
            latest_record_ts,
            approved_at,
        )

        return ConstructionProjectScorecardResponse(
            project_id=project.id,
            project_name=project.name,
            has_approved_baseline=has_baseline,
            approved_baseline_set_id=approved_baseline_set_id,
            approved_baseline_amount=approved_baseline_amount,
            approved_at=approved_at,
            current_forecast_amount=current_forecast_amount,
            cost_variance_amount=cost_variance_amount,
            cost_variance_pct=cost_variance_pct,
            cost_status=cost_status,
            contingency_amount=contingency_amount,
            contingency_pressure_pct=contingency_pressure_pct,
            contingency_status=contingency_status,
            overall_health_status=overall_health_status,
            last_updated_at=last_updated_at,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def build_project_construction_scorecard(
        self, project_id: str
    ) -> ConstructionProjectScorecardResponse:
        """Return the full construction scorecard for a single project.

        Returns an incomplete-state scorecard when no approved baseline exists.
        Raises HTTP 404 when the project does not exist.
        """
        project = self._require_project(project_id)
        return self._build_scorecard(project)

    def build_portfolio_construction_scorecards(
        self,
    ) -> ConstructionPortfolioScorecardsResponse:
        """Build construction scorecards for all projects and aggregate.

        Projects are ordered in the response by severity (critical → warning →
        incomplete → healthy) then by cost_variance_pct descending.
        """
        projects = self.db.query(Project).order_by(Project.name).all()

        items: List[ConstructionPortfolioScorecardItem] = []
        for project in projects:
            sc = self._build_scorecard(project)
            items.append(
                ConstructionPortfolioScorecardItem(
                    project_id=sc.project_id,
                    project_name=sc.project_name,
                    has_approved_baseline=sc.has_approved_baseline,
                    approved_baseline_amount=sc.approved_baseline_amount,
                    current_forecast_amount=sc.current_forecast_amount,
                    cost_variance_amount=sc.cost_variance_amount,
                    cost_variance_pct=sc.cost_variance_pct,
                    contingency_amount=sc.contingency_amount,
                    contingency_pressure_pct=sc.contingency_pressure_pct,
                    overall_health_status=sc.overall_health_status,
                )
            )

        # Sort: severity first, then by variance_pct descending
        items.sort(
            key=lambda x: (
                _SEVERITY_ORDER.get(x.overall_health_status, 99),
                -(float(x.cost_variance_pct) if x.cost_variance_pct is not None else 0),
            )
        )

        # Aggregated summary counts
        healthy_count = sum(1 for i in items if i.overall_health_status == "healthy")
        warning_count = sum(1 for i in items if i.overall_health_status == "warning")
        critical_count = sum(1 for i in items if i.overall_health_status == "critical")
        incomplete_count = sum(
            1 for i in items if i.overall_health_status == "incomplete"
        )

        summary = ConstructionPortfolioScorecardSummary(
            total_projects_scored=len(items),
            healthy_count=healthy_count,
            warning_count=warning_count,
            critical_count=critical_count,
            incomplete_count=incomplete_count,
            projects_missing_baseline=incomplete_count,
        )

        # Top risk: critical + warning projects, capped at _TOP_RISK_LIMIT
        top_risk = [
            i
            for i in items
            if i.overall_health_status in ("critical", "warning")
        ][:_TOP_RISK_LIMIT]

        # Missing baseline projects
        missing_baseline = [i for i in items if not i.has_approved_baseline]

        return ConstructionPortfolioScorecardsResponse(
            summary=summary,
            projects=items,
            top_risk_projects=top_risk,
            missing_baseline_projects=missing_baseline,
        )
