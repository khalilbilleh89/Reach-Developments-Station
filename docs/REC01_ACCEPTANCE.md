# PR-REC-01 — Pre-Launch expense correction and removal

Governed by [Engineering Rules](ENGINEERING_RULES.md),
[Architecture](ARCHITECTURE.md), and the approved
[record correction plan](RECORD_CORRECTION_AUDIT.md).
Base: main `97e08d3`, after merged #292 and #293; its post-merge CI passed.

## Candidate behavior

An eligible Recorded expense offers Edit and Remove. Edit starts with the current
values and updates category, exact amount, movement date, counterparty, invoice,
evidence and notes. Currency, phase, bank/value-date fields, record identity and
original recorder remain unchanged. Only the original recorder with current
Pre-Launch recording authority may edit, including an original Master recorder;
Masters cannot edit another person's entry and then confirm it themselves.

Remove requires a reason. The original recorder with recording authority, or
existing Finance/CFO reversal authority, may remove an unconfirmed expense. It
leaves recorded totals, remains in the register as Removed with its reason, and
never enters confirmed cash. Confirmed expenses retain the existing Reverse
workflow; no posted amount is edited and no record is physically deleted.

New PATCH `/projects/{project_id}/pre-launch/expenses/{movement_id}` accepts
`expected` and `changes`, each containing the seven editable fields. New POST
`.../{movement_id}/remove` accepts `expected` and `reason`. Both take the same
project/row locks used by confirmation and reject changed snapshots or terminal
states with 409. Remove cannot silently become a confirmed-cash reversal.
Pre-Launch Confirm now also requires `expected` with the seven displayed fields;
stale approval returns 409 instead of confirming an amount the checker never saw.
Its frontend caller and existing integration callers are updated together.
The generic Cashflow confirmation request contract remains unchanged.

Responses add actor-specific `can_edit`, `edit_blocker`, `can_remove`,
`removal_blocker`, `removed_without_confirmation` and `reversal_reason`.
Original recorder identifiers are not exposed. The locked service rechecks
eligibility; response flags are guidance, not permission tokens.

Corrections emit `cashflow.development_movement_corrected` with before/after
amount, date, category, references and notes. Removal retains the existing
reversal audit event and stored reason. No new schema, migration, dependency,
financial formula or generic workflow framework is introduced. The Fast selector
now includes Pre-Launch when its owning Cashflow services change.

The existing form/reason guards keep drafts after failed writes, prevent leaving
dirty forms without handling them, and prevent duplicate submissions. A 403/409
refreshes the register without replaying the write. A stale editor retains its
draft for comparison; close/reopen after reviewing it to load current values.

## Validation and remaining acceptance

- PostgreSQL tests cover original-recorder correction/removal, Finance versus
  reader/admin permissions, preserved bank/value-date/phase, cross-project 404,
  disallowed categories, exact decimals, stale edit/remove, blank reasons,
  unchanged cash totals and retained audit history.
- Simultaneous API requests cover edit versus confirmation and removal versus
  confirmation. The resulting status and totals must match the winning order.
- Frontend: 69 tests passed, including draft-value retention after errors,
  stale-removal eligibility refresh, and synchronous duplicate-submit blocking.
  Production webpack build and TypeScript checking passed.
- Final backend/static/selector results are recorded in the PR description.
- Browser/mobile acceptance is **Pending**: the browser tool fails before
  execution with `failed to write kernel assets ... os error 3`. No browser
  screenshots or operator acceptance are claimed.

Before release, exercise at desktop and 390 px: PM records an incorrect expense,
edits it, removes a duplicate with a reason; another authorized user confirms
the corrected expense; Edit/Remove become unavailable and confirmed reversal
remains clear. Check keyboard focus, dirty-draft cancel, failed-save recovery,
long references, readable amounts and action reachability.

Independent review and exact-head Full CI remain separate gates. This candidate
does not implement the other Cashflow, Collections, Construction or abandoned
draft findings, nor does it declare operator UAT or MVP freeze complete.
