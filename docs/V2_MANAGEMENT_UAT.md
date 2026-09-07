# MVP 2 batch 5 — Management, reporting and acceptance

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
| Project and permits | Free-text land classifications, add permit type, persisted dates | Pending |
| Hierarchy/import | Phase/building/floor/unit drilldown and generated workbook import | Pending |
| Physical unit | Six components total gross; parking/storage excluded; features/documents | Pending |
| Direct price | Create in unit, different-person approval, activation, correct price/gross | Pending |
| Buyer and sale | Add buyer, reserve, SPA signing, registry lodging, controlled cancellation | Pending |
| Payment plan | Create from sale, schedule reconciliation, separate approval/activation | Pending |
| Collections | Record then confirm receipt, allocation, unapplied cash, correct SPA percentage | Pending |
| Construction stages | Project stage list, independent unit completion, reasoned correction/history | Pending; #262 still has implementation follow-up |
| Management | Direct prices without policy, failed-source handling, report navigation | Static/build checks recorded in PR; browser run pending |
| Dated reporting | Same date and filters for screen/drilldown/CSV; reconcile source totals | Pending |
| Security | Eleven roles; project and selected-phase scope; no unauthorized financial requests | Pending |
| Accessibility | Keyboard-only forms, focus return, named controls, readable status text | Pending |
| Responsive | 1600, 1440, 1280, 1024, 768 and 390 widths; no page overflow | Pending |
| Database/release | Migration upgrade/downgrade, model agreement, full CI on each merge candidate | Pending |

## Closure gates

1. Finish batch 4's documented work, including stage configuration editing and
   its database/security/concurrency verification. Bring the resulting changes
   into this branch and repeat affected checks.
2. Record actual integrated test and browser outcomes above, fix findings and
   complete independent review.
3. Obtain successful required CI for the final commits. Merge batch 4 before
   batch 5; update this branch against main after the preceding squash merge.
4. Mark V2 complete only after those gates pass. Keep the legacy migration and
   production go-live evidence separate, as the roadmap requires.

No production dependencies, backend formulas, schema or deployment configuration
are added by batch 5. Rollback is an application revert; batch 4's migration has
its own retained-data rollback rules.
