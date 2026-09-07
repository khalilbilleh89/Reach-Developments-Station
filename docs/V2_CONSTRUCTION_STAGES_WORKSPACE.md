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
  technical role set. New stages append; whole-project Project Managers may
  edit names, set or clear planned dates, and move stages to positions 1..N.
  Readers have no maintenance controls. Selected-phase PM writes are refused
  by the backend even if a client sends the request directly.
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

## Configuration update contract

`PATCH /api/v1/projects/{project_id}/construction/stages/{stage_id}` accepts only
`name`, `planned_date`, `sequence`, and concurrency preconditions. Omitted values
remain unchanged; explicit null clears only the planned date. Null name/sequence,
blank/duplicate names and positions outside the list are refused.

Every request supplies `expected_name`, `expected_planned_date` and
`expected_sequence`. Moves also supply `expected_order`, the displayed stage UUID
list. Behind the project lock the service refreshes configuration and refuses
stale snapshots with 409. This is value comparison, not an added versioning
subsystem; an intervening change that returns to exactly the same state is
equivalent for this contract.

A move parks its stage at max(sequence)+1, shifts each intervening row into the
vacant slot in deterministic order (flushing each step), then places the moved
stage. All intermediate values are positive and unique; final positions are
contiguous. One domain audit event carries actor, correlation ID, before/after
name/date/sequence and ordered UUIDs. Internal shifts create no extra audit noise.
No-op saves do not create an audit event. Stage UUIDs and unit completion events
are unchanged. Creation audit also includes the assigned sequence.

The inline editor focuses its name input and returns focus to Edit on save or
cancel. Move controls are named for their stage. Reload is explicit after a stale
save; the editor preserves the rejected input until cancelled, never silently
retries against new state. See [V2_MANAGEMENT_UAT.md](V2_MANAGEMENT_UAT.md) for
actual verification outcomes; implementation alone is not acceptance evidence.

Migration `0015_construction_stages` adds two tables without backfilling existing
units. An empty checklist is shown as unconfigured. Downgrade refuses once any
stage exists, preserving entered history; retain the schema or restore an
appropriate pre-upgrade backup. The legacy import contract excludes both tables.
