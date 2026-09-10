# M3-03 Draft acceptance evidence — 2026-09-10

PR #279 remains Draft. Main `2e697c8bbe9d1d5908ffdc15b54e0f4f9240ca16`
contains M3-01 and M3-02; M3-03 is a candidate, not merged or deployed.
Independent review, exact-head Full CI, human merge, post-merge CI, migration
deployment and production smoke remain subsequent gates. Historical MVP1/MVP2
and earlier MVP3 acceptance records are unchanged.

## Failure investigation and database isolation

The review supplied a migration-roundtrip failure (1 failed / 742 passed).
The retrievable CI run `34436400385` on reviewed head `23fad1c` instead reports
1 failed / 3126 passed: the full business golden attempted to govern Cashflow
with an undated manual lender installment. The corrected fixture supplies its
forecast date through the existing Payment Plans API before governance. The
owner's refusal is preserved. These are distinct findings; the supplied
migration failure was not reproduced in that retrieved log.

The migration test's assumption is now explicit: `empty_database` establishes
base before the generic base → head → base → head test, which checks both
reporting tables contain zero retained rows before downgrade. The shared
throwaway-database lifecycle explicitly includes both reporting tables in its
privileged TRUNCATE. Previously cleanup depended on foreign-key cascade from
other tables, so inspection alone does not establish why the reported run
retained rows. No DELETE or trigger bypass was added to application code.
Transaction rollback cannot contain tests that commit through separate API
connections and execute Alembic DDL; administrative fixture reset is intentional.

The dedicated integrity golden creates a genuine snapshot, refuses UPDATE and
DELETE on both tables, refuses additional inconsistent scope at deferred
constraint evaluation, refuses downgrade with retained data, compares all
persisted rows before/after refusal, and verifies the revision remains
`0020_management_reporting`. Test-only cleanup then proves empty downgrade and
upgrade with no metadata drift. Migration 0020 and its production protections
are unchanged by this correction. `HEAD_REVISION` remains 0020.

## Action retention decision

Snapshots retain full detail only for open/in-progress Actions, frozen counts
for all statuses, and `(action_id, project_id, version)` visibility frontiers for
every captured Action. Terminal titles, owners, dates and completion detail are
not repeatedly copied into every snapshot. Append-only Action history supplies
interval execution events, bounded by the captured versions and `(A, B]` time.
No current Action or User join reconstructs the comparison.

The per-Action frontier deliberately remains linear in Action count: one global
timestamp or maximum ID cannot distinguish a concurrent transaction that commits
late from a row visible in the capture's repeatable-read view. This retains
correctness while removing avoidable terminal detail growth. Tests cover cancel,
reopen, start, complete, consecutive intervals and unchanged earlier comparison
and Board Pack after later changes. This Draft payload evolves before deployment;
no deployed historical documents or backfill are assumed.

## Acceptance coverage

| Requirement | Executable evidence |
| --- | --- |
| Full A → source changes → B story | `test_management_reporting_golden.py`: live sale/plan, confirmed receipt, governed forecast versions, construction, issued permit, consultant dates and Actions; later receipt/reopen cannot change prior reports |
| Currency separation | Comparison golden: JOD +250000 and USD -50000 remain separate; absent currency is not zero |
| Coverage and Cashflow mismatch | Both unavailable→available and available→unavailable omit deltas; forecast denomination changes preserve each currency and source version |
| Sales penetration | 40/100→47/100 is +7 percentage points; 40/100→47/110 is +2.73, with denominator movement retained |
| Construction | Exact Decimal EAC +0.002 and budget +0.001; incompatible estimate basis omits delta |
| Portfolio composition | Added/removed projects identified; portfolio total deltas suppressed when scope changes |
| Risk history | Stable identity yields new/resolved/continuing; lost evaluation coverage yields coverage-changed, not resolution |
| Action/risk independence | Completed funding Action leaves cash deficit continuing; issued permit resolves risk while permit Action stays open |
| Action interval | Exact lower/upper timestamp boundaries plus visibility versions; adjacent intervals do not double-count |
| Consistent capture | Two concurrent connections mutate receipt/project during capture; every captured owner read retains the original repeatable-read view |
| Atomicity and business unavailable | Technical exception leaves no snapshot; owner unavailable is successfully retained with its explicit reason |
| Authorization | Capture/read role matrix, unauthorized and phase-only access, and revocation of one project deny the whole retained document |
| Reproducibility | Board Pack and comparison remain equal after source mutation and Action lifecycle changes |
| Source independence | Full persisted-row comparison excludes only reporting tables and session bookkeeping; operational owner rows remain equal |
| Migration protection | Clean roundtrip, retained refusal, immutable payload/scope and deferred equality as described above |

Comparison arithmetic goldens intentionally use typed in-memory retained payloads
for exact edge values; the separate business golden performs legitimate source
workflows and persists both captures. Neither form substitutes for the other.

## Validation results

Local results are recorded below. Exact-head Draft CI links and SHA belong to
the PR handoff after push; a local pass does not substitute for those checks.
The mandatory Full gate remains deferred until independent approval.

- Product Experience and CI-selector source checks: 185 passed after the
  navigation class correction.
- Management Reporting: all six PostgreSQL suites, 26 passed in 216.04 seconds
  after the fixture correction, including the full business golden.
- Full migration-focused suite: all 13 files, 181 passed in 805.29 seconds,
  against the same disposable database after the reporting regression. This
  includes the generic base → head → base → head roundtrip. An earlier duplicate
  run on OneDrive encountered setup errors and was stopped; it is not pass
  evidence. The complete isolated rerun above is the authoritative result.
- Fresh PostgreSQL Alembic `upgrade head`, `current`, `heads`, and `check` passed:
  one head, `0020_management_reporting`, no new upgrade operations detected.
