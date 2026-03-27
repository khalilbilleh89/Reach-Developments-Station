"""
portfolio.service

Portfolio Intelligence aggregation service.

Composes repository query results into dashboard-ready response structures.
All methods are read-only — no source records are mutated.

Health badge rules are intentionally simple and transparent:
  - 'at_risk'         : sell-through < 20 % OR overdue receivables > 0
  - 'needs_attention' : sell-through < 50 %
  - 'on_track'        : sell-through >= 50 % and no overdue receivables

Risk flag thresholds are documented inline.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.portfolio.repository import PortfolioRepository
from app.modules.portfolio.schemas import (
    PortfolioCollectionsSummary,
    PortfolioDashboardResponse,
    PortfolioPipelineSummary,
    PortfolioProjectCard,
    PortfolioRiskFlag,
    PortfolioSummary,
)


# ---------------------------------------------------------------------------
# Health badge thresholds (transparent, documented)
# ---------------------------------------------------------------------------
_AT_RISK_SELL_THROUGH_THRESHOLD = 0.20   # below 20 % → at_risk
_NEEDS_ATTENTION_SELL_THROUGH_THRESHOLD = 0.50  # below 50 % → needs_attention

# Risk flag thresholds
_LOW_SELL_THROUGH_FLAG_THRESHOLD = 0.30   # portfolio-project sell-through below 30 %
_LOW_COLLECTIONS_RATE_THRESHOLD = 0.30    # collection rate below 30 %


def _safe_pct(numerator: float, denominator: float) -> Optional[float]:
    """Return numerator / denominator * 100, or None when denominator is zero."""
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


class PortfolioService:
    """Service that assembles portfolio dashboard data from source domain records."""

    def __init__(self, db: Session) -> None:
        self.repo = PortfolioRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_dashboard(self) -> PortfolioDashboardResponse:
        """Assemble and return the full portfolio dashboard response."""
        summary = self._build_summary()
        projects = self._build_project_cards()
        pipeline = self._build_pipeline_summary()
        collections = self._build_collections_summary()
        risk_flags = self._derive_risk_flags(projects, collections)

        return PortfolioDashboardResponse(
            summary=summary,
            projects=projects,
            pipeline=pipeline,
            collections=collections,
            risk_flags=risk_flags,
        )

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_summary(self) -> PortfolioSummary:
        unit_counts = self.repo.count_units_by_status()
        return PortfolioSummary(
            total_projects=self.repo.count_projects(),
            active_projects=self.repo.count_active_projects(),
            total_units=sum(unit_counts.values()),
            available_units=unit_counts.get("available", 0),
            reserved_units=unit_counts.get("reserved", 0),
            under_contract_units=unit_counts.get("under_contract", 0),
            registered_units=unit_counts.get("registered", 0),
            contracted_revenue=self.repo.sum_contracted_revenue(),
            collected_cash=self.repo.sum_collected_cash(),
            outstanding_balance=self.repo.sum_outstanding_balance(),
        )

    def _build_project_cards(self) -> List[PortfolioProjectCard]:
        projects = self.repo.list_projects()
        cards: List[PortfolioProjectCard] = []

        for project in projects:
            unit_counts = self.repo.count_units_by_status_for_project(project.id)
            total_units = sum(unit_counts.values())
            available = unit_counts.get("available", 0)
            reserved = unit_counts.get("reserved", 0)
            under_contract = unit_counts.get("under_contract", 0)
            registered = unit_counts.get("registered", 0)
            contracted_revenue = self.repo.sum_contracted_revenue_for_project(project.id)
            collected_cash = self.repo.sum_collected_cash_for_project(project.id)
            outstanding_balance = self.repo.sum_outstanding_balance_for_project(project.id)

            sold_units = under_contract + registered
            sell_through_pct = _safe_pct(sold_units, total_units)
            sell_through_ratio = sold_units / total_units if total_units > 0 else None

            overdue_count = self.repo.count_overdue_receivables_for_project(project.id)
            health_badge = self._derive_health_badge(sell_through_ratio, overdue_count)

            cards.append(
                PortfolioProjectCard(
                    project_id=project.id,
                    project_name=project.name,
                    project_code=project.code,
                    status=project.status,
                    total_units=total_units,
                    available_units=available,
                    reserved_units=reserved,
                    under_contract_units=under_contract,
                    registered_units=registered,
                    contracted_revenue=contracted_revenue,
                    collected_cash=collected_cash,
                    outstanding_balance=outstanding_balance,
                    sell_through_pct=sell_through_pct,
                    health_badge=health_badge,
                )
            )

        return cards

    def _build_pipeline_summary(self) -> PortfolioPipelineSummary:
        total_projects = self.repo.count_projects()
        run_counts_by_project = self.repo.get_all_project_feasibility_run_counts()
        # Count projects that have zero feasibility runs
        projects_with_runs = len(run_counts_by_project)
        projects_with_no_feasibility = max(0, total_projects - projects_with_runs)

        return PortfolioPipelineSummary(
            total_scenarios=self.repo.count_scenarios(),
            active_scenarios=self.repo.count_active_scenarios(),
            total_feasibility_runs=self.repo.count_feasibility_runs(),
            calculated_feasibility_runs=self.repo.count_calculated_feasibility_runs(),
            projects_with_no_feasibility=projects_with_no_feasibility,
        )

    def _build_collections_summary(self) -> PortfolioCollectionsSummary:
        total_receivables = self.repo.count_receivables()
        overdue_receivables = self.repo.count_overdue_receivables()
        overdue_balance = self.repo.sum_overdue_balance()
        collected = self.repo.sum_collected_cash()
        outstanding = self.repo.sum_outstanding_balance()
        collection_rate_pct = _safe_pct(collected, collected + outstanding)

        return PortfolioCollectionsSummary(
            total_receivables=total_receivables,
            overdue_receivables=overdue_receivables,
            overdue_balance=overdue_balance,
            collection_rate_pct=collection_rate_pct,
        )

    # ------------------------------------------------------------------
    # Health badge derivation
    # ------------------------------------------------------------------

    def _derive_health_badge(
        self,
        sell_through_ratio: Optional[float],
        overdue_count: int,
    ) -> Optional[str]:
        """Return a health badge string or None when no units exist."""
        if sell_through_ratio is None:
            return None
        if sell_through_ratio < _AT_RISK_SELL_THROUGH_THRESHOLD or overdue_count > 0:
            return "at_risk"
        if sell_through_ratio < _NEEDS_ATTENTION_SELL_THROUGH_THRESHOLD:
            return "needs_attention"
        return "on_track"

    # ------------------------------------------------------------------
    # Risk flag derivation
    # ------------------------------------------------------------------

    def _derive_risk_flags(
        self,
        project_cards: List[PortfolioProjectCard],
        collections: PortfolioCollectionsSummary,
    ) -> List[PortfolioRiskFlag]:
        """Derive portfolio-level risk flags from assembled data.

        Rules are intentionally simple and transparent for this first slice:
          1. Portfolio has overdue receivables → 'overdue_receivables' warning/critical
          2. Project sell-through < 30 % → 'low_sell_through' warning per project
          3. Portfolio collection rate < 30 % → 'low_collections' warning
        """
        flags: List[PortfolioRiskFlag] = []

        # Rule 1 — portfolio-wide overdue receivables
        if collections.overdue_receivables > 0:
            severity = (
                "critical" if collections.overdue_receivables >= 10 else "warning"
            )
            flags.append(
                PortfolioRiskFlag(
                    flag_type="overdue_receivables",
                    severity=severity,
                    description=(
                        f"{collections.overdue_receivables} overdue receivable(s) with "
                        f"total outstanding balance of AED {collections.overdue_balance:,.2f}."
                    ),
                    affected_project_id=None,
                    affected_project_name=None,
                )
            )

        # Rule 2 — low sell-through per project
        for card in project_cards:
            if card.sell_through_pct is not None:
                sell_through_ratio = card.sell_through_pct / 100.0
                if sell_through_ratio < _LOW_SELL_THROUGH_FLAG_THRESHOLD:
                    flags.append(
                        PortfolioRiskFlag(
                            flag_type="low_sell_through",
                            severity="warning",
                            description=(
                                f"Project '{card.project_name}' has a sell-through rate of "
                                f"{card.sell_through_pct:.1f}% (below {_LOW_SELL_THROUGH_FLAG_THRESHOLD * 100:.0f}% threshold)."
                            ),
                            affected_project_id=card.project_id,
                            affected_project_name=card.project_name,
                        )
                    )

        # Rule 3 — low collection rate at portfolio level
        if (
            collections.collection_rate_pct is not None
            and collections.collection_rate_pct / 100.0 < _LOW_COLLECTIONS_RATE_THRESHOLD
        ):
            flags.append(
                PortfolioRiskFlag(
                    flag_type="low_collections",
                    severity="warning",
                    description=(
                        f"Portfolio collection rate is {collections.collection_rate_pct:.1f}% "
                        f"(below {_LOW_COLLECTIONS_RATE_THRESHOLD * 100:.0f}% threshold)."
                    ),
                    affected_project_id=None,
                    affected_project_name=None,
                )
            )

        return flags
