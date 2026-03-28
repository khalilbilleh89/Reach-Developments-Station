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

    # ------------------------------------------------------------------
    # Absorption Metrics (detailed planned vs actual)
    # ------------------------------------------------------------------

    def get_absorption_metrics(
        self, project_id: str
    ) -> "ProjectAbsorptionMetricsResponse":
        """Return detailed absorption metrics for a single project.

        Compares actual sales velocity against planned feasibility assumptions
        and recalculates IRR using actual contracted revenue.

        Raises HTTP 404 if the project does not exist.
        All values are derived on request from live source data and read-only.
        """
        from app.modules.feasibility_feedback.schemas import ProjectAbsorptionMetricsResponse
        from app.modules.feasibility.irr_engine import calculate_irr

        project = self.repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        # --- Unit inventory ---
        unit_counts = self.repo.count_units_by_status_for_project(project_id)
        total_units = sum(unit_counts.values())
        available = unit_counts.get("available", 0)
        reserved = unit_counts.get("reserved", 0)
        under_contract = unit_counts.get("under_contract", 0)
        registered = unit_counts.get("registered", 0)
        sold_units = under_contract + registered

        # --- Revenue ---
        contracted_revenue = self.repo.sum_contracted_revenue_for_project(project_id)

        # --- Feasibility plan data ---
        feas_result = self.repo.get_latest_feasibility_result_for_project(project_id)
        feas_assumptions = self.repo.get_latest_feasibility_assumptions_for_project(project_id)

        projected_revenue: float | None = None
        planned_irr: float | None = None
        planned_total_cost: float | None = None
        planned_dev_period: int | None = None
        planned_absorption_rate_per_month: float | None = None

        if feas_result is not None and feas_result.gdv is not None:
            projected_revenue = float(feas_result.gdv)
        if feas_result is not None and feas_result.irr is not None:
            planned_irr = float(feas_result.irr)
        if feas_result is not None and feas_result.total_cost is not None:
            planned_total_cost = float(feas_result.total_cost)
        if feas_assumptions is not None and feas_assumptions.development_period_months is not None:
            planned_dev_period = int(feas_assumptions.development_period_months)

        # Planned absorption: total_units / development_period_months
        if total_units > 0 and planned_dev_period is not None and planned_dev_period > 0:
            planned_absorption_rate_per_month = total_units / planned_dev_period

        # --- Actual absorption rate from contract dates ---
        first_date = self.repo.get_first_contract_date_for_project(project_id)
        last_date = self.repo.get_latest_contract_date_for_project(project_id)
        contract_count = self.repo.count_non_cancelled_contracts_for_project(project_id)

        absorption_rate_per_month: float | None = None
        avg_selling_time_days: float | None = None

        if first_date is not None and last_date is not None and contract_count >= 2:
            days_elapsed = (last_date - first_date).days
            if days_elapsed > 0:
                months_elapsed = days_elapsed / 30.4375  # average days per month
                absorption_rate_per_month = round(contract_count / months_elapsed, 4)
                avg_selling_time_days = round(days_elapsed / contract_count, 2)

        # --- Absorption vs plan ---
        absorption_vs_plan_pct: float | None = None
        if (
            absorption_rate_per_month is not None
            and planned_absorption_rate_per_month is not None
            and planned_absorption_rate_per_month > 0
        ):
            absorption_vs_plan_pct = round(
                (absorption_rate_per_month / planned_absorption_rate_per_month) * 100, 2
            )

        # --- Revenue realized % ---
        revenue_realized_pct: float | None = _safe_pct(
            contracted_revenue,
            projected_revenue if projected_revenue is not None else 0.0,
        )

        # --- IRR recalculation using actual contracted revenue ---
        actual_irr_estimate: float | None = None
        irr_delta: float | None = None
        if (
            planned_total_cost is not None
            and planned_dev_period is not None
            and contracted_revenue > 0
        ):
            actual_irr_estimate = round(
                calculate_irr(
                    total_cost=planned_total_cost,
                    gdv=contracted_revenue,
                    development_period_months=planned_dev_period,
                ),
                6,
            )
            if planned_irr is not None:
                irr_delta = round(actual_irr_estimate - planned_irr, 6)

        # --- Cashflow timing delay ---
        cashflow_delay_months: float | None = None
        revenue_timing_note: str

        if absorption_rate_per_month is not None and planned_absorption_rate_per_month is not None:
            if planned_absorption_rate_per_month > 0 and total_units > 0:
                actual_months = total_units / absorption_rate_per_month
                planned_months = total_units / planned_absorption_rate_per_month
                cashflow_delay_months = round(actual_months - planned_months, 2)
            if cashflow_delay_months is None or cashflow_delay_months == 0.0:
                revenue_timing_note = "Revenue timing is on plan."
            elif cashflow_delay_months > 0:
                revenue_timing_note = (
                    f"Revenue timing is delayed by approximately "
                    f"{cashflow_delay_months:.1f} months vs plan."
                )
            else:
                revenue_timing_note = (
                    f"Revenue is arriving approximately "
                    f"{abs(cashflow_delay_months):.1f} months ahead of plan."
                )
        elif feas_result is None:
            revenue_timing_note = (
                "No feasibility run found. Revenue timing vs plan cannot be derived."
            )
        elif contract_count < 2:
            revenue_timing_note = (
                "Insufficient sales data to derive absorption rate and timing."
            )
        else:
            revenue_timing_note = "Revenue timing comparison is unavailable."

        return ProjectAbsorptionMetricsResponse(
            project_id=project.id,
            project_name=project.name,
            project_code=project.code,
            total_units=total_units,
            sold_units=sold_units,
            reserved_units=reserved,
            available_units=available,
            absorption_rate_per_month=absorption_rate_per_month,
            planned_absorption_rate_per_month=planned_absorption_rate_per_month,
            absorption_vs_plan_pct=absorption_vs_plan_pct,
            avg_selling_time_days=avg_selling_time_days,
            contracted_revenue=contracted_revenue,
            projected_revenue=projected_revenue,
            revenue_realized_pct=revenue_realized_pct,
            planned_irr=planned_irr,
            actual_irr_estimate=actual_irr_estimate,
            irr_delta=irr_delta,
            cashflow_delay_months=cashflow_delay_months,
            revenue_timing_note=revenue_timing_note,
        )
