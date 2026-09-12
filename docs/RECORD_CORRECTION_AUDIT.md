# Record editing and removal audit — implementation plan

Current status (2026-09-12): REC-01 / F1 merged in #295. REC-02A is addressing
F2 on main `a638294`: Cashflow recorded development/financing Delete through the
existing retained reversal, including failure retention. F3 and F4 remain separate
slices. Later Inventory/Permits changes require a fresh check before acting on F5.
The matrix below is the historical audit, not a current list of missing UI.
REC-02A verification also found that the generic Cashflow API accepts a
whitespace-only reversal reason before stripping it. The UI trims and sends an
empty reason, which is rejected; direct API validation needs a separate backend
hardening slice. See REC02A_ACCEPTANCE_2026_09_12.md.


Status: baseline source audit and approved sequence. PR-REC-01 now has an
[implementation candidate](REC01_ACCEPTANCE.md); the findings below describe
the pre-fix base, not release acceptance. Other findings remain queued.
Base: `97e08d3af058b19e7197648891eb10fce109b40e`, merged Land #292 and Sales #293.
Governed by [Engineering Rules](ENGINEERING_RULES.md) and the
[owner-directed finish roadmap](UX_MVP_FINISH_2026_09_11.md).

## Conclusion

The owner's Pre-Launch example is confirmed in the source. A recorded expense
has neither Edit nor Remove in its page. This is not a financial rule requiring
it to become confirmed first: Cashflow already permits reversal of a recorded
movement. Other genuine draft dead ends exist, but several modules already have
working edit, deactivate, withdraw or reversal operations. Do not replace those
with indiscriminate physical deletion.

Start with **PR-REC-01 — Pre-Launch expense correction and removal**. Keep the
remaining work separate; a single application-wide deletion PR would combine
unrelated financial and legal lifecycles.

## Method and limits

The [source catalogue](RECORD_CORRECTION_CATALOGUE.md) enumerates all 106 mapped
record classes and 279 declared mutation routes in app/modules. It includes
system-generated evidence, configuration and child rows, so these counts are
not counts of editable screens. The matrix below groups these by operator task.
The concrete findings were checked against both relevant UI controls and owning
services; other rows are triage findings, not completed end-to-end acceptance.

No live data was changed, no deletion was attempted, and no business behavior
was implemented. Browser/mobile acceptance is not claimed. This source review
cannot establish which user account, role or expense state the owner observed.
Reported skipped Sales CI is not converted into a successful validation result.

## Confirmed findings

### F1 — Pre-Launch recorded expenses have no correction path (high)

Reproduction from the implementation: a Finance or Project Manager records an
expense. It appears as Recorded. The page offers only Confirm to Finance/CFO;
the original recorder cannot confirm their own entry. A mistaken amount or a
duplicate therefore has no edit/removal action for its creator.

