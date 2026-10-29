# Commercial Operations

Commercial → Operations appears directly below Commissions. Its question is:
which buyers have completed their purchase paperwork and Golden Visa steps?
It reads every authorized Sales client, including buyers with no purchase yet
and inactive buyers. Buyer identity and purchases are never copied into a second register.

## Pipeline and entry

The project starts with Signed EOI, Signed Reservation, Signed Engagement Letter,
Signed SPA, Signed POA, Bank Clearance and Opened Bank Account under Property Purchase;
Golden Visa Submission and Golden Visa Issuance under Golden Visa. Purchase purpose
is a separate buyer field: Investment Only, Golden Visa, or not yet recorded.

Configuration is a full page: add, rename, reorder, move between sections, retire,
restore or delete stages. Stable IDs preserve progress through edits. Up to 100
stages per project. The default pipeline is read without writes; the first explicit
configuration/progress save materializes it. Configuration changes affect all buyers.

Every manual milestone supports Yes, No or Not recorded, plus a calendar date.
No/Not recorded clear the date; Yes with a missing date is explicitly reported.
Golden Visa steps are applicable only after selecting Golden Visa. Investment-only
and unknown-purpose buyers have separate denominators, never false outstanding counts.
Changing purpose preserves previous visa evidence. Entries are revised with a reason.

The register includes both sections, purchase links, overall applicable completion,
next outstanding stage, buyer/purchase search, purpose and stage/status filters.
Stage analysis reports Yes, No, unrecorded, missing dates and applicability counts.
Analysis covers all accessible buyers; register filters do not relabel those totals.
All totals and progress counts come from the server.

## Connected evidence

Signed SPA reads unreversed `buyer_signed` legal events on all current, non-cancelled
sales for a buyer. All must be signed for Yes; the completion date is the latest
buyer signature. Partial completion shows signed purchases / current purchases.
This is explicitly buyer signature, not an assertion that the seller signed too.
Editing linked SPA progress is refused; the owning Sales legal timeline must be corrected.
Manual SPA entry is available only when the buyer has no current sale.

Reservation activation, a contract date, KYC clearance, and a POA reference do not
prove signed reservation, signature, bank clearance, or signed POA respectively.
Those facts are therefore never auto-completed. Operations changes do not activate
contracts, bypass legal gates, record payments or establish visa eligibility.

## Permissions, concurrency and removal

Existing Sales reader roles apply, including advisors' own-client restriction.
Because a buyer's progress spans purchases, whole-project access is required;
selected-phase membership returns 404 before buyer data is read. Configuration:
Master Administrator, System Administrator, Project Manager or Sales Operations.
Progress: Master Administrator, Sales Operations or Legal. Authority is returned
by the server and checked again for every mutation.

Writes lock the project and check explicit pipeline/buyer versions. An edit based
on an old pipeline or buyer revision fails with 409, preserving the entered form.
Foreign keys bind every stage and buyer entry to the same project.

Delete is visible in configuration and the buyer page. Unused stages are physically
deleted; used stages are retired and remain visible in the buyer's history. Delete
manual progress clears purpose/milestone rows while retaining before-values and reason
in the existing append-only audit trail. The buyer, sales and legal signatures remain.
The buyer revision frontier survives removal to reject stale replay. Individual
milestones can also be cleared to Not recorded with an audited reason.

Migration `0036_sales_operations` adds four tables without backfilling business facts.
Empty-schema downgrade is supported. Once configuration or buyer history exists,
downgrade refuses data loss: retain the schema and roll forward. Export/backup and a
separately reviewed cleanup are required before any destructive rollback.

No dependency, production environment, deployment branch or connection is changed.
Governing policy: [Engineering Rules](ENGINEERING_RULES.md) and
[Deletion Policy](DELETION_POLICY.md).


## Excel updates and register

Update from Excel opens a full-page download/upload/review flow for Operations writers.
The template contains every accessible client (up to 5,000), current purpose and
status/date pairs for the active project stages. Client identity/version and stage IDs
remain stable; visible client references, names and purchases are context, never keys.
Blue values are inputs and grey values are reference or linked Sales evidence.

Blank cells preserve existing values. Not recorded explicitly clears purpose/status;
CLEAR removes a date. No/Not recorded clears its date, and a supplied date requires
Yes. Dates accept Excel calendar dates or ISO YYYY-MM-DD; formulas are never evaluated.
Visa edits require Golden Visa purpose. Linked SPA changes are rejected.

Validation shows each proposed field change and row errors without persistence.
Apply rechecks the entire file under the same project lock and saves all changes plus
per-client audit reasons in one transaction. Any invalid/stale row prevents the batch.
A changed pipeline or client revision requires a fresh download. Unchanged clients
produce no new revision or audit event. Files and previews are never stored; imported
progress uses the existing buyer page's Delete/manual correction path.

The analysis uses server-reported completion percentages and stage cards with
clickable status/missing-date counts. The compact register leads with client identity,
purpose, overall progress and next step; Show every stage exposes the detailed matrix.
No new dependency, database table or migration is required.
