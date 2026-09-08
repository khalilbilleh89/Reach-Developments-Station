# True MVP3 acceptance

M3-01 is an implementation candidate, not independently accepted. MVP3: 0 / 3.
Historical MVP2 Partial/Pending UAT evidence is unchanged.

Required evidence: PostgreSQL owner parity; original currencies; incompatible and
mixed Cashflow refusal; weighted 10/100 penetration; converted commitment dedup;
confirmed receipt/allocation/refund reconciliation; Pre-Launch counted once;
Commission and Consultant independence; all-role, unauthorized-project and
phase-only isolation; no writes or migrations; bounded 1/20-project query growth
and EXPLAIN; paginated API responses; explicit missing-source coverage; deterministic
risks and order; responsive 1600/1440/1280/1024/768/390 views and accessibility;
focused local checks plus exact-head GitHub Backend Smoke and Frontend.

## M3-01 candidate evidence — 2026-09-08

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
