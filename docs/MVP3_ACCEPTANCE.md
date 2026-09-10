# True MVP3 acceptance

M3-01 merged in PR #273 (`5363388`); UX-06 merged in PR #274 (`73036d8`).
M3-02 merged in PR #275 (`fceb047`); M3-03 is a candidate in Draft PR #279.
MVP3: **2 / 3 merged**. M3-03 final acceptance remains pending.
Historical MVP2 Partial/Pending UAT evidence is unchanged.

Historical M3-01 required evidence: PostgreSQL owner parity; original currencies; incompatible and
mixed Cashflow refusal; weighted 10/100 penetration; converted commitment dedup;
confirmed receipt/allocation/refund reconciliation; Pre-Launch counted once;
Commission and Consultant independence; all-role, unauthorized-project and
phase-only isolation; no writes or migrations; bounded 1/20-project query growth
and EXPLAIN; paginated API responses; explicit missing-source coverage; deterministic
risks and order; responsive 1600/1440/1280/1024/768/390 views and accessibility;
focused local checks plus exact-head GitHub Backend Smoke and Frontend.

## Historical M3-01 candidate evidence — 2026-09-08

- PostgreSQL Portfolio suite: **14 passed** in 442.64 seconds on the local Windows
  test host. Covers the role matrix, phase-only and large unauthorized sources,
  original/mixed currencies, receipt allocation deduplication, 30,000 confirmed /
  10,000 unconfirmed / 5,000 refund, safe actual and governed forecast parity,
  Construction parity, weighted 10/100 penetration, read-only snapshots, partial
  EAC coverage, permit resolution, deterministic risk pages, commercial stall,
  Pre-Launch counted once and Commission/Consultant cash independence.