- Portfolio, Outlook, Actions and workspace regression: 202 passed; its one
  stylesheet failure was corrected and verified in the 185-test source rerun.
- Ruff check and format: passed (408 files); compilation, dependency consistency
  and whitespace checks: passed. No dependency manifests or CI workflows changed.

## Synthetic scale and payload measurements

Windows, Python 3.13.15 and PostgreSQL 16.15, disposable local database with
fsync/synchronous commit disabled. These timings are synthetic diagnostics,
not production capacity or durability evidence.

| Projects | Capture queries | Seconds | Payload bytes |
| --- | --- | --- | --- |
| 1 | 182 | 0.3198 | 31,409 |
| 20 | 182 | 0.2942 | 415,808 |
| 50 | 182 | 0.5108 | 1,014,615 |

| Historical read | Queries | Seconds | Response bytes |
| --- | --- | --- | --- |
| List | 2 | 0.0059 | 1,301 |
| Detail | 1 | 0.0482 | 1,015,045 |
| Comparison projection | 0 | 0.0021 | 45,069 |
| Board projection | 0 | 0.0001 | 1,015,571 |

Projection query figures exclude fetching their retained inputs; the comparison
fixture has no Action events. Eventful comparison uses append-only history.
EXPLAIN ANALYZE confirms the scope lookup uses `ix_mrsp_project_snapshot`.
The three-row snapshot list appropriately uses a small sequential scan/sort;
that plan is not evidence for a large archive.

The separate 1,000-completed-Action/2,000-history-row fixture measured 573,890
bytes for full detail versus 116,000 bytes for compact frontiers (79.8% less).
It verifies zero terminal detail entries and a frozen completed count of 1,000.

## Browser and print scope

Snapshot, comparison and Board Pack use durable query routes and real navigation
links. Captured permit and Consultant facts are rendered in historical documents.
Board printing expands all retained Outlook disclosure sections for print and
restores their prior screen state afterward. Focus decoration is suppressed on
paper. Browser QA uses an isolated Chromium session against a disposable seeded
database, not production or the user's authenticated browser profile.

The final Chromium run passed 24 combinations: register/snapshot/comparison/Board
at 1600, 1440, 1280, 1024, 768 and 390 pixels. No document-width overflow and
exactly one H1 were observed throughout. Dialog focus entry, forward/reverse Tab
containment, Escape and focus restoration passed at each width. Keyboard submission
created both portfolio and project snapshots. Deep links, selected comparator,
reload and back/forward navigation passed; no JavaScript page errors occurred.
This is targeted keyboard/semantic QA, not a screen-reader certification.

An explicit heading-order assertion found the shared header component's default
H3 skipped H2 in full-page reports. Top-level reporting sections now request H2;
comparison subsections remain H3. The final browser matrix checks heading order
and nonempty table headers. Separate keyboard checks select and clear the prior
snapshot, activate Board Pack navigation, and invoke the Print button's browser
print action. These checks pass on the corrected production build.

A4 and Letter each produced 14 populated pages, inspected as rendered images.
Tables wrap inside the page, repeat column headers and show 30/60/90-day Outlook
content. No blank pages or clipping were found; currency, capture identity,
coverage reasons and source versions remain visible. Sidebar/action controls
are absent. Printing temporarily expands closed sections and restores them.
The retained QA A/B documents were used even after later live source mutations.

Native Windows print-dialog automation was stopped by the computer-use URL
safety check. Chromium A4/Letter PDF rendering can verify the browser print
engine and document layout, but does not claim that native dialog was exercised.

## Changed files against main

- `app/db/migrations/env.py`
- `app/db/migrations/versions/0020_management_reporting.py`
- `app/main.py`
- `app/modules/consultant_engineering/batch.py`
- `app/modules/management_actions/reporting.py`
- `app/modules/management_actions/schemas.py`
- `app/modules/management_reporting/__init__.py`
- `app/modules/management_reporting/api.py`
- `app/modules/management_reporting/board.py`
- `app/modules/management_reporting/canonical.py`
- `app/modules/management_reporting/comparison.py`
- `app/modules/management_reporting/models.py`
- `app/modules/management_reporting/permissions.py`
- `app/modules/management_reporting/repository.py`
- `app/modules/management_reporting/schemas.py`
- `app/modules/management_reporting/snapshot.py`
- `app/modules/projects/batch.py`
- `CLAUDE.md`
- `docs/ARCHITECTURE.md`
- `docs/CANONICAL_INTAKE_CONTRACT.md`
- `docs/MVP3_ACCEPTANCE.md`
- `docs/MVP3_M3_03_EVIDENCE.md`
- `docs/MVP3_PRODUCT_SPEC.md`
- `docs/MVP3_ROADMAP.md`
- `frontend/src/app/globals.css`
- `frontend/src/app/portfolio/page.tsx`
- `frontend/src/components/portfolio/Reporting.tsx`
- `frontend/src/components/portfolio/ReportingDocument.tsx`
- `frontend/src/lib/api/reporting.ts`
- `scripts/ci_backend_smoke.py`
- `scripts/ci_backend_tests.py`
- `tests/conftest.py`
- `tests/modules/test_commissions_review.py`
- `tests/modules/test_consultant_engineering_review.py`
- `tests/modules/test_management_reporting_comparison.py`
- `tests/modules/test_management_reporting_golden.py`
- `tests/modules/test_management_reporting_integrity.py`
- `tests/modules/test_management_reporting_scale.py`
- `tests/modules/test_management_reporting_security.py`
- `tests/modules/test_management_reporting.py`
- `tests/modules/test_migration_management_actions.py`
- `tests/modules/test_project_analysis.py`
- `tests/test_ci_selector.py`
- `tests/test_migrations.py`
