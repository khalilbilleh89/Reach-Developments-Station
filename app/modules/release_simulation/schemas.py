"""
release_simulation.schemas

Typed Pydantic request and response contracts for the Release Strategy
Simulation Engine (PR-V7-04).

All response schemas are read-only.  Simulation outputs are never persisted.

Schema hierarchy:
  SimulationScenarioInput           — per-scenario inputs (price %, delay, strategy)
  SimulationResult                  — per-scenario simulation outputs
  SimulateStrategyRequest           — single-scenario request body
  SimulateStrategyResponse          — single-scenario response envelope
  SimulateStrategiesRequest         — multi-scenario request body
  SimulateStrategiesResponse        — multi-scenario comparison response

Release strategy values:
  hold        — reduce absorption velocity, extend cashflow timeline
  accelerate  — increase absorption velocity, compress cashflow timeline
  maintain    — keep current absorption velocity unchanged

Risk score rules:
  irr_delta > +2 %  → low
  irr_delta 0–2 %   → medium
  irr_delta < 0 %   → high
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SimulationScenarioInput(BaseModel):
    """Inputs for a single release strategy simulation scenario."""

    price_adjustment_pct: float = Field(
        default=0.0,
        description=(
            "Percentage adjustment applied to the baseline GDV. "
            "Positive values increase revenue; negative values decrease it. "
            "Range: -50 to +50."
        ),
        ge=-50.0,
        le=50.0,
    )
    phase_delay_months: int = Field(
        default=0,
        description=(
            "Additional months added to the baseline development period. "
            "Positive delays revenue; negative accelerates it. "
            "Range: -24 to +60."
        ),
        ge=-24,
        le=60,
    )
    release_strategy: Literal["hold", "accelerate", "maintain"] = Field(
        default="maintain",
        description=(
            "Release strategy modifier applied on top of any phase delay. "
            "'hold' extends the effective period by 10% (slower absorption). "
            "'accelerate' compresses the effective period by 10% (faster absorption). "
            "'maintain' leaves the period unchanged."
        ),
    )
    label: Optional[str] = Field(
        None,
        description="Optional human-readable label for this scenario (e.g. 'Base', '+5% Price').",
        max_length=100,
    )


class SimulationResult(BaseModel):
    """Outputs for a single release strategy simulation scenario.

    All financial values are derived from the project's latest calculated
    feasibility run.  No source records are mutated.
    """

    label: Optional[str] = Field(
        None,
        description="Scenario label passed in the request, if any.",
    )

    # Scenario inputs (echoed for traceability)
    price_adjustment_pct: float = Field(
        ..., description="Price adjustment applied in this scenario (%)."
    )
    phase_delay_months: int = Field(
        ..., description="Phase delay applied in this scenario (months)."
    )
    release_strategy: str = Field(
        ..., description="Release strategy applied in this scenario."
    )

    # Simulated economics
    simulated_gdv: float = Field(
        ...,
        description="Simulated GDV after applying price_adjustment_pct to baseline GDV (AED).",
    )
    simulated_dev_period_months: int = Field(
        ...,
        description=(
            "Effective development period after applying phase_delay_months and "
            "release_strategy modifier (months)."
        ),
    )
    irr: float = Field(
        ...,
        description=(
            "Simulated annualized IRR recalculated from baseline total_cost, "
            "simulated_gdv, and simulated_dev_period_months."
        ),
    )
    irr_delta: Optional[float] = Field(
        None,
        description=(
            "Difference between simulated IRR and baseline IRR "
            "(irr − baseline_irr). Positive = improvement; null when baseline IRR unavailable."
        ),
    )
    npv: float = Field(
        ...,
        description=(
            "Net Present Value of the simulated cashflows at the platform discount "
            "rate (10% p.a.). AED."
        ),
    )
    cashflow_delay_months: int = Field(
        ...,
        description=(
            "Delta between simulated and baseline development period in months "
            "(simulated_dev_period_months − baseline_dev_period_months). "
            "Positive = delayed; negative = accelerated."
        ),
    )
    risk_score: str = Field(
        ...,
        description=(
            "Risk classification based on irr_delta: "
            "'low' (>+2%), 'medium' (0–2%), 'high' (<0%)."
        ),
    )

    # Baseline references (for comparison)
    baseline_gdv: Optional[float] = Field(
        None, description="Baseline GDV from the latest feasibility result (AED)."
    )
    baseline_irr: Optional[float] = Field(
        None, description="Baseline IRR from the latest feasibility result."
    )
    baseline_dev_period_months: Optional[int] = Field(
        None, description="Baseline development period in months."
    )
    baseline_total_cost: Optional[float] = Field(
        None, description="Baseline total cost from the latest feasibility result (AED)."
    )


class SimulateStrategyRequest(BaseModel):
    """Request body for the single-scenario simulation endpoint."""

    scenario: SimulationScenarioInput = Field(
        ..., description="Simulation scenario inputs."
    )


class SimulateStrategyResponse(BaseModel):
    """Response envelope for the single-scenario simulation endpoint.

    Returns the simulation result alongside the project context.
    No source records are mutated.
    """

    project_id: str
    project_name: str
    has_feasibility_baseline: bool = Field(
        ...,
        description=(
            "True when a calculated feasibility run exists for this project. "
            "When false, simulation uses default assumptions and results are indicative only."
        ),
    )
    result: SimulationResult


class SimulateStrategiesRequest(BaseModel):
    """Request body for the multi-scenario simulation endpoint."""

    scenarios: List[SimulationScenarioInput] = Field(
        ...,
        description="List of simulation scenario inputs to compare.",
        min_length=1,
        max_length=20,
    )


class SimulateStrategiesResponse(BaseModel):
    """Response envelope for the multi-scenario comparison endpoint.

    Returns all simulation results ranked by IRR descending so the
    highest-return strategy appears first.  No source records are mutated.
    """

    project_id: str
    project_name: str
    has_feasibility_baseline: bool = Field(
        ...,
        description=(
            "True when a calculated feasibility run exists for this project. "
            "When false, simulation uses default assumptions and results are indicative only."
        ),
    )
    results: List[SimulationResult] = Field(
        ...,
        description="Simulation results ranked by IRR descending (highest IRR first).",
    )
    best_scenario_label: Optional[str] = Field(
        None,
        description="Label of the highest-IRR scenario, if a label was provided.",
    )
