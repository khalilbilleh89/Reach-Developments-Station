# MVP 2 batch 5 — Management, reporting and acceptance

## Historical owner closure — 2026-09-07

- **MVP 2 DELIVERY: COMPLETE**
- **MVP 2 OWNER ACCEPTANCE: CLOSED — 2026-09-07**
- **CLOSURE PR: #264**, merged as `650eef17bcffa203c6ed7a5a5b482e9cd0f27582`.
- **RESIDUAL UAT: DOCUMENTED AND ACCEPTED BY OWNER**.

The owner explicitly elected to merge #264 and close MVP 2. That governance
choice remains recorded historical evidence. Subsequent stakeholder clarification
reopened MVP 2 only for Gate 0A completion; these results are not rewritten.
The existing matrix below remains the truthful historical record of what was
and was not independently exercised before closure. Partial and Pending rows
are accepted residual UAT debt, not passing evidence. Gate 0A adds new evidence
without retroactively changing these rows.
Later regression/UAT may naturally cover them, but cannot retroactively change
this record or imply those checks were executed before closure.

MVP 1 real legacy-source migration / production go-live evidence remains a
separate historical track. This decision does not mark that track complete.

## Pre-closure record retained verbatim

The following matrix, partial results and instructions describe the state
recorded in #264 before owner closure. References below to Draft, pending gates
or incomplete acceptance are historical, not current instructions to reopen V2.

