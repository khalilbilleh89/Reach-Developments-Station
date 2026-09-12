# REC-02C — recorded Collections receipt/refund removal

Independent finish-plan candidate based on main `a638294`. Implements the
Collections part of the recorded-removal gap from the record correction audit.
Does not depend on the Cashflow code changes in #307 or #308. It updates different
entries in the shared deletion manifest; retain both sets when reconciling merges.

## Operator behavior

Collections > account > Receipt journal and Refunds offer Delete on recorded
entries to Collections users. Each centered reason prompt names the receipt or
refund reference and explains retained history and the absence of confirmed cash.
On failure the reference, reason and server explanation remain visible; success
refreshes the register and account totals. Recorded removals are labelled Removed.

A receipt with active allocations cannot be removed. The refusal explains that
Collections must reverse those allocations explicitly first. Removing the receipt
then retains both the receipt and the reversed allocation history. No child rows
are silently deleted or reversed by the new removal operation.

Refund entries remain visible even if a cancellation was withdrawn and the amount
due is now zero. A failed refund read offers Retry rather than a false empty state.
Confirmed refund Reverse also now retains its reason prompt after a failed write.

## API and ownership

| Endpoint under `/projects/{project_id}/collections` | Allowed state | Authority |
| --- | --- | --- |
| `POST /receipts/{receipt_id}/void` | Recorded, never confirmed, no active allocations | Collections |
| `POST /refunds/{refund_id}/void` | Recorded, never confirmed | Collections |
| Existing receipt/refund `/reverse` | Confirmed only | Finance |

The additive void routes require the existing reason request, enforce visible
sale/project/phase scope, lock the project and record, and use the existing
`reversed` retained terminal state. Refunds also lock the owning cancellation.
An independent confirmation that wins the lock causes void to fail with 409;
void never turns into a confirmed-cash reversal. Repeated void and subsequent
confirmation also fail. Blank reasons are rejected by the existing service guard.

New audit actions `collections.receipt_voided` and `collections.refund_voided`
retain actor, time, reason, reference, sale, amount and the recorded-to-reversed
transition. Confirmed timestamps remain null. No financial formula, currency,
rounding, liability or approved cancellation term is changed. Historical reads
continue to require confirmation evidence before counting cash.

No new dependency, database schema, migration, hard-delete route or CI setting.
Deletion contracts for the two creators are implemented and removed from the
baseline gap allowance. Other Collections creators remain separately tracked.

## Candidate validation

- New PostgreSQL tests cover receipt and refund removal, Collections versus
  Finance/admin/auditor authority, real cross-project identifier substitution,
  phase narrowing, blank reasons, repeated requests, blocked confirmation,
  retained records and audit events, current/historical totals, explicit allocation
  cleanup and confirmation/void races. Also cover refund cleanup after withdrawal.
- Existing receipt/refund regression tests run separately against the same
  isolated test database after the new tests finish: 45 passed in 535.30 seconds.
  The initial new-removal/deletion-contract run passed 10 tests in 122.16 seconds.
  Final historical/withdrawal checks: 3 passed in 41.50 seconds, using a second
  isolated test database. Five unaffected new tests were excluded from that rerun.
- Native frontend tests exercise role/state controls, retained failure prompts,
  success reload, zero-liability refund history and failed-read Retry. Existing
  frontend suite passed 87 tests; all four new removal tests passed separately.
  Production build/TypeScript/static export, lint, Ruff and diff checks passed.
- Real Chrome uses a separate synthetic PostgreSQL database. Receipt removal
  returns a real active-allocation refusal and retains the reason; explicit
  allocation reversal permits a successful retry. Refund removal survives a
  simulated 503, retries through the real API and remains Removed after reload.
  Desktop and 390 px phone captures are visually inspected; no page errors.
- Local evidence is in the task workspace under `outputs/collections-removal/`:
  `browser-qa.json`, `receipt-blocked-mobile.png`, `refund-failure-desktop.png`,
  `refund-failure-mobile.png`, and `refund-removed-desktop.png`.

## Remaining gates and scope

Independent review, applicable exact-head CI and human merge remain pending.
Render stays on main. Synthetic browser checks are not operator UAT or production
acceptance. Next finish-plan work is REC-03 draft commission/consultant cleanup,
remaining correction triage, narrow UX-13, real operator UAT and scope/freeze
reconciliation. Construction payment removal remains a separate scope decision.
