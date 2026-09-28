# CI strategy: test according to blast radius

Required pull-request status names remain **PR Quality**, **Backend**, and
**Frontend**. Review readiness does not change test breadth: Draft and Ready
pull requests run the same plan for the same head and diff.

## Backend risk tiers

### Module

One product domain changed. Backend runs static quality, dependency validation,
compilation, a real PostgreSQL 16 migration to head, Alembic drift detection,
the global invariant pack, the changed domain's tests, and tests for its direct
consumers. Selection stops after one downstream edge.

Examples:

- Pricing selects Pricing and Sales, not Payment Plans, Collections, Cashflow,
  or Portfolio.
- Sales selects Sales, Payment Plans, and Unit Economics.
- Construction selects Construction, Cashflow, and Unit Economics.
- Projects selects Projects, Inventory, Management Actions, and Cutover.

An unregistered `app/modules/<name>/` change is a plan error. Register its module
path, test prefixes, and direct consumers in `scripts/ci_backend_tests.py`; CI
does not hide that omission behind a long Full run.

### Cross-domain

Two or more product domains intentionally changed. Backend runs the invariant
pack, every changed domain, and each changed domain's direct consumers. It does
not recursively select consumers of consumers. This tier is larger than Module
but is still targeted.

`EDGE_CONTRACT_TESTS` in the selector is the extension point for replacing a
consumer's complete test family with a smaller explicit producer-to-consumer
contract pack when those contracts are introduced.

`CROSS_DOMAIN_CONTRACT_PACKS` is the fail-closed equivalent for one cohesive
feature that changes several domain-owned adapters together. A pack activates
only when its exact product path set and its integration test change together;
partial or additional product changes fall back to the ordinary domain
families. The risk tier and changed-domain report remain cross-domain.

Cross-domain plans with more than 80 selected files are deterministically split
across three targeted runners. Each selected file is assigned exactly once by
collected-test weight. This preserves the complete risk plan while keeping the
serial targeted job inside its 20-minute bound; ordinary plans still use one
PostgreSQL runner.

### System

Foundational behavior changed: `app/core`, authentication/access core, shared
database base/session infrastructure, Alembic environment semantics, dependency
files, pytest configuration, or the shared test harness. Required Backend runs
static/migration checks and the complete backend suite across eight shards.

Routine router registration in `app/main.py`, an ordinary domain migration, and
CI tooling changes are not System risk.

## Global invariant pack

Every backend-bearing targeted plan retains configuration/bootstrap, migration
history and drift, authorization, audit, strict request handling, selector and
workflow guards, test isolation, deletion contracts, canonical intake
classification, and PR/agent governance. In particular,
`tests/modules/test_cutover_intake_contract.py` always runs, so a new table with
no intake disposition fails in the targeted lane.

An ordinary domain migration also selects its domain migration tests. CI always
runs `alembic upgrade head` and `alembic check`. Changing
`app/db/migrations/env.py` is System risk; merely adding a domain-owned revision
is not.

## No-backend changes

Docs-only and frontend-only diffs do not start PostgreSQL. The required Backend
aggregate still reports success with `No backend-affecting files changed — PASS`.
Frontend remains always-on and runs `npm ci`, lint, the complete frontend test
suite through `prebuild`, and the production build.

## Full Backend Shadow

`.github/workflows/full-backend-shadow.yml` runs the complete backend suite when
manually dispatched or when a pull request receives `ci:full`. It publishes
JUnit XML, pytest logs, pass/fail totals, duration, and slowest tests. It is not
part of the required Backend aggregate, and failures stay red and visible.

Use `ci:full` for a major cross-domain refactor, release candidate, large
financial-engine redesign, manual confidence sweep, or suspected hidden
integration regression. Explain the blast radius when applying it.

Do not use `ci:full` merely because a pull request is Ready, adds a table,
changes a frontend page, or changes one module.

## Performance and cost targets

- Ordinary backend module PR: target at most 10 minutes, warning after 15,
  timeout at 20; normally one PostgreSQL runner.
- Frontend: target at most 3 minutes.
- PR Quality: seconds.
- System Full: allowed to take longer and use eight PostgreSQL shards because it
  is rare by design.

Main pushes use the same selector over `github.event.before` to `github.sha`.
They do not automatically launch Full. Pull-request runs share one concurrency
group per PR, and a newer run cancels the obsolete run.
