<!--
Reach Developments Station — MVP 1.0 pull request template.

Governing policy: docs/ENGINEERING_RULES.md
Roadmap position: docs/MVP_ROADMAP.md

Delete sections that genuinely do not apply. Do not delete a section merely
because filling it in is inconvenient.
-->

## CI phase

<!--
Draft  = iteration. Runs `Backend Fast`. NEVER merge from this state.
Ready  = merge candidate. Runs the full `Backend` suite on the exact head.

Any commit pushed after the PR is marked ready re-runs the full suite, so the
green tick always belongs to the current head. Never merge on an older SHA.
-->

- [ ] Draft — focused CI while iterating
- [ ] Ready for review — full exact-head regression

## Context

<!-- Why does this PR exist? Which roadmap PR is it? -->

## Scope

<!-- What exactly changes? -->

## Non-goals

<!-- What does this PR deliberately not build? -->

## Architecture

```text
Domain:
Cross-domain dependencies:
New abstraction introduced:
Why abstraction is necessary:
```

## Dependency Impact

<!-- The default and expected answer is "None". Unused dependencies are forbidden. -->

```text
Production Dependencies Added: None
Development Dependencies Added: None
Dependencies Removed: None
Justification:
Why existing framework/native functionality is insufficient:
```

## Contract Impact

```text
API Contract Changed: Yes / No
Database Schema Changed: Yes / No
Frontend Types Changed: Yes / No
Financial Calculation Changed: Yes / No
```

## Migration Impact

```text
Migration Required: Yes / No
Backfill Required: Yes / No
Destructive Change: Yes / No
Rollback Safe: Yes / No
```

## Financial Integrity

<!-- Required whenever money, rates, quantities or dates are touched. -->

```text
Source-of-truth fields:
Derived fields:
Formula changed:
Currency behavior:
Rounding behavior:
Reconciliation test:
```

## Security / Privacy

```text
Authorization impact:
PII impact:
Financial-data exposure impact:
Audit impact:
```

## Deletion coverage (required for every record-creating feature)

- [ ] Every new or changed user-created record has a visible Delete action, including child rows and configuration choices.
- [ ] Unused/draft deletion works through the UI and API; confirmation names the record and explains consequences.
- [ ] Server permissions, project/phase isolation, linked-record protection and retained audit evidence are tested.
- [ ] Posted/approved records explain their supported cancellation/reversal/retirement path.
- [ ] Lists, selections and affected totals refresh correctly after removal.
- [ ] `docs/deletion_contracts.json` is updated; no new removal gaps are introduced.

Deletion UI location, endpoint, allowed states and test evidence:

## Validation results

```text
Backend tests:
Frontend checks:
Migration test:
Manual validation:
Screenshots:
```

## Deployment

```text
Render configuration changed:
Environment variables changed:
Rollback procedure:
Post-merge checks:
```

## Follow-up

<!-- Only genuine deferred scope. No speculative "future engine" follow-ups. -->
