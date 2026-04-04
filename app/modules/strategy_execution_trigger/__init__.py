"""
strategy_execution_trigger

Execution Trigger & Handoff Records module (PR-V7-09).

Provides a controlled execution trigger layer that:
  - allows approved strategies to be formally triggered for execution handoff
  - creates immutable execution handoff records
  - tracks execution status at a lightweight governance level
  - keeps execution non-automated and non-destructive

State machine
-------------
  triggered → in_progress  (via start endpoint)
  triggered → cancelled    (via cancel endpoint)
  in_progress → completed  (via complete endpoint)
  in_progress → cancelled  (via cancel endpoint)

Forbidden transitions
---------------------
  completed → any
  cancelled → any

Forbidden actions
-----------------
  Mutation of pricing, phasing, feasibility, or project source records.
  Auto-execution of any strategy action.
  Trigger creation without a prior approved strategy approval.
"""
