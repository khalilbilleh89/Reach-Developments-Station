# Date-driven permit status

Saving actual milestone dates on creation or edit sets status in the same
transaction and appends an actor-attributed history event. No separate status
action or reason is required.

| Actual date | Status |
| --- | --- |
| Submission | Submitted |
| Accepted for review | Accepted for review |
| Comments received | Comments received |
| Resubmission | Resubmission |
| Issue | Completed |
| Renewal | Renewed |

The latest actual date wins; ties follow the table order (last wins).
Planned, forecast and expiry dates never advance status. Expiry is a deadline,
not evidence that an event happened.

An explicit actual-date edit recalculates from all remaining actual dates.
Clearing the last actual date returns to Not started, effective today. Corrections
append history rather than changing old events. Effective-date corrections that
keep the same status are recorded in the append-only audit, not as a status
movement. Re-saving matching facts adds no status event.
Unrelated edits do not overwrite manual exception statuses. Optional manual
status changes remain available for exceptions and retain their existing rules.

Existing records are not bulk-converted: saving an actual-date field reconciles
their status. Legacy API initial status input remains supported when no actual
date is supplied; actual dates take precedence when present. No schema change,
production backfill, new permission or dependency is required.
