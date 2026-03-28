"""
phasing_optimization

Phasing Optimization Engine (PR-V7-03).

Provides deterministic, backend-owned phasing recommendations by converting:
  - sales absorption and sell-through signals
  - inventory availability by phase
  - project readiness (approved baseline state)
  - phase context (current active phase, next phase)

into:
  - current-phase release strategy recommendations
  - next-phase readiness recommendations
  - inventory holdback / release guidance
  - portfolio-level phase timing insights

All recommendations are read-only.  No phase or inventory records are mutated.
"""