- [UI actions](../frontend/src/components/projects/PreLaunchTab.tsx#L136) show
  Reverse only for confirmed rows. No expense editor is rendered.
- [Pre-Launch routes](../app/modules/prelaunch/api.py#L64) offer create, confirm
  and reverse, but no update/delete.
- [Cashflow reversal](../app/modules/cashflow/service.py#L1279) accepts both
  recorded and confirmed movements; reversal of a recorded entry needs no cash
  confirmation. The facade nevertheless requires Finance/CFO authority even
  when a Project Manager is only correcting their own unconfirmed entry.

Fix both the UI omission and the narrow own-draft permission gap. Never require
confirming false cash simply to make a Remove/Reverse button appear.

### F2 — Cashflow movement register repeats the hidden removal action (high)

[CashflowMovements](../frontend/src/components/projects/cashflow/CashflowMovements.tsx#L234)
renders Reverse only for confirmed development/financing movements. The shared
service can reverse recorded movements. There is no header edit route for these
movements. Finance should be able to abandon a mistaken recorded movement with
a reason. This is the same task problem in another surface, but broader bank
movement editing should not expand the first Pre-Launch PR.

### F3 — Unconfirmed cash records elsewhere need distinct void paths (high)

[Receipt reversal](../app/modules/collections/service.py#L1280),
[refund reversal](../app/modules/collections/service.py#L2942) and
[construction payment reversal](../app/modules/construction/service.py#L3179)
require confirmed state. Their API route inventories have no generic edit/delete
for the recorded header. An erroneous unconfirmed record needs an explicit
abandon/void operation, not a broadened confirmed-cash reversal that accidentally
changes allocations, refunds or historical balances. Dependency and permission
tests must be designed separately for each domain before implementation.

### F4 — Draft business headers can become permanent clutter (medium)

- Commission grant: draft edit and beneficiary edit/removal exist. Reversal is
  [released-only](../app/modules/commissions/service.py#L459); no draft grant
  discard route exists. Removing all beneficiaries does not remove the grant.
- Consultant agreement: draft edit exists, but
  [transitions](../app/modules/consultant_engineering/service.py#L176) permit
  draft-to-active, active-to-completed and active-to-terminated only. A mistaken
  draft agreement cannot be abandoned through those operations.
- Versioned Budget, Payment Plan, Pricing, Cashflow and Unit Economics records
  have correction through editable draft lines/new versions and approval
  decisions, but no general draft-header discard surface in the route inventory.
  Inspect each model's one-open-version rule before adding cancellation. Do not
  require submitting junk to an approver solely so it can be rejected.

### F5 — Existing removal mechanisms are inconsistent to discover (medium)

Land's retirement control is an `is_active` checkbox within Edit parcel;
Documents calls retirement Supersede/Restore; Permits uses Withdraw through
status transitions. These are existing operations, not absent backend features.
Expose their meaning next to the record's Edit/action controls, with a reason
where required and an explanation of dependencies. Inventory's protected Delete
and Sales cancellation already provide patterns; reuse the primitives without
creating a global deletion engine.

## Record-family matrix

Role names below summarize existing roles; Master override and project/phase
scope remain governed by each backend. They are not new permission grants.
“Inspect” means source triage is insufficient for a completed state-by-state verdict.

| Page / records | Existing correction/removal | Role / state boundary | Disposition |
|---|---|---|---|
| Pre-Launch expenses | Create; confirm; backend reverse recorded/confirmed, UI confirmed only | Finance/PM record; Finance/CFO confirm/reverse; distinct confirmer | F1: implement first |
| Cashflow development/financing movements | Confirm/reverse; no header edit | Finance records; Finance/CFO confirms/reverses | F2: expose recorded removal; separate edit review |
| Cashflow restrictions/releases | Confirm/reverse routes and escrow controls | Finance and checker rules; receipt/restriction dependencies | Inspect recorded-state removal and cascading effects |
| Cashflow forecast versions/lines | Draft line write, submit/approve/reject/activate; new versions | Preparer versus CFO approval; frozen active version | Inspect draft discard; preserve approved snapshots |
| Collection receipts | Record/confirm; confirmed reversal cascades allocations | Finance; sale scope; second confirmer | F3: recorded void; preserve confirmed reversal |
| Receipt allocations | Allocate/reverse | Collections/Finance permission and receipt/installment links | Existing operation; verify eligible-state visibility |
| Collection actions/contact entries | Record operational history | Collection writer; buyer/sale visibility | Inspect correction annotation/withdrawal; retain communication evidence |
| Disputes/waivers/restructures | Resolve/withdraw and approval/decision routes | Collections requests; Finance/CFO decisions | Existing lifecycle; inspect draft/request dead ends |
| Refunds | Record/confirm/reverse confirmed | Finance; cancellation settlement dependencies | F3: recorded void |
| Inventory phases/buildings/floors/units | Edit and protected reason-gated Delete from #289 | Admin/Master per operation; children and references block | Preserve; verify clear blocker and correct child-first action |
| Sub-assets/features/unit documents | Update and activation/replacement inputs | Inventory technical roles; linked Unit | Inspect retirement discoverability; no assumption of hard delete |
| Area types/schedules/measurements | Draft correction and approved revision lifecycle | Technical/approval permissions; governed price basis | Preserve frozen evidence; inspect abandoned draft cleanup |
| Custom fields/options/values | Definition update and scoped value writes | Configuration/technical roles | Inspect deactivate/clear controls and referenced definitions |
| Land parcels | Edit including active checkbox | Project/technical roles; financial field filtering | Existing retirement, improve discoverability; inspect dependency effects |
| Land annual market assumptions | Editable annual rate through PUT; no removal route | Project writer plus financial visibility; parcel scope | New #292 row: inspect removal of an accidental year; zero growth is not equivalent to no assumption |
| Planning controls | Write updated planning facts | Technical permission; parcel dependency | Correction exists; inspect clearing mistaken optional facts |
| Permits/types/status history | Edit permit; Withdraw and other transitions | Project/technical roles; transition reasons | Existing correction; retain generated status history |
| Document references | Edit; Supersede/Restore via is_active | Project/technical permissions | Existing path; explain retirement versus deleting a file |
| Buyers and buyer parties | Edit; protected unused-buyer delete; party updates | Sales roles, own-buyer scope; admin deletion | Preserve; inspect party retirement without breaking shares |
| Reservations/adjustments | Preparation edit/reprice; cancellation | Sales permissions; active/frozen gates | Existing path; managed negotiated adjustments stay server-only |
| Sale contracts/legal events/cancellations/handovers | Draft edit, cancellation workflow, event reversal, handover update | Sales/Legal/Finance roles and legal/financial state | Preserve governed corrections; inspect draft Sale exit separately |
| Payment Plans/versions/installments/triggers | Draft schedule editing/removal; new version; trigger reversal | Preparer/checker; active schedule and receipts | Inspect draft discard; do not detach Sale or erase paid installments |
| Pricing configurations/rules/versions/benchmarks | Draft edits, approval/version lifecycle, escalation reversal | Pricing/Finance/approver roles | Inspect draft cleanup and rule deactivation; frozen prices immutable |
| Construction stages/cost codes | Edit; governed stage events; code retirement | PM/engineering/Finance per action | Existing correction; inspect mistakenly created unused record removal |
| Construction Budget/lines | Draft line update/removal; rejection/replacement | Preparer/CFO; committed headroom | Inspect draft header discard; active budget retained |
| Construction Contract/lines | Draft header/line edit/removal; uncommitted cancel; terminate/complete | Preparer/checker and dependency guards | Existing bounded path from #288; verify discoverability |
| Variations/certificates/invoices | Withdraw, reverse, void routes | Technical/Finance approval; downstream references | Inspect UI and state coverage; do not expand deferred Construction C |
| Construction payments/allocations | Allocation edits; confirmed payment reversal | Finance/checker; invoice/advance constraints | F3: recorded void, separate domain PR |
| Milestones/dependencies/forecasts | Update/cancel milestone; dependency/forecast line writes | Construction roles; confirmed events and forecast versions | Inspect draft cleanup; preserve historical evidence |
| Consultant agreements/disciplines/stages/deliverables | Draft edit, active termination; child updates and terminal states | PM/engineering; accepted records immutable | F4: draft agreement abandon; child state review |
| Commission grants/beneficiaries | Draft edit; beneficiary remove; released reversal | PM/Sales Ops/Finance prepare; Finance/CFO release/reverse | F4: draft grant abandon |
| Unit Economics allocations/pools/drivers/unit costs | Draft pool delete/update; version lifecycle; cost reversal | Domain preparer/checker; frozen allocations | Existing row-level path; inspect version discard and recorded costs |
| Projects/access/Settings/users | Update/deactivate/revoke through existing controls | Administrators/project configurators | Inspect retirement labels; no cascade project or user deletion |
| Management Actions | Update/status control | Assigned/governed action roles | Inspect cancel/close discoverability rather than hard delete |
| Reporting snapshots, audit events, status events, tax/party snapshots | Generated historical evidence | Read/governed creation; immutable evidence | Do not offer physical deletion; correct source and explain retained history |

## Execution plan — bounded PRs

### PR-REC-01 — Pre-Launch expense correction and removal (next implementation)

1. Add Edit and Remove to eligible Recorded expenses. Add server-computed
   eligibility/blocker fields, rather than UI guesses about permission.
2. Add a narrow recorded-expense update operation in Cashflow, exposed by the
   Pre-Launch facade. Support category, amount, movement date, description,
   counterparty, invoice and evidence. Preserve currency, phase, bank/value-date
   fields not present in the editor, UUID and original creator evidence.
3. Original recorders may edit their own still-recorded expense; do not give PM
   users broader cash authority. Keep confirmed/reversed amounts immutable.
   Any wider editing authority must preserve the identity-based maker/checker rule.
4. Remove an unconfirmed expense with a reason using the existing recorded
   reversal semantics. Make the UI say Removed, not cash reversal, where the
   record was never confirmed. Keep it available in history and out of current
   recorded totals. Finance/CFO retain their current reversal authority;
   allow the authorized original recorder to remove their own recorded mistake.
5. Lock project/record, recheck state and permissions, and reject stale edits.
   Use an expected snapshot of the editable fields so concurrent windows cannot
   overwrite another correction; no new state framework is needed.
6. Keep the draft/reason after 422, 403, 409 or network failure. Refresh eligibility
   without replay. Use existing dialogs, validation and duplicate-submit guard.
7. Tests: own PM/Finance correction, other user denial, reader/admin/Master matrix,
   cross-project/category refusal, stale edit, confirm-vs-edit/remove contention,
   duplicate removal, blank reason, exact Decimal totals, no new confirmed cash,
   preserved reversal history and dialog recovery. Browser at 390 and desktop.

Do not add general expense hard-delete, change posted-cash mathematics, or include
Collections/Construction accounting in this PR. No migration is expected for
the narrow expected-snapshot approach; verify during implementation.

### PR-REC-02 — Recorded cash removal (separate domain slices)

First expose Cashflow's existing recorded development/financing removal. Then
design recorded receipt/refund voiding in a separate Collections PR. Construction
recorded-payment voiding is another small slice only if that workflow is in the
accepted MVP. Each must preserve confirmed reversal and its dependency rules;
do not combine all three financial domains into one PR.

### PR-REC-03 — Abandon drafts and clarify existing retirement

Start with commission grants and consultant agreements, each with explicit
abandonment semantics. Triage version-header discard against open-version
constraints before adding it. Improve Land/Documents/Permits action labels where
existing operations suffice. Split by domain; do not make every “Inspect” row
an automatic feature commitment or mark it passed without verifying its states.

After the named gaps are resolved, run the operator task: create a mistaken
record, correct it, remove a duplicate, and understand why posted evidence is
retained. Close the matrix with evidence, then continue narrow UX-13 and UAT.
This plan is the report-before-implementation checkpoint, not an implemented fix.
