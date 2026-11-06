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
Saving a legacy Not started/Preparing record reconciles all its recorded actual
dates even when no date changed. The permit editor always sends Save, including
an unchanged form. Other manual exception statuses are not overwritten by
unrelated edits. The separate manual status form has been removed; the existing
API remains compatible and historical exception statuses remain readable.

Migration 0063 repairs active Not started/Preparing records with existing actual
dates, using the same latest-date/tie order. Deleted records, undated records and
explicit later/exception states remain untouched. Each correction retains full
before/after facts in a system-attributed audit event, without fabricating a human
status event or changing earlier history. Downgrade retains the correction and
audit (there is no schema change); it must not restore knowingly stale status.
Legacy API initial status input remains supported when no actual date is supplied.
No new permission or dependency is required.
