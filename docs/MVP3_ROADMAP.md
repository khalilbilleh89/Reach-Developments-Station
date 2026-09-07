# MVP 3 roadmap — five product PRs

Authority: [MVP3_PRODUCT_SPEC.md](MVP3_PRODUCT_SPEC.md),
[ARCHITECTURE.md](ARCHITECTURE.md), [ENGINEERING_RULES.md](ENGINEERING_RULES.md).
Acceptance: [MVP3_ACCEPTANCE.md](MVP3_ACCEPTANCE.md).

**MVP 3 product: 0 / 5 COMPLETE.** PR-ENG-04 is engineering infrastructure and
governance, not one of these five product PRs. No product feature has been
implemented or accepted by creating these documents.

| Order | Product PR | Initial status | Expected schema impact |
| --- | --- | --- | --- |
| 1 | PR-V3-01 — Project Setup & Lifecycle Simplification | NOT STARTED | None unless a genuine invariant requires a reviewed migration |
| 2 | PR-V3-02 — Pre-Launch & Consultant Engineer | NOT STARTED | Consultant engineering; provisional 0016, resolved against actual head |
| 3 | PR-V3-03 — Sales Commission Distribution | NOT STARTED | Next legitimate sequential revision |
| 4 | PR-V3-04 — Project Analysis Suite | NOT STARTED | None expected |
| 5 | PR-V3-05 — Integrated UAT, Hardening & Main Promotion | NOT STARTED | Verification; only justified corrective changes |

## PR-V3-01 — Project Setup & Lifecycle Simplification

Contextual country/currency setup in New Project; project identity, jurisdiction,
base/reporting currency, fiscal basis and programme. Simplify Settings navigation
and remove generic Reference Data from ordinary navigation while preserving
normalized configuration and contextual domain paths. Remove ordinary Pricing
navigation, redirect obsolete links, rename Sales & Legal to Sales and establish
the final MVP 3 lifecycle shell. A future workspace is not shown as implemented
before its owning PR supplies it. Add backend-derived Land Total Acquisition Cost
and clear Obtained / Issued permit presentation.

Retain PriceVersion, Currency, CountryPack, ReferenceValue, price approvals and
history, financial precision, legal states and authorization. Expected migration:
none unless implementation demonstrates a genuine invariant. Exit: affected
tests, Smoke ownership, Frontend and independent review, with scope documented.

## PR-V3-02 — Pre-Launch & Consultant Engineer

Part A: Development-facing Pre-Launch UX over Cashflow Development Movements.
No second expense table; confirmed cash and separate confirmation stay in Cashflow.

Part B: new consultant engagement/agreement/reference, disciplines, scope, design
stages, deliverables, planned/forecast/actual dates, status/history and documents.
Agreement value is not cash; consultant payments remain Development Movements.
Register the new domain's small Smoke contract and migration integrity tests.
Expected migration name: `0016_consultant_engineering` only if 0015 is still head
when implemented. Never hardcode that number over a legitimately newer revision.

## PR-V3-03 — Sales Commission Distribution

Commission and CommissionAllocation (or equivalent narrow entities) implement
Draft → Released → Reversed. Record sold snapshot/provenance, manual commissionable
base, granted rate/amount and named beneficiary rates/amounts. Both rate and amount
sums must reconcile; beneficiary rates are of the base, not shares totaling 100%
of the commission pool. No physical delete, tiers, payroll or payout engine.

Structurally prohibit mutation of Unit Economics, direct costs, PriceVersion,
contract amounts, pricing adjustments, profit and margin. Prove no double counting
through lifecycle and rejected/concurrent-operation regression tests. Add explicit
Smoke and migration ownership. Use the next legitimate migration revision.

## PR-V3-04 — Project Analysis Suite

