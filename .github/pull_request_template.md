<!--
Reach Developments Station — MVP 1.0 pull request template.

Governing policy: docs/ENGINEERING_RULES.md
Roadmap position: docs/MVP_ROADMAP.md

Keep every required section. For non-applicable sections give a brief reason.
PR Quality enforces this contract; comments and checkboxes are not explanations.
Draft requires Context, Scope, Non-goals, Architecture, Contract Impact,
Migration Impact and Validation results; explicit pending evidence is allowed.
Ready requires all delivery sections below. Page layout is required for frontend
source changes. Broad Drafts and Ready PRs also require Change cohesion.
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

## Repo reality / Root cause

<!-- What already exists, what is actually missing, what is reused, and why? -->

## Scope

<!-- What exactly changes? -->

## Non-goals

<!-- What does this PR deliberately not build? -->

## Change cohesion

<!-- Why does everything belong in one reviewable change? For 20+ files, 800+
additions or multiple backend domains, explain the shared delivery outcome and
why separation is unsafe, or split the PR. One precise sentence can suffice. -->

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

## Deletion / Retention

<!-- Deletion coverage is required for every record-creating feature.
Otherwise explain that this creates no user-created persistent record. -->

- [ ] Every new or changed user-created record has a visible Delete action, including child rows and configuration choices.
- [ ] Unused/draft deletion works through the UI and API; confirmation names the record and explains consequences.
- [ ] Server permissions, project/phase isolation, linked-record protection and retained audit evidence are tested.
- [ ] Posted/approved records explain their supported cancellation/reversal/retirement path.
- [ ] Lists, selections and affected totals refresh correctly after removal.
- [ ] `docs/deletion_contracts.json` is updated; no new removal gaps are introduced.

Creation route, removal route, UI location, allowed removal states, retention behavior
and test evidence:

## Validation results

<!-- Name the exact checks and results that actually ran against this code.
Never claim a pass for an unexecuted check. Explain unavailable checks and
required CI explicitly. Bare N/A is invalid; give a reason. -->

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

## Review focus

<!-- Identify the decisions, risks or edge cases the independent reviewer should inspect. -->

## Follow-up

<!-- Only genuine deferred scope. No speculative "future engine" follow-ups. -->

## Page layout

- [ ] Record creation, editing, details and drilldowns use full pages; no side drawers.
- [ ] Back preserves register context; unsaved changes and deletion controls still work.
- [ ] Desktop and mobile layouts checked; only small centered dialogs remain.

Layout explanation and desktop/mobile evidence (or reasoned non-applicability):
