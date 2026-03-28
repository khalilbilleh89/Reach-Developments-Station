"""
release_simulation.api

Release Strategy Simulation Engine API router (PR-V7-04).

Endpoints:
  POST /api/v1/projects/{project_id}/simulate-strategy
    — Single-scenario what-if simulation.
  POST /api/v1/projects/{project_id}/simulate-strategies
    — Multi-scenario comparison (ranked by IRR descending).

Both endpoints are read-only.  No feasibility runs, phase records, or
pricing data are mutated.  Simulation state is never persisted.

Simulation reuses the feasibility IRR engine — no duplicate formulas.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.release_simulation.schemas import (
    SimulateStrategiesRequest,
    SimulateStrategiesResponse,
    SimulateStrategyRequest,
    SimulateStrategyResponse,
)
from app.modules.release_simulation.service import ReleaseSimulationService

router = APIRouter(
    prefix="/projects",
    tags=["Release Simulation"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> ReleaseSimulationService:
    return ReleaseSimulationService(db)


ServiceDep = Annotated[ReleaseSimulationService, Depends(_service)]


@router.post(
    "/{project_id}/simulate-strategy",
    response_model=SimulateStrategyResponse,
)
def simulate_strategy(
    project_id: str,
    body: SimulateStrategyRequest,
    service: ServiceDep,
) -> SimulateStrategyResponse:
    """Run a single release strategy what-if simulation for a project.

    Adjusts GDV, development period, and absorption curve based on the
    supplied scenario inputs, then recalculates IRR and NPV using the
    feasibility IRR engine.

    Simulation inputs:
    - price_adjustment_pct  — % change applied to baseline GDV
    - phase_delay_months    — months added/removed from development period
    - release_strategy      — 'hold' | 'accelerate' | 'maintain'

    Simulation outputs:
    - irr                   — recalculated annualized IRR
    - irr_delta             — difference vs baseline IRR
    - npv                   — NPV at 10% p.a. discount rate (AED)
    - cashflow_delay_months — effective period delta vs baseline
    - risk_score            — 'low' | 'medium' | 'high'

    All values are derived from the latest calculated feasibility run.
    No source records are mutated.  Returns 404 if the project does not exist.
    """
    return service.simulate_strategy(project_id, body)


@router.post(
    "/{project_id}/simulate-strategies",
    response_model=SimulateStrategiesResponse,
)
def simulate_strategies(
    project_id: str,
    body: SimulateStrategiesRequest,
    service: ServiceDep,
) -> SimulateStrategiesResponse:
    """Run multiple release strategy simulations and return results ranked by IRR.

    Accepts a list of scenario inputs (max 20) and runs each simulation
    deterministically using the feasibility IRR engine.  Results are returned
    sorted by IRR descending so the highest-return strategy appears first.

    Each scenario accepts:
    - price_adjustment_pct  — % change applied to baseline GDV
    - phase_delay_months    — months added/removed from development period
    - release_strategy      — 'hold' | 'accelerate' | 'maintain'
    - label                 — optional scenario label (e.g. 'Optimistic')

    Response includes:
    - results               — all scenarios sorted by IRR descending
    - best_scenario_label   — label of the highest-IRR scenario (if labelled)

    All values are derived from the latest calculated feasibility run.
    No source records are mutated.  Returns 404 if the project does not exist.
    """
    return service.simulate_strategies(project_id, body)
