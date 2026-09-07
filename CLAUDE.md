# Working in this repository

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/ENGINEERING_RULES.md](docs/ENGINEERING_RULES.md). They govern changes;
this file is a short entry point, not a second policy copy.

## Current product track

MVP 2 was closed by owner decision through merged #264 on 2026-09-07. Preserve
its Partial/Pending historical UAT rows as accepted residual debt; do not reopen
MVP 2 as a prerequisite to MVP 3. Real legacy migration/go-live remains separate.

MVP 3 authority: [product specification](docs/MVP3_PRODUCT_SPEC.md),
[roadmap](docs/MVP3_ROADMAP.md), [acceptance matrix](docs/MVP3_ACCEPTANCE.md).
The roadmap is the **single canonical temporary MVP 3 branch/PR workflow**.
Read its branch topology, sequencing, exact five-product-PR count, integration
exceptions and final main-promotion gate before starting any MVP 3 task. Do not
copy or invent alternate rules here. PR-ENG-04 is engineering, not product.

## CI and review

Engineering Rules §10a defines Smoke (integration), Fast (main Draft), and
complete sharded Full (main Ready and every main push). Smoke is not main
merge evidence. Full preserves every test file; Backend is its aggregate check.
Frontend runs for every supported event. Render remains on main.

Implement on the roadmap's appropriate branch/base. Run relevant PostgreSQL
tests, Ruff check/format, compile and frontend checks. Open the PR as Draft and
stop for independent review. Only after review accepts the candidate may it be
marked Ready through the applicable authorized path. Never recommend a main
merge before exact-head Full Backend and Frontend conclude successfully.
**Never merge: a human merges.** Pending post-merge main CI permits Draft work;
a failure takes priority. Do not change Render's branch or use production data.

## Maintaining test selection

Fast ownership and transitive downstream edges live in scripts/ci_backend_tests.py.
Smoke representatives and migration owner/integrity registrations live in
scripts/ci_backend_smoke.py; unknown/shared-risk work refuses immediately.
Full discovers and partitions all test files automatically. Update selector
and workflow guards when legitimately changing CI. Never skip/delete tests,
substitute SQLite, suppress failures or add dependencies to obtain a green run.
