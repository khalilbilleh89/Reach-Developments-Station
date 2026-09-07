# MVP 3 acceptance matrix

Criteria established by PR-ENG-04 **before product implementation**. Product
authority: [MVP3_PRODUCT_SPEC.md](MVP3_PRODUCT_SPEC.md). Delivery and temporary
branch workflow: [MVP3_ROADMAP.md](MVP3_ROADMAP.md).

All rows begin PENDING. Evidence is filled during V3-05 from actual integrated
execution against its accumulated candidate. Individual PR tests support their
review but do not silently mark final acceptance passed. Record exact SHA, command/
scenario, synthetic dataset, date/time/as-of/currency/filter, actor roles, result,
artifact and reviewer. Failure or unavailable evidence is not a pass. Re-execute
affected rows after fixes; preserve failed/partial evidence and its resolution.

| Workflow | Required pass criteria | Status | Evidence |
| --- | --- | --- | --- |
| Project creation | Create with contextual country/currency, identity, reporting/base currency, fiscal basis and programme; no Settings detour, duplicate normalized records or unauthorized configuration writes | PENDING | — |
| Land | Purchase price + fees produces exact backend Decimal acquisition consideration; currency and missing-input behavior explicit; total not editable or mislabelled valuation | PENDING | — |
| Permits | Contextual type creation; Obtained / Issued reflects existing precise state; statutory transitions, permissions and dated history retained | PENDING | — |
| Pre-Launch | Record and separately confirm Development Movement through Development UX; recorded excluded from cash, confirmation counted once, reasoned reversal; no duplicate expense/source | PENDING | — |
| Consultant agreement | Engagement/reference, consultant, disciplines, scope, agreement value/currency and documents persist; access/audit correct; no consultant-owned cash writes | PENDING | — |
| Consultant design stages | Deliverables and planned/forecast/actual dates, progress, corrections/history; no implied certification/payment or lost revisions | PENDING | — |
| Inventory | Hierarchy/register/import validation and atomic apply, phase scope, six-component gross, features/documents and excluded parking/storage persist | PENDING | — |
| Direct pricing through Unit | Separate approval/activation, immutable history and frozen sale provenance; price/gross backend-derived; obsolete Pricing links redirect safely | PENDING | — |
| Sales | Sales label retains buyer/reservation/SPA/signature/registry/cancellation workflow; frozen values, PII and independent four-status meanings survive | PENDING | — |
| Payment Plans | Create from sale, percentage/amount/tax/fee reconciliation, separate approval, activation/revision and dated triggers; authoritative history preserved | PENDING | — |
| Collections | Record versus confirm, maker/checker, allocation/unapplied cash, refund/reversal/history and confirmed receipts / total SPA payable incl. tax/fees; refunds separate | PENDING | — |
| Commissions | 150000/10% example yields 15000 and 5/3/1/1 allocations; differing manual base works; exact rate and amount reconciliation, rounding, access, concurrent release and reversal; no mutation/double counting in economics, price, sale or cash | PENDING | — |
| Construction | Physical stage configuration/completion/corrections, separate units, certificates/invoices/payments and financial-control independence remain sound | PENDING | — |
| Cashflow | Confirmed source amounts counted once; development/construction/receipts/refunds distinct; opening + inflows − outflows = closing, restricted cash and funding basis reconcile | PENDING | — |
| Fundamental Analysis | Entire metric catalogue reconciles to filtered inventory/sale history; monthly/cohort/denominator/currency basis visible; deterministic velocity forecast explains zero/insufficient history | PENDING | — |
| Financial Analysis | Sales demand versus actual/forecast cash, unrestricted cash, funding gap, 30/60/90 requirements and coverage reconcile to sources without duplicate inflows/outflows | PENDING | — |
| Technical Analysis | Physical mix/areas/features, consultant progress/deliverables, permits and construction distribution match scoped records; no invented Technical Score | PENDING | — |
| Security | All eleven roles, project/phase isolation, denied mutation, maker/checker, PII/financial redaction, audit and no unauthorized browser requests across new and retained workflows | PENDING | — |
| Dated reporting | Screen/drilldown/export share dates, filters, currency and denominators; historical reversal/cancellation boundaries; unavailable source distinct from zero | PENDING | — |
| Accessibility | Keyboard-only primary flows; labelled controls, focus trap/return, error announcements, readable statuses and reduced-motion behavior | PENDING | — |
| Responsive | 1600/1440/1280/1024/768/390 widths across primary workflows; no page overflow, clipped primary action or unusable table/form | PENDING | — |
| Migration/release | Actual sequential head, clean upgrade/model agreement, retained-data-safe downgrade/rollback, exact-reviewed-head independent review, all Full shards + Backend + Frontend success and recorded benchmark | PENDING | — |

Use synthetic data and distinct preparer/checker identities. Do not touch Render
or production databases for acceptance or CI. No product browser UAT is required
for PR-ENG-04 itself because it changes no product behavior.

The final evidence must include every shard verdict/duration, the slowest shard,
wall-clock from first shard start to last finish, aggregator result and Frontend
result. A cancelled/skipped/failed shard cannot establish Full success. Smoke or
Draft Fast evidence never substitutes for the final main merge gate.

MVP 2 residual UAT was accepted by owner at closure; later coverage here does not
rewrite that historical matrix. MVP 1 real legacy-source migration and production
go-live retain their own evidence track.
