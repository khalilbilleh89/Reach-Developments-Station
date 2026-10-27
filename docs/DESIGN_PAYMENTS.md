# Design appointments and stage payments

The Design tab keeps the existing consultant-engineering API URLs and navigation
key for compatibility. Existing agreements become `main`; each project may have
one active main appointment and multiple independent active `subconsultant`
appointments. Each agreement has its own company, scope, programme, disciplines
and deliverables. The company/agreement selector includes retained history.
Project delivery reporting continues to use the active main appointment.

## Stage fees and cash

`agreed_payment_amount` is an optional gross stage fee in the project's base
currency. Null means not agreed; zero is explicit. Completing a stage with an
actual completion date enables payment entry after the agreement is activated.
The user enters the amount excluding VAT and the applicable VAT percentage;
Cashflow's existing Decimal calculation and rounding produce VAT and gross cash.

Design stores a stage-to-movement link, not another amount or ledger. The existing
Consultants development movement appears in Pre-Launch and counts exactly once
when confirmed. Recorded and confirmed amounts are presented separately; the
remaining stage amount is agreed gross less confirmed cash. A negative remaining
amount is an overpayment, not a clipped zero. Reversed/removed movements remain
visible but leave both current totals. No forecast or payable is created by
completing a stage or entering an agreed fee.

Recording uses a project-scoped request UUID and payload fingerprint, under the
project lock. A retry returns the same link; reuse with different details refuses.
Stage version and completion dates are validated before writing. Standing recorded
or confirmed payments prevent reopening or changing completion. A database trigger
also prevents generic Pre-Launch corrections from changing the category or dating
a linked payment before completion. Cashflow translates that named constraint into
a recoverable conflict without importing Design.

## Access and evidence

Existing Design readers retain programme access. Actual payment totals and PDFs
require Cashflow read permission before any request. PM/Finance record; existing
Finance/CFO confirmation and Boss self-confirmation rules apply unchanged.
Every route scopes project, payment and proof identities. Phase-scoped requests
remain refused by the existing Design project dependency.

Each payment accepts optional PDFs during entry or later, including after
confirmation. Uploads authorize before reading the body, stream at most 10 MiB,
validate filename and PDF signature, and store bytes and SHA-256 in PostgreSQL.
Duplicate active content on the same payment returns the existing proof. Download
uses attachment, no-sniff and private/no-store headers; no public file URL exists.
This signature check does not establish document authenticity or perform malware
scanning.

Payment and PDF save are separate: after a successful payment save, a failed PDF
upload retains the selected file and retries only the upload. Users may finish
without a PDF. Unconfirmed payment deletion uses retained Cashflow removal;
confirmed payments use reversal. PDF deletion requires a reason, hides the proof
and retains its bytes, identity, hash and audit. Unused draft appointments may be
deleted with a reason and version check; linked programmes block deletion.

## Migration and rollback

Revision `0052_design_payments` preserves existing appointments as main, changes
only the active-main uniqueness predicate, adds optional stage fees and the two
attribution/evidence tables. Downgrade is allowed only before stage fees,
sub-consultants or payment/proof history exist. Afterwards restore the application
version only if compatible, or roll forward; do not discard retained evidence.
