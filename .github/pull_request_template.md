<!--
Reach Developments Station — MVP 1.0 pull request template.

Governing policy: docs/ENGINEERING_RULES.md
Roadmap position: docs/MVP_ROADMAP.md

Delete sections that genuinely do not apply. Do not delete a section merely
because filling it in is inconvenient.
-->

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

## Validation

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
