# Price Escalation

Finance > Price Escalation is a project-wide strategy register. Each entry stores an effective calendar date, a positive percentage increase and a freely entered project status (up to 200 characters). Suggested statuses are Pre-launch, Launch, Construction and Foundation, plus saved statuses in the current register. Suggestions never restrict input or alter the project's official lifecycle status.

Entries are ordered by descending effective date. Add and edit use RecordPage with unsaved-change protection; failed requests retain the draft. Each row exposes authorized Edit and Delete actions. Delete requires a named confirmation and reason; the row and complete audit history are retained and removed from ordinary reads. These records have no child or transaction links.

Whole-project financial readers may read. Whole-project System/Master Administrators, Project Managers and Finance may create, edit and delete. Selected-phase and inactive memberships cannot read the project-wide register. Every mutation locks the project and checks the saved version. Wrong-project identifiers answer 404; stale writes answer 409.

The API accepts and returns decimal percentage strings. The server divides by Decimal 100 and stores the shared Numeric(9,6) fraction; up to four percentage decimal places are accepted without rounding. For example, 5.1256% stores 0.051256. Values must be positive and below 100000%. Multiple entries may share a date. No cumulative percentage is inferred.

The register does not activate pricing escalation rules, change approved prices, reprice units or modify sale contracts. It records the owner's strategy and history. Inventory remains the place to maintain unit prices.

Migration 0045_price_escalation follows 0044_team_job_description and adds only project_price_escalations. No backfill or production facts are seeded. Empty downgrade drops the new table; any retained row, including a deleted entry, refuses downgrade. Roll back application code while retaining the additive schema, or roll forward. Never delete history to force rollback.

Validation: tests/modules/test_project_price_escalation.py covers exact percentage persistence, custom statuses, ordering, partial edits, invalid/null/unknown input, stale writes, roles, project and phase isolation, reasoned deletion, audit, replay and migration roundtrip/drift/retention. frontend/tests/priceEscalation.test.mjs covers saved-value display, versioned deletion and refresh, failed/reader states, arbitrary status and failed-save draft retention. Shared migration head and CI migration ownership are updated.