Implements V2-10 and V2-11 under [ENGINEERING_RULES.md](ENGINEERING_RULES.md).
The requirements reference is the owner's MVP document, including its final
amendments. This PR builds on batch 4 (#262); it is the fifth delivery PR,
not evidence that acceptance testing or operational go-live has completed.

## Management experience

The project overview offers a report directory using the same role catalogue
as navigation. Inventory/delivery, sales/legal, collections, construction,
profitability, cashflow and permits open their owning registers. Filtering and
exports remain with those registers, so the directory does not duplicate their
financial calculations. It fetches nothing itself.

Source coverage distinguishes loaded, loading, unavailable and refused data.
The live overview is labelled as live; it does not claim a common historical
snapshot. Dated reports continue to display the server's as-of date and currency.
An unavailable source cannot yield an unqualified all-clear attention message.

Direct-entry unit pricing counts and repricing exceptions remain visible when
no pricing policy exists. The obsolete statement that a pricing policy is
required to price any unit is removed. Financial amounts and counts remain
server-owned, and the existing mixed-currency treatment is unchanged.

Report and transaction buttons have contextual accessible names. Construction
stage configuration is expandable in the overview so project setup does not
dominate management's working surface.

## Acceptance matrix

Record an outcome and evidence for each row; an empty outcome is not a pass.
Use synthetic data and distinct users for preparation and approval. Previous PR
descriptions record their own validation, which is not substituted for this
final integrated pass.

| Workflow | Required evidence | Current integrated result |
| --- | --- | --- |
| Project and permits | Free-text land classifications, add permit type, persisted dates | Pending: integrated browser workflow not yet executed |
| Hierarchy/import | Phase/building/floor/unit drilldown and generated workbook import | Partial: API-created hierarchy and browser unit register/drawers verified; XLSX error/atomic-apply workflow pending |
| Physical unit | Six components total gross; parking/storage excluded; features/documents | API pass in combined scenario: gross 200 from 100+20+30+40+5+5, parking/storage 999 each excluded, feature/document added. Browser physical-edit workflow pending |
| Direct price | Create in unit, different-person approval, activation, correct price/gross | API pass in combined scenario: 200000 direct price, gross 200, price/gross 1000, no pricing configuration; separate approval/activation, new 210000 draft leaves live version intact. Browser workflow pending |
| Buyer and sale | Add buyer, reserve, SPA signing, registry lodging, controlled cancellation | Partial: combined API scenario creates purchaser/reservation with explicit expiry, activates reservation, converts/signs/activates SPA and lodges registry event. Cancellation and full browser sequence pending |
| Payment plan | Create from sale, schedule reconciliation, separate approval/activation | Partial: same SPA has reconciled 20/30/50 schedule prepared by Collections and approved/activated by CFO. Revision-history/browser acceptance pending |
| Collections | Record then confirm receipt, allocation, unapplied cash, correct SPA percentage | Partial: same SPA receives 10000, excluded until Finance confirms; 5000 allocated and 5000 unapplied; historical pre-receipt read excludes it. Refund lifecycle/browser acceptance pending |
| Construction stages | Project stage list, independent unit completion, reasoned correction/history | Checklist regression and browser paths passed: create/edit/date set/clear/move, separate unit progress, completion/reopen and retained actor/time/reason history; delivery unchanged. Independent review pending |
| Management | Direct prices without policy, failed-source handling, report navigation | Partial: PM report catalogue/source coverage rendered; keyboard Open Inventory & delivery reaches unit register. Failed-source injection and direct-price-without-policy browser scenario pending |
| Dated reporting | Same date and filters for screen/drilldown/CSV; reconcile source totals | Partial: historical receipt read and UTC-midnight regression passed. Screen/drilldown/export parity across all reports pending |
| Security | Eleven roles; project and selected-phase scope; no unauthorized financial requests | Checklist API role catalogue, selected-phase and cross-project boundaries passed. Broader eleven-role browser/network matrix pending |
| Accessibility | Keyboard-only forms, focus return, named controls, readable status text | Partial: checklist editor focuses name; save/cancel return to Edit; completion save returns to summary; drawer Escape returns to opener; text status present. Remaining primary workflows pending |
| Responsive | 1600, 1440, 1280, 1024, 768 and 390 widths; no page overflow | Partial: overview/checklist and unit drawer checked at all six widths with no page overflow; 390px unit header corrected and visually rechecked. Other screens pending |
| Database/release | Migration upgrade/downgrade, model agreement, full CI on each merge candidate | Local migration/schema/retained-data checks passed; wider local regression running. Final base-main and exact-head Full Backend + Frontend and independent acceptance pending |

## Closure execution evidence (2026-09-07 UTC)

Base: `8ea849e378b228b0a890e6c187896ec0752f3b39`; closure is Draft PR #264.
Synthetic data only. Standalone PostgreSQL 16.15 bound to 127.0.0.1:55432,
separate disposable regression and browser-UAT databases; no production access.

- 28 tests passed in 248.44s: existing construction stages plus new configuration,
  access/composite-FK and four real-connection concurrency cases (append, move,
  name edit, completion). Concurrent stale writers lose with ConflictError.
- 20 tests passed in 231.10s: migration history (including explicit 0014→0015→0014),
  schema agreement, retained checklist/history downgrade refusal, and physical
  completion/correction/reopen with all other mapped business tables unchanged.
- Combined direct-price→SPA→payment-plan→cash→physical-progress scenario and
  UTC-midnight default-date test passed (2 tests, 29.94s). The scenario lives in
  `tests/modules/test_construction_stage_integrated_uat.py`; it is one shared
  project/unit flow, not a claim based on old PR descriptions.
- Ruff, format check, compileall app/scripts, pip check, frontend TypeScript,
  ESLint and production static export passed during implementation.
- Full local `pytest -q tests --durations=20` was restarted after the date-boundary
  correction; its verdict is pending. The earlier interrupted run is not a pass.
- Browser evidence: synthetic Galini Blu, B1-101/B1-102; renamed Structure to
  Structural Works, moved it below Finishes, set/cleared its planned date, completed
  B1-101, reopened with a reason, retained both history entries, and confirmed B1-102
  remained untouched. Final-build completion save returned focus to its summary.
  Responsive measurements used document scroll width versus viewport width;
  drawer screenshots were also inspected, revealing and verifying the header fix.

### Findings corrected within MVP 2 scope

1. Explicit Clear planned date avoids leaving a native date input half-empty and invalid.
2. Small-screen drawer actions get their own wrapping row instead of squeezing unit identity.
3. Completion saves retain the component and return focus to the summary.
4. The shared backend default applicability date now uses UTC, matching ledger
   lifecycle cutoffs. Previously a host west of UTC could hide a receipt confirmed
   after UTC midnight from the default current view (and omit a newly activated
   schedule). Explicit requested dates and user-entered business dates are unchanged;
   frontend local calendar entry defaults are unchanged. No monetary formula changes.

These are partial execution results, **not MVP 2 acceptance**. Unexecuted browser
paths and pending full runs remain gates, not assumed passes. The closure must
stay Draft for correction and independent review.

## Closure gates

1. Verify the closure PR's stage edit/reorder implementation and database,
   security, concurrency and independence regressions.
2. Record actual integrated test and browser outcomes above, fix findings and
   complete independent review.
3. Obtain successful Full Backend + Frontend for both the final base main and
   the exact reviewed closure head. All five grouped delivery PRs are merged.
   Keep PR-V2-CLOSE Draft through implementation and independent review; only
   the owner/reviewer may authorize marking Ready. Do not merge this Draft.
4. Mark V2 complete only after those gates pass. Keep the legacy migration and
   production go-live evidence separate, as the roadmap requires.

No production dependencies, backend formulas, schema or deployment configuration
are added by batch 5. Rollback is an application revert; batch 4's migration has
its own retained-data rollback rules.
