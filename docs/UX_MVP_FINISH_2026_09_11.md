# MVP finish plan — round-2 UX closure

Owner-directed sequence after merged UX-07 through UX-10 (#281–#284).
Governed by [Engineering Rules](ENGINEERING_RULES.md),
[Architecture](ARCHITECTURE.md), and [UX System](UX_SYSTEM.md).

## Bounded sequence

1. **UX-11 — Trustworthy Financial & Approval States:** no-forecast financial
   presentation and actor-specific Pre-Launch confirmation eligibility only.
2. **UX-12 — Draft Safety & Recovery Closure:** Documents, Payment Plan creation,
   Land parcel/planning, Permit creation/status forms; the identified principal
   failed-read retries; shared money/percentage accessibility context. Stop at
   these named gaps rather than auditing every conceivable form.
3. **Construction Budget lifecycle:** prepare, validate, submit, approve/reject,
   activate, and return/history using existing domain governance.
4. **Construction Contract/commitment lifecycle:** prepare, validate, submit,
   activate, and explain headroom/role blockers. Shared product planning with
   Budget, but a separate PR.
5. **PR-COM-SALES-01:** Sales-owned unit selection, transaction register and
   negotiated price variance. Explicit owner priority ahead of UX-13; see the
   [implementation plan](COM_SALES_01_PLAN.md). Preserve quote/exception
   governance and frozen historic prices. Implemented as a draft; see
   [handoff and acceptance](COM_SALES_01_ACCEPTANCE.md). Browser/operator
   acceptance and independent review remain pending.
6. **Narrow UX-13:** Portfolio Projects search; Exceptions project/severity/type
   filters; Portfolio return-to-page; Cashflow tab/date/forecast restoration.
7. **Operator UAT, then MVP freeze:** Sales, Finance/Collections and Project
   Management complete real tasks. Engineering checks do not substitute for use.

No Experience 5, broad makeover, new state framework, generic workflow engine,
blanket search system, or automatic Construction C. Documents/Commissions search
and unrelated register conveniences remain deferred. New scope requires a
concrete prerequisite, confirmed release blocker, or explicit owner decision.

The official [MVP Construction scope](MVP_ROADMAP.md)
still includes later lifecycles. Before freeze, reconcile that broader scope
with the proposed Budget/Contract release boundary. Do not mark unimplemented
workflows accepted or silently expand this sequence. Existing API integration
acceptance is not proof of completed operator UI workflows.

## UX-11 candidate

- Cashflow actual balances remain visible without a forecast. Funding windows,
  projected balances, forecast collection coverage and investment returns are
  unavailable until an active forecast exists. Open Forecast leads to the
  existing version workspace. Project overview funding figures use the same
  presence condition. Valid zero requirements remain zero; stale active
  forecasts retain their approved values and visible source warnings.
- Pre-Launch list/create/confirm/reverse responses add `can_confirm` and
  `confirmation_blocker`, computed for the current actor without exposing recorder
  identity. UI confirmation requires positive server eligibility. A 403/409
  refreshes the register without retrying the write or discarding its explanation.
- **Audit assumption corrected by an actual PostgreSQL test:** the general
  Master permission helper bypasses maker/checker comparison, but development
  movements have a database constraint that rejects the same recorder/confirmer.
  Eligibility now reflects that enforced rule. The locked development-movement
  write returns a readable 403 before SQL instead of the pre-existing integrity
  failure. Masters can still confirm another person's movement. Other Master
  permission exceptions and all database constraints remain unchanged.

Additive Pre-Launch response fields only; generic Cashflow response shapes stay
unchanged. No financial formula, currency, rounding, schema, migration, dependency,
CI configuration or audit-event change. Successful confirmation still counts
the same movement once in actual cash.

## Acceptance boundary

Test no forecast versus an active zero-outflow forecast and an active deficit;
retain stale-source warnings. Exercise ordinary recorder, independent confirmer,
read-only actor, Master recorder, already-confirmed/reversed state and denied
project/phase scope. Verify actual cash stays visible, the forecast next step
works, and eligibility explanations remain usable on phone.

Draft review, required CI and human merge remain separate gates. Historical
Partial/Pending UAT is preserved. Candidate validation and observed browser
results are recorded in the PR; this document does not declare operator UAT or
MVP release complete.

## UX-12 candidate

Named draft protection, principal-read Retry controls and currency/percentage
accessibility context are implemented using existing primitives. Candidate
validation is recorded in [UX-12 acceptance](UX12_ACCEPTANCE_2026_09_11.md).
This does not declare operator UAT or MVP release complete. Construction Budget
remains the next implementation slice after review and human merge of UX-12.


## Construction Budget candidate

UX-12 merged in #286 (`3844623`). The next bounded candidate completes the
Budget workspace and its correction path. See the shared
[Budget/Contract plan and Budget acceptance](CONSTRUCTION_MVP_BUDGET_2026_09_11.md).
Contracts remain the next separate PR after Budget review and human merge.
Operator UAT and the MVP scope reconciliation remain pending.

## Construction Contract candidate

Budget merged in #287 (`327ed35`). Contract/commitment implementation and the
remaining acceptance boundary are recorded in
[Contract acceptance](CONSTRUCTION_MVP_CONTRACT_2026_09_11.md). Browser/mobile
acceptance and independent review remain pending; this is not release acceptance.
Contract #288 and owner controls #289 are now merged. The owner has prioritized
PR-COM-SALES-01 next, followed by narrow UX-13, operator UAT and scope
reconciliation/freeze. Historical pending browser/operator acceptance is not
converted into a pass by either merge.
