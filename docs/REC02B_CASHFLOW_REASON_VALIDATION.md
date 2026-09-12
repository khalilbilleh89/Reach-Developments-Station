# REC-02B — Cashflow reason validation

Independent candidate based on main `a638294`. This closes the direct API
whitespace-only reason gap discovered while validating REC-02A / PR #307.

## Behavior and scope

Cashflow's existing ReasonRequest now rejects whitespace-only text with a 422
field error before a reason-bearing operation reaches its write handler. Empty
strings retain their existing length-validation failure. Valid text is returned
unchanged; this does not rewrite supplied wording or change the existing length
limits, stored financial values, audit attribution or lifecycle rules.

The shared request is used by forecast approve/reject/discard, development and
financing reversal, escrow restriction/release reversal, and inherited Pre-Launch
removal. Nonblank reasons remain required even when a caller bypasses the UI.
This is input validation, not a financial calculation in a schema.

No new endpoint, record creator, removal state, permission, dependency, database
schema or migration. Existing retained-removal and dependency protections remain
in their owning services. Deletion-contract coverage does not change in this PR;
#307 separately delivers the Cashflow recorded Delete controls and manifest update.

## Delivery alongside other PRs

The owner authorized continuing independent PRs while earlier work is reviewed.
This supersedes the finish plan's earlier one-at-a-time development sequence,
without removing review or merge checks.

- #307 and this PR both target main and can be reviewed independently: there are
  no overlapping changed files or code dependencies. Either can merge first.
- Collections recorded receipt/refund removal remains the next domain slice.
  It does not need to inherit these Cashflow commits. Split receipt/refund work
  further if the full mutation and UI path cannot stay small and reviewable.
- Use a stacked base only when a child actually imports or relies on unmerged
  parent code. Review its incremental diff, merge the parent first, then rebase
  or retarget the child to main and rerun required CI on its resulting head.
- Never merge a child into its feature parent as a substitute for deploying main.
  Render remains on main. Avoid CI policy changes to accommodate a stack; direct
  main PRs already have supported Draft and Ready lanes.

## Candidate validation

Tests cover ASCII and Unicode whitespace, unchanged nonblank text/length limits,
the inherited Pre-Launch request, and real PostgreSQL-backed development and
financing reversal in both recorded and confirmed states. A rejected request must
leave the complete public movement response and reversal audit events unchanged;
a subsequent valid reason must succeed with one attributed audit event.

Relevant existing Pre-Launch correction/removal tests also run because that
request inherits the validator. Local validation: 19 tests passed in 107.76 seconds;
one unrelated migration downgrade test was excluded (no migration changes).
Ruff lint/format and diff whitespace checks passed. No UI code
changes; REC-02A's separate browser evidence remains scoped to that PR.

Independent review, exact-head CI and human merge remain release gates. Neither
this candidate nor parallel PR development establishes operator UAT or a release
freeze.
