"""
feasibility_feedback.schemas

Typed Pydantic response contracts for the Sales Absorption → Feasibility Feedback module.

All schemas are read-only response models.  No request/create schemas exist
because this module is a read-only aggregation surface.

Schema hierarchy:
  ProjectAbsorptionFeedback           — unit absorption / sell-through summary
  ProjectCollectionFeedback           — cash collection and overdue receivables summary
  ProjectFeasibilityFeedbackResponse  — top-level envelope returned by the endpoint
"""

from typing import Optional

from pydantic import BaseModel, Field


class ProjectAbsorptionFeedback(BaseModel):
    """Unit absorption summary derived from live inventory and sales data."""

    total_units: int = Field(..., description="Total inventory units for this project")
    sold_units: int = Field(
        ...,
        description=(
            "Units with status 'under_contract' or 'registered' (i.e. committed sales)"
        ),
    )
    reserved_units: int = Field(..., description="Units with status 'reserved'")
    available_units: int = Field(..., description="Units with status 'available'")
    sell_through_pct: Optional[float] = Field(
        None,
        description=(
            "Percentage of units sold (under_contract + registered) out of total units; "
            "null when the project has no units"
        ),
    )
    contracted_revenue: float = Field(
        ..., description="Sum of contract_price for all non-cancelled sales contracts (AED)"
    )


class ProjectCollectionFeedback(BaseModel):
    """Cash collection and overdue receivables summary for this project."""

    collected_cash: float = Field(
        ..., description="Sum of amount_paid across all receivables for this project (AED)"
    )
    outstanding_balance: float = Field(
        ..., description="Sum of balance_due across all open receivables for this project (AED)"
    )
    overdue_receivable_count: int = Field(
        ..., description="Number of receivables with status 'overdue' for this project"
    )
    overdue_balance: float = Field(
        ..., description="Sum of balance_due for overdue receivables for this project (AED)"
    )
    collection_rate_pct: Optional[float] = Field(
        None,
        description=(
            "amount_paid / (amount_paid + balance_due) expressed as a percentage; "
            "null when no receivables exist for this project"
        ),
    )


class ProjectFeasibilityFeedbackResponse(BaseModel):
    """Top-level feedback envelope for a single project.

    Combines absorption and collection signals with a transparent feedback
    badge and explanatory notes.  All values are derived on request from live
    source data — nothing is persisted as a derived feedback snapshot.

    Feedback badge rules (transparent):
      'at_risk'         : sell-through < 20 % OR overdue receivables > 0
      'needs_attention' : sell-through < 50 %
      'on_track'        : sell-through >= 50 % and no overdue receivables
      null              : project has no units (cannot derive a signal)

    Threshold references used for badge derivation are surfaced in
    ``feedback_thresholds`` to make the interpretation explicit.
    """

    project_id: str
    project_name: str
    project_code: str
    project_status: str

    absorption: ProjectAbsorptionFeedback
    collections: ProjectCollectionFeedback

    feedback_status: Optional[str] = Field(
        None,
        description=(
            "Derived feedback badge: 'on_track' | 'needs_attention' | 'at_risk'; "
            "null when the project has no units"
        ),
    )
    feedback_notes: str = Field(
        ...,
        description="Human-readable explanation of the feedback status",
    )

    latest_feasibility_run_id: Optional[str] = Field(
        None,
        description="ID of the most recently created feasibility run for this project, if any",
    )
    latest_scenario_id: Optional[str] = Field(
        None,
        description="Scenario ID linked to the most recent feasibility run, if any",
    )
    feasibility_lineage_note: str = Field(
        ...,
        description=(
            "Indicates whether this project has a feasibility lineage "
            "(e.g. 'Linked to feasibility run' or 'No feasibility run found')"
        ),
    )

    feedback_thresholds: dict = Field(
        default_factory=dict,
        description=(
            "Threshold values used for feedback badge derivation, "
            "surfaced for transparency"
        ),
    )