- Populated batch queries: **46 for one project; 46 for twenty**. Actual scoped
  PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` examples: Units hash join 0.177 ms;
  Collections receipts sort 0.123 ms; Construction budget aggregate 0.580 ms;
  forecast-line aggregate 0.361 ms; Development Movement hash join 0.090 ms.
  These are small synthetic fixtures, not production capacity measurements.
  No index or migration was justified.
- Production frontend: lint, TypeScript and build passed. Chromium exercised
  Overview, Projects, Risks and project summary at 1600, 1440, 1280, 1024, 768
  and 390 px: **24 combinations without page-level horizontal overflow**.
  Wide registers scroll internally; long row headings wrap and do not cover
  the remaining columns. Checked one h1, table captions/scoped headers, keyboard
  tabs and visible 2 px focus, pagination, source navigation, explicit currency
  and coverage, empty/loading/error states, and denied role with no Portfolio
  request. No browser page errors; one compact Portfolio read per view.
- Ruff check/format and Python compilation passed. Alembic current and heads are
  `0017_consultant_commissions`; `alembic check` detects no new upgrade operations.
  No dependency manifests or migration files changed; installed pins are compatible.

Additional focused owner regressions and exact-head GitHub Backend Smoke /
Frontend outcomes belong to the candidate PR's validation handoff. Full Backend
must stay skipped for ordinary integration development. Smoke does not certify
a main promotion. Independent review, Ready status and merge are separate gates;
none is granted by this candidate evidence. M3-02 and M3-03 remain not started.

## M3-01 risk pagination correction — 2026-09-08

The Risks endpoint now uses a Portfolio-specific set-based projection over the
authorized project relation. It shares the frozen predicates and owner financial
calculators with summaries, but builds no `ProjectSummary`, full money/Design
response graph, sellout forecast or Commission rollup. Narrow owner reads omit
Land acquisition, Construction commitment/paid rollups, Sales contracted totals
and Collections receipt/refund display totals. Cashflow's complete governing
currency checks and owner bridge remain intact.

Triggered candidates feed bounded `nsmallest(offset + limit)` selection using
the existing severity/project-code/project-UUID/risk-ID order. Only page items
become response `Risk` objects. All authorized risk facts still contribute to
the exact global total and incomplete-coverage project count; neither count is
derived from the page. Owner source reads remain proportional to authorized
source data, and deep offsets increase the retained candidate prefix. This is
not constant-time pagination or a persisted risk index.

Populated PostgreSQL risk read, `limit=20, offset=0`, excluding fixture setup
and HTTP authentication:

| Authorized projects | Queries | Runtime | Full summaries | Response risks |
| --- | --- | --- | --- | --- |
| 1 | 40 | 67.91 ms | 0 | 3 |
| 20 | 40 | 90.86 ms | 0 | 20 |
| 50 | 40 | 120.80 ms | 0 | 20 |

These are local synthetic measurements, not production capacity claims. Each
of seven owner batches is called once per read. The unchanged full-summary
path's separate 46/46-query evidence above should not be read as risk-page cost.

The regression installs failing guards on summary constructors, unrelated KPI
composition and Commission reads; `limit=1` constructs exactly one response
risk. Three pages reproduce the complete 150-risk ordered golden across 50
projects with unchanged totals and coverage. A hidden project with 30 high
risks contributes nothing to scoped source reads, counts, coverage or offsets,
including when it has phase-only access. An authorized currency mismatch
removes both formerly triggered cash candidates and marks their evaluations
unavailable. These three regressions are registered in Backend Smoke.

Focused PostgreSQL validation: **17 passed in 248.79 seconds** across
`test_portfolio.py`, `test_portfolio_risks.py`,
`test_portfolio_risk_pagination.py`, `test_portfolio_scale.py` and
`test_portfolio_governance.py`. The unchanged summary path again measured 46/46
queries. CI selector, Smoke, shard and workflow guards: **187 passed in 37.53
seconds** (source-only, `--noconftest`). Ruff check, format check (370 files),
Python compilation and whitespace checks passed.
An in-memory negative control restored the reviewed summary-then-slice read;
the regression failed at its summary-construction guard, as intended (27.89 s).

Frontend, UX-05, dependency manifests and migrations are unchanged by this
correction. Fresh exact-head CI results are recorded in PR #273's handoff.

## M3-02 Draft implementation evidence — 2026-09-09 (historical)

PR #275 branches from main `73036d8af8d98dfdc6be81034eae4ddbaeb233db`.
It was opened Draft and marked Ready externally. Main `96db2f9` is now included;
M3-02 is not merged or deployed. Full CI and Frontend are the current gates.

- Actions have separate persistence and immutable append-only history. PostgreSQL
  tests cover lifecycle, reasons, reassignment, conflicting expected versions,
  source preservation, source resolution independence, whole-project access and
  phase-only exclusion. Migration 0019 (after main's 0018 Master Administrator) round-trips and has no schema drift.
- Outlook goldens cover the existing three-complete-month commercial calculator,
  indeterminate absorption, original-currency scheduled dues distinct from cash,
  governed Cashflow lowpoints, mixed-currency refusal, stale source versions,
  permit SLA deadlines and active Consultant planned/forecast dates.
- Populated Outlook projection uses 43 queries at 1, 20 and 50 projects; measured
  0.122 / 0.310 / 0.613 seconds. The 50-project fixture includes 10,000 actions.
  Action filtered count plus page uses two queries, including owner, overdue and
  project filters. Actual PostgreSQL EXPLAIN ANALYZE plans are captured locally.
- Structural/Product Experience and CI-selection checks: 242 passed (17.81 s).
  Responsive browser matrix covers 1600/1440/1280/1024/768/390 widths, populated
  Portfolio sections, Action records and Project Overview. Desktop and phone
  management loops and Executive Viewer/Auditor read-only browser checks pass.
- Final exact-head applicable Backend and Frontend results, complete local logs,
  screenshots, commit/file inventory and contract details belong to the PR #275
  handoff. Earlier-head CI is not acceptance evidence for a later head.

Coverage limits are visible: monthly Cashflow uses whole intersecting calendar
months without daily proration; a forecast ending inside the requested horizon
is partial. Missing dates and sources remain unavailable/undated. Currency buckets
never convert or combine currencies. Completing an Action cannot resolve a risk;
a source resolving cannot close an Action. No source-owner table is written by
management actions or Outlook. There are no new dependencies or CI workflow edits.

## M3-03 Draft candidate evidence — 2026-09-10

The completed checks, test-isolation correction, retention rationale, acceptance
goldens, scale measurements and browser/print limitations are recorded in
[M3-03 evidence](MVP3_M3_03_EVIDENCE.md). This is prospective retained history;
earlier reports are never reconstructed from today's source rows. M3-01 and
M3-02 are merged (2/3); M3-03 remains Draft #279 pending independent review and
the subsequent mandatory exact-head Full gate. This does not rewrite earlier
historical acceptance or declare MVP3 complete.
