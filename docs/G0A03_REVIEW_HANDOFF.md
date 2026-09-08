# PR-G0A-03 independent review handoff

This is the third and final MVP 2 Gate 0A PR: Project Analysis Suite, accumulated
G0A-02 promotion, integrated Gate 0 + Gate 0A acceptance, and the final main
promotion candidate. It does not start true MVP 3 or claim completion while Draft.
Follow [ENGINEERING_RULES.md](ENGINEERING_RULES.md). Independent review precedes
Ready; Full precedes main merge. Do not delete `integration/mvp3` in this PR.

## Candidate and scope

Base: `main`, verified at `0cd56c886801dfd000fc8986d1efc3e645f219cf`.
Branch: `v2/g0a-03-analysis-final-acceptance`, created from integration head
`2724f7b14d7c7589b882a450f7d57b60890b8bc7`. Main synchronization merge:
`aca828f5fdcbfe3c71b6b9ec5301a7fcc7cc1eb1`. `git merge-base --is-ancestor
origin/main HEAD` succeeds. The Draft PR body records the exact final candidate
SHA and links its CI runs; these cannot be embedded in their own commit.

Accumulated G0A-02 includes Consultant Engineer and Commission Distribution
modules, owning APIs, workspaces and permissions; retained-history/maker-checker
and concurrency tests; migration 0017; navigation/API types and canonical intake
updates. G0A-01 is already in main. Conflict resolution preserved G0A-02 behavior
and main's independent selector changes. No workflow/deployment change is included.
The PR's Files changed view is the authoritative complete path list against main.

## Analysis contract

`app/modules/project_analysis`: `api.py`, `permissions.py`, `schemas.py`,
`service.py`, `calculations.py` and package initializer. No persistence model.
Three GET endpoints under `/api/v1/projects/{project_id}/analysis/`:
`fundamental`, `financial`, `technical`. Shared parameters: `as_of`, `period_from`,
`period_to`, optional project-owned `phase_id` and `building_id`. The UI exposes
observation dates within Project Overview, with three role-gated section buttons.
It creates no primary navigation destination and computes no authoritative money.

Context includes project ID, as-of date, observation bounds, scope filters, project
currency, source basis and current snapshot date. Availability is available,
partial or unavailable with reason and sample size. Ratios include numerator,
denominator and source; money retains original currency. Missing coverage and
forbidden reads do not become zero. Failures, refusals and empty data are distinct.

| Role | Fundamental | Financial | Technical |
| --- | --- | --- | --- |
| System Admin, Project Manager, Finance, CFO, Executive, Auditor | Yes | Yes | Yes |
| Sales Operations | Yes | No | No |
| Design Engineering | No | No | Yes |
| Sales Advisor, Legal, Collections | No | No | No |

All require whole-project access. Selected-phase-only actors receive 403,
foreign-project access 404. Requested filters do not enlarge membership. No buyer
PII or legal document content is in the response schema. Browser visibility matches
backend authorization; hidden sections are not fetched.

## Fundamental definitions

Current primary-unit commercial, legal and delivery status dimensions are kept
separate. Eligible denominator: active Inventory units in available, reserved,
contract_pending, contracted or returned states; held, unreleased, withdrawn and
inactive are excluded. Returned stock requires repricing. Committed numerator is
the distinct eligible units in Sales' live reservation/contract states. Penetration
is committed / eligible × 100; available, active-sold and remaining counts are
separate. Historical inventory is not reconstructed, so historical penetration
and remaining-based forecasts are unavailable.

Monthly sale activations use UTC `activated_at`, not creation, reservation or
receipt dates. Cancellations use UTC `cancelled_at`, only for activated contracts.
Gross contract value is `total_contract_price` including its tax/fee snapshot;
activation and cancellation counts and net absorption are separate. Branch/advisor
rankings use standing activated sales within the period, with actual
`sales_branch_code` and `advisor_user_id` assignments. Unassigned stays visible;
creator/client owner is never substituted. Assignment IDs preserve distinct people
with identical names. Rank by count, then value only for comparable currency,
then deterministic identity; return per-currency values and shares.

Forecast = remaining eligible units / average monthly net activated-minus-cancelled
sales over the last three complete UTC calendar months. [4,5,6] gives 5/month;
30 remaining gives 6 months. No eligible denominator, missing history, historical
inventory, and zero/negative net absorption produce reasons and null estimates.
Known zero remaining is zero months. This is a transparent run-rate, not a promise.

