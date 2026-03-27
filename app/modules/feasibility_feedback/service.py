"""
feasibility_feedback.service

Assembles project-level sales absorption and collection feedback.

All methods are read-only — no source records are mutated.

Feedback badge rules are intentionally simple and transparent:
  'at_risk'         : sell-through < 20 % OR overdue receivables > 0
  'needs_attention' : sell-through < 50 %
  'on_track'        : sell-through >= 50 % and no overdue receivables
  null              : project has no units (cannot derive a signal)

Thresholds are defined as module-level constants so they are easy to audit.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.modules.feasibility.models import FeasibilityRun
from app.modules.feasibility_feedback.repository import FeasibilityFeedbackRepository
from app.modules.feasibility_feedback.schemas import (
    ProjectAbsorptionFeedback,
    ProjectCollectionFeedback,
    ProjectFeasibilityFeedbackResponse,
)


# ---------------------------------------------------------------------------
# Feedback badge thresholds (transparent, documented)
# ---------------------------------------------------------------------------
_AT_RISK_SELL_THROUGH_THRESHOLD = 0.20    # below 20 % → at_risk
_NEEDS_ATTENTION_SELL_THROUGH_THRESHOLD = 0.50  # below 50 % → needs_attention

# Exported for use in response (transparency)
_FEEDBACK_THRESHOLDS = {
    "at_risk_sell_through_pct": _AT_RISK_SELL_THROUGH_THRESHOLD * 100,
    "needs_attention_sell_through_pct": _NEEDS_ATTENTION_SELL_THROUGH_THRESHOLD * 100,
    "at_risk_on_overdue_receivables": True,
}


def _safe_pct(numerator: float, denominator: float) -> Optional[float]:
    """Return numerator / denominator * 100, or None when denominator is zero."""
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


class FeasibilityFeedbackService:
    """Service that assembles project-level feedback from source domain records."""

    def __init__(self, db: Session) -> None:
        self.repo = FeasibilityFeedbackRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_project_feedback(
        self, project_id: str
    ) -> ProjectFeasibilityFeedbackResponse:
        """Return sales absorption and collection feedback for a single project.

        Raises HTTP 404 if the project does not exist.
        All feedback values are derived on request from live source data.
        """
        project = self.repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        absorption = self._build_absorption_feedback(project_id)
        collections = self._build_collection_feedback(project_id)
        feedback_status = self._derive_feedback_status(absorption, collections)
        feedback_notes = self._derive_feedback_notes(absorption, collections, feedback_status)
        lineage_run = self.repo.get_latest_feasibility_run_for_project(project_id)
        feasibility_lineage_note = self._derive_lineage_note(lineage_run)

        return ProjectFeasibilityFeedbackResponse(
            project_id=project.id,
            project_name=project.name,
            project_code=project.code,
            project_status=project.status,
            absorption=absorption,
            collections=collections,
            feedback_status=feedback_status,
            feedback_notes=feedback_notes,
            latest_feasibility_run_id=lineage_run.id if lineage_run else None,
            latest_scenario_id=lineage_run.scenario_id if lineage_run else None,
            feasibility_lineage_note=feasibility_lineage_note,
            feedback_thresholds=_FEEDBACK_THRESHOLDS,
        )

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_absorption_feedback(
        self, project_id: str
    ) -> ProjectAbsorptionFeedback:
        """Compute unit absorption signals for the project."""
        unit_counts = self.repo.count_units_by_status_for_project(project_id)
        total_units = sum(unit_counts.values())
        available = unit_counts.get("available", 0)
        reserved = unit_counts.get("reserved", 0)
        under_contract = unit_counts.get("under_contract", 0)
        registered = unit_counts.get("registered", 0)

        sold_units = under_contract + registered
        sell_through_pct = _safe_pct(sold_units, total_units)
        contracted_revenue = self.repo.sum_contracted_revenue_for_project(project_id)

        return ProjectAbsorptionFeedback(
            total_units=total_units,
            sold_units=sold_units,
            reserved_units=reserved,
            available_units=available,
            contracted_revenue=contracted_revenue,
            sell_through_pct=sell_through_pct,
        )

    def _build_collection_feedback(
        self, project_id: str
    ) -> ProjectCollectionFeedback:
        """Compute collections and overdue signals for the project."""
        collected_cash = self.repo.sum_collected_cash_for_project(project_id)
        outstanding_balance = self.repo.sum_outstanding_balance_for_project(project_id)
        overdue_count = self.repo.count_overdue_receivables_for_project(project_id)
        overdue_balance = self.repo.sum_overdue_balance_for_project(project_id)
        collection_rate_pct = _safe_pct(
            collected_cash, collected_cash + outstanding_balance
        )

        return ProjectCollectionFeedback(
            collected_cash=collected_cash,
            outstanding_balance=outstanding_balance,
            overdue_receivable_count=overdue_count,
            overdue_balance=overdue_balance,
            collection_rate_pct=collection_rate_pct,
        )

    # ------------------------------------------------------------------
    # Feedback badge derivation
    # ------------------------------------------------------------------

    def _derive_feedback_status(
        self,
        absorption: ProjectAbsorptionFeedback,
        collections: ProjectCollectionFeedback,
    ) -> Optional[str]:
        """Return feedback badge string or None when no units exist."""
        if absorption.sell_through_pct is None:
            return None

        sell_through_ratio = absorption.sell_through_pct / 100.0

        if (
            sell_through_ratio < _AT_RISK_SELL_THROUGH_THRESHOLD
            or collections.overdue_receivable_count > 0
        ):
            return "at_risk"
        if sell_through_ratio < _NEEDS_ATTENTION_SELL_THROUGH_THRESHOLD:
            return "needs_attention"
        return "on_track"

    # ------------------------------------------------------------------
    # Explanatory notes
    # ------------------------------------------------------------------

    def _derive_feedback_notes(
        self,
        absorption: ProjectAbsorptionFeedback,
        collections: ProjectCollectionFeedback,
        feedback_status: Optional[str],
    ) -> str:
        """Return a human-readable explanation of the feedback status."""
        if feedback_status is None:
            return (
                "No units are recorded for this project. "
                "Absorption feedback cannot be derived until inventory is added."
            )
        if feedback_status == "at_risk":
            reasons = []
            if absorption.sell_through_pct is not None and (
                absorption.sell_through_pct / 100.0 < _AT_RISK_SELL_THROUGH_THRESHOLD
            ):
                reasons.append(
                    f"sell-through is {absorption.sell_through_pct:.1f}% "
                    f"(below {_AT_RISK_SELL_THROUGH_THRESHOLD * 100:.0f}% threshold)"
                )
            if collections.overdue_receivable_count > 0:
                reasons.append(
                    f"{collections.overdue_receivable_count} overdue receivable(s) "
                    f"with AED {collections.overdue_balance:,.2f} outstanding"
                )
            return "Project is at risk: " + "; ".join(reasons) + "."
        if feedback_status == "needs_attention":
            return (
                f"Project needs attention: sell-through is {absorption.sell_through_pct:.1f}% "
                f"(below {_NEEDS_ATTENTION_SELL_THROUGH_THRESHOLD * 100:.0f}% threshold)."
            )
        return (
            f"Project is on track: sell-through is {absorption.sell_through_pct:.1f}% "
            "with no overdue receivables."
        )

    def _derive_lineage_note(self, lineage_run: Optional[FeasibilityRun]) -> str:
        """Return a note indicating whether a feasibility lineage exists."""
        if lineage_run is None:
            return "No feasibility run found for this project."
        return f"Linked to feasibility run '{lineage_run.id}' (status: {lineage_run.status})."
