"""
release_simulation

Release Strategy Simulation Engine (PR-V7-04).

Provides deterministic, synchronous what-if simulation for release strategy
decisions.  Accepts scenario inputs (price adjustment, phase delay, release
strategy) and recalculates IRR, NPV and cashflow timing using the existing
feasibility IRR engine.

No source records are mutated.  No persistent simulation state is created.

Endpoints:
  POST /api/v1/projects/{project_id}/simulate-strategy
    — Single-scenario simulation.
  POST /api/v1/projects/{project_id}/simulate-strategies
    — Multi-scenario comparison (sorted by IRR descending).
"""