Property and view demand use current structured `unit_type_code` and
`view_class_code`, retaining Unknown / Unclassified. Group penetration uses that
group's eligible stock; demand share uses eligible standing period sales. Historical
classification limitations are explicit. No view inference from names or prose.
Observed view premium compares total contracted value / total approved six-
component gross area with other explicitly classified views of the same property
type: (view price per gross area / baseline price per gross area − 1) × 100.
Currency and area measure must match, complete positive areas and a positive
baseline must exist. Otherwise it is unavailable. Samples/baseline are visible;
this is observed association, not a pricing adjustment or valuation.

## Financial and Technical definitions

Financial reads use the public Cashflow collector's standing-as-of rules. Business
dates choose the month; confirmation/reversal timestamps choose whether actuals
existed at cutoff. Only confirmed standing receipt/refund, development movement,
construction payment and financing rows count. Pre-Launch is the same development
row, included once. Schedule receivables, forecasts, escrow restrictions/releases,
commission liabilities and consultant agreements do not create cash. Contract
value is distinct from receipts; contract minus receipts is not overdue. No FX or
cross-currency totals. Project-level cash stays whole project even when sales have
phase/building filters; no unsupported allocation is invented. Refund and financing
details reconcile the reported net movement.

Technical reads approved area components and six-component gross, active unit
types, features and attachments; separate statutory Permit status, Consultant
agreement/design/deliverable workspace and physical construction-stage events.
Area statistics are grouped by measurement unit. Missing gross, permits, design or
construction sources are labelled. Latest construction corrections govern counts.
Consultant submission/acceptance is not construction completion. No buyer-issued
specification provenance exists, so the output explicitly says recorded technical
product profile, not a claimed buyer-issued specification. This is a current
snapshot and says so even with a historical sales observation date.

## Validation and operational limits

See [MVP2_GATE0A_ACCEPTANCE.md](MVP2_GATE0A_ACCEPTANCE.md) for the synthetic
PostgreSQL integrated journey, reconciled figures, read-only snapshots, role matrix,
phase refusal and browser evidence. Browser: 18 surfaces × 6 widths = 108 checks,
1600/1440/1280/1024/768/390; labelled controls, one h1, no page overflow or JS errors.
Desktop/mobile images were inspected. Real contextual setup, keyboard dialogs,
403/500 failure distinction and delayed Project A response after navigation to B
were separately exercised. Browser writes used a disposable database, not production.

Bulk queries group source data without per-unit queries; a populated Fundamental
API test asserts a positive count below 30 SQL statements. PostgreSQL EXPLAIN
ANALYZE on the one-unit synthetic fixture measured Inventory/Sales/latest-stage
queries at 0.079/0.044/0.068 ms. This is query-shape evidence, not a load benchmark.
Default output is 12 calendar months, maximum 732 days. Existing source collectors
read project history; work grows with project records. No cache or warehouse exists.

Analysis has no schema change. The promotion carries existing 0017 above main's
0016. The deployed-path test retains project/inventory/pricing/reservation/sale/
schedule/confirmed-receipt data, upgrades 0016 to head and checks drift/snapshots.
Fresh history round-trip and retained consultant/commission/utility downgrade
refusal are separate gates. Do not destructively downgrade retained histories as a
software rollback. The final PR body records focused test counts, Alembic checks,
Backend Fast and Frontend CI results/runtimes against the exact candidate.

Production Dependencies Added: None. Development Dependencies Added: None.
Frontend Dependencies Added: None. Dependencies Removed: None. Existing framework/native functionality is sufficient.
Validation tools/runtimes live outside tracked dependency manifests.

Documentation updates: README current/after-merge state, Product Spec source and
formula definitions, Roadmap final promotion boundary, Acceptance new integrated
evidence, Architecture read composition, this handoff; accumulated G0A-02 canonical
intake rules remain included. Historical Pending/Partial evidence is retained.

Current: MVP 1 foundation complete; MVP 2 Gate 0 complete; Gate 0A 2 / 3 merged,
G0A-03 Draft/final review; true MVP 3 NOT STARTED. Only the independently approved
exact candidate's main merge makes Gate 0A 3 / 3 complete and MVP 2 stakeholder
iteration complete. Retire integration only after post-merge verification. Stop
there: future true MVP 3 needs a new product-planning session.
