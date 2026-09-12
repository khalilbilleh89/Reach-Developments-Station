# REC-02A — Cashflow recorded removal

Base: main `a638294`. First remaining implementation slice in the reconciled
[MVP finish plan](UX_MVP_FINISH_2026_09_11.md).

## Behavior

Cashflow > Development & financing now offers Delete for recorded development
and financing movements to the existing confirmer roles. Confirmation names
the movement reference, requires a reason and explains that the record remains
for audit and has not counted as cash. This invokes the existing scoped, locked,
audited `POST /{kind}-movements/{movement_id}/reverse` contract. The stored state
and register label remain Reversed; this is retained removal, not hard deletion.

Confirmed movements retain Reverse and an explicit explanation of withdrawal
from current cash with historical evidence preserved. Both operations keep the
dialog mounted while pending and after failure. The parent returns success only
after the write succeeds, refreshes server reads and displays errors inside the
open reason prompt. Reversed rows offer neither action.

No API/schema, permissions, calculation, currency, dependency, migration,
CI configuration or Render settings change. Generic Cashflow recording-dialog
recovery, other cashflow draft headers, recorded Collections/Construction voiding
and REC-03 are outside this slice.

## Candidate evidence

- Frontend test suite passed (90 tests at the initial implementation), followed
  by all four removal tests after adding the confirmed-reversal regression.
- ESLint and production Next.js build, including TypeScript and static export,
  passed. This workstation's npm wrapper could not invoke the nested prebuild
  command; the native test command and Next build were run explicitly in order.
- PostgreSQL behavioral validation: the final recorded-removal tests plus the
  Cashflow workspace tests passed, 66 tests in 197.67 seconds.
  Existing development/financing, security and deletion-contract tests: 45 passed.
  New coverage exercises recorded removal for both kinds, read-only refusal,
  empty reason, missing and cross-project identifiers, repeat requests, blocked
  re-confirmation, retained register rows, no cash and one attributed audit event.
- Real Chrome browser against a separately cloned synthetic PostgreSQL database:
  both Delete paths succeeded, refreshed and survived reload. A simulated 503 on
  each path retained the selected reference and typed reason; retry used the real
  API successfully. The reason dialogs fit a 390 px phone viewport. No page errors.
- Local evidence: `outputs/finish-plan/browser-qa.json`,
  `movements-desktop.png`, `movements-after-desktop.png`,
  `development-failure-mobile.png`,
  `financing-failure-mobile.png` in the task workspace. Mobile capture visually
  inspected for legibility and usable actions.

## Existing backend validation gap found during verification

The initial two new tests expected a whitespace-only API reason to return 422,
but the existing generic ReasonRequest accepts it and the service strips it.
Those assertions failed while the other 45 selected tests passed. The UI already
trims input before submission, so whitespace becomes an empty string and the API
rejects it without closing this dialog. The new tests now assert that actual UI
payload. Direct API whitespace validation remains a separate backend hardening
item; this frontend slice does not silently change a shared schema contract.

The final desktop inspection also found an existing active-tab contrast issue
(dark text on a dark background in the shared tab style). Record this in final
UX/accessibility closure; it is not a change introduced by the movement buttons.
The movement actions and centered removal prompt remain legible.

## Acceptance boundary

This is candidate validation, not operator UAT or production acceptance.
Independent review, applicable CI and human merge remain pending at handoff.
Main's Full CI was still running during implementation; its Structural and
Frontend jobs had passed. Render remains on main.
