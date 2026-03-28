"""
phasing_optimization

Phasing Optimization Engine (PR-V7-03).

Provides deterministic, backend-owned phasing recommendations by converting:
  - sales absorption signals
  - inventory availability by phase
  - pricing optimization demand signals
  - project readiness (approved baseline, construction records)
  - phase context (current active phase, next phase)

into:
  - current-phase release strategy recommendations
  - next-phase readiness recommendations
  - inventory holdback / release guidance
  - portfolio-level phase timing insights

All recommendations are read-only.  No phase or inventory records are mutated.
"""
