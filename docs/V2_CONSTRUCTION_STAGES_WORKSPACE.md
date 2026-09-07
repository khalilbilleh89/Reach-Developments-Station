# MVP 2 batch 4 — Construction Stage Experience

Implements V2-09 under [ENGINEERING_RULES.md](ENGINEERING_RULES.md).
Requirements were checked against the owner's `Real_Estate_Development_Tracking_System_MVP (2).docx`,
especially its final “General amendments/clarification” section.

## Confirmed scope

The project configures its planned construction stages. Every unit displays
those stages and the actual completion date recorded for each one. This gives
the operator a unit-specific construction record alongside delivery status.
The document supplies no fixed stage catalogue: names must be project inputs.

## Implementation design

- Construction owns ordered project stages with a name and optional planned
  completion date. Project Managers configure the shared list; configuration
  requires whole-project access because it affects every unit.
- Unit progress is scoped through the existing inventory project/phase boundary.
  Project Managers, Design / Engineering and Finance record completion, using
  the existing Construction technical role set.
- Completion has an actual date, actor and recorded timestamp. Corrections
  require a reason and preserve the preceding record. Future actual dates are
  refused. No financial state is changed by these records.
- Unit progress exposes only stage and delivery information. Existing
  Construction reader permissions remain unchanged for financial APIs.
- Project members may read this nonfinancial checklist, including roles that
  cannot read construction costs. The unit endpoint additionally enforces phase
  visibility. Creation is Project Manager only; completion uses the existing
  technical role set. Stage order is append order, and names/dates are fixed in
  this first implementation; schedule editing is still to be implemented.
- A completed checklist is not a certificate, a payable instalment, or handover
  approval. Existing milestone certification and delivery transitions continue
  to own those decisions. No automatic delivery date is inferred from an
  undated or unfinished checklist.

## Acceptance and verification plan

Configure stages once; open two units and record different completion dates;
verify each has independent progress. Correct a completion with a reason and
verify the earlier entry remains visible. Exercise project and phase scoping,
unauthorized mutation, future dates, duplicate stage names and concurrent writes.
Verify stages cannot trigger buyer instalments or overwrite delivery status.
Check migration upgrade, downgrade and model agreement, plus responsive and
keyboard operation of project configuration and unit progress.

Implementation and verification are in progress. No completion, passing test,
deployment or production-data claim is made by this document.

Migration `0015_construction_stages` adds two tables without backfilling existing
units. An empty checklist is shown as unconfigured. Downgrade refuses once any
stage exists, preserving entered history; retain the schema or restore an
appropriate pre-upgrade backup. The legacy import contract excludes both tables.