Fundamental, Financial and Technical Analysis as narrow backend read/derived
services over authoritative source modules. Include the specification's full
metric catalogue, explicit dates/currencies/filters/sources/denominators, source
availability, drilldown/export reconciliation and explainable deterministic
forecasting. No duplicate financial tables, warehouse, pandas, AI model or generic
Technical Score. No migration expected. Default: no new dependency. A chart
dependency requires demonstrated need and explicit owner approval.

## PR-V3-05 — Integrated UAT, Hardening & Main Promotion

One final accumulated candidate containing V3-01 through V3-04 plus closure fixes.
Complete every acceptance row with actual evidence: workflow integration,
financial reconciliation, security, dated analysis/source/export parity,
responsive, accessibility, migration/release and documentation. Review the entire
candidate, not just its last patch. Remove/retire temporary integration artifacts
where appropriate. This is the fifth product PR and the promotion into main;
there is no sixth promotion PR. Mark 5 / 5 COMPLETE only after successful acceptance
and the final candidate merges through the full gate.

## Canonical temporary MVP 3 branch workflow

This section is the single authority for the temporary topology; agent guidance
and CI documentation point here rather than maintaining separate copies.

1. PR-ENG-04 branches from verified main, targets main and stays Draft through
   implementation and independent review. First handoff stops there. It must not
   create `integration/mvp3`, start product branches or mark itself Ready.
2. After independent review accepts the exact engineering head, authorized review
   may mark Ready once. Benchmark the new sharded Full gate on this engineering
   PR: all shard results/durations, slowest shard, first-shard-start to last-shard-
   finish wall-clock, Backend aggregator and Frontend. This engineering proof is
   separate from the one planned full pre-merge gate for the five product PRs.
3. After PR-ENG-04 merges, confirm exact then-current main SHA and that its
   post-merge sharded CI starts. Create `integration/mvp3` from that exact SHA.
   Render remains configured to deploy **main**. Never deploy integration to
   production. Creation alone does not increment 0 / 5.
4. V3-01 branches from integration and targets `integration/mvp3`. Require Smoke
   and Frontend on its exact head plus independent review before human merge.
   V3-02, V3-03 and V3-04 each branch from the updated integration branch in turn.
   Do not start the next until the current PR is reviewed and merged into integration.
   Neither Draft nor Ready state on these integration PRs invokes Fast or Full.
5. V3-05 branches **from latest integration/mvp3** and targets **main**, carrying
   all accumulated product work plus its own UAT/hardening changes. During Draft
   it uses normal main Fast + Frontend. After independent review accepts the
   candidate, mark Ready once and require complete sharded Full Backend + Frontend
   on the exact reviewed head. Only then recommend human merge.
6. After successful V3-05 merge and acceptance, mark 5 / 5 and retire/delete the
   temporary integration branch. Main still receives normal full post-merge CI.

Smoke is not evidence for a main merge. A full-risk integration change must be
avoided or take an explicit owner/reviewer-approved full-gate exception. No label,
Ready toggle or environment variable silently waives the refusal. Exception
review must specify the exact full candidate and passing checks before integration
merge; if it alters the planned five-PR topology, obtain an explicit roadmap
amendment. The no-shared-risk product plan expects only V3-05 to pay for the full
pre-merge product gate. Safety exceptions cannot be hidden to preserve that target.

Superseded PR runs may cancel. Every main push receives its own Full + Frontend
run, including queued commits. A pending main run does not prevent beginning
authorized Draft work; a failing main run takes priority. Agents never merge.

## Master countdown and historical boundary

| Track | Status |
| --- | --- |
| MVP 1 | Historical delivery complete; real legacy-source migration/go-live evidence separate |
| MVP 2 | CLOSED BY OWNER on 2026-09-07 through #264; residual UAT accepted and preserved |
| MVP 3 infrastructure | PR-ENG-04 CURRENT — engineering, not product |
| MVP 3 product | 0 / 5 COMPLETE |

Do not reopen MVP 2 as an active milestone. Its partial/pending historical tests
remain truthful and may be naturally covered later without retroactive rewriting.
