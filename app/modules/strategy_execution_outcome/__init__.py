"""
strategy_execution_outcome

Execution Outcome Capture & Feedback Loop Closure module (PR-V7-10).

Provides a persisted outcome capture layer that:
  - records the realized execution outcome for a triggered strategy
  - captures actual values taken at a governance level
  - compares intended strategy vs realized outcome
  - closes the loop back into platform intelligence without mutating prior snapshots
  - exposes portfolio-level executed strategy visibility

Outcome result classification
------------------------------
  matched_strategy    — execution matched the approved strategy
  partially_matched   — some but not all strategy actions were executed
  diverged            — execution materially diverged from the strategy
  cancelled_execution — execution was cancelled before completion
  insufficient_data   — outcome cannot be classified (no comparable strategy data)

Outcome status lifecycle
-------------------------
  recorded → superseded  (when a newer outcome is recorded for the same trigger)

Eligibility rule
-----------------
  Outcome may be recorded only for triggers in 'in_progress' or 'completed' state.
  Recording for 'triggered' or terminal-cancelled triggers is forbidden.

Forbidden actions
-----------------
  Mutation of pricing, phasing, feasibility, or project source records.
  Auto-application of execution changes to the source commercial model.
  Rewriting or mutating prior approval or trigger records.
  Bypassing the canonical project hierarchy.
"""
