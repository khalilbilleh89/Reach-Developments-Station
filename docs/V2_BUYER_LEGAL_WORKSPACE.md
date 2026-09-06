# MVP 2 batch 2 — Buyer, reservation, sale, SPA and registry

Implements V2-05 and V2-06 under [ENGINEERING_RULES.md](ENGINEERING_RULES.md).
Built on batch 1 (#259); merge batch 1 first, then rebase this batch onto main
and run its final checks. The draft targets the batch 1 branch to show only
batch 2 changes. CI currently triggers only for PRs targeting main; after #259
merges, rebase and retarget this PR to main before review completion and full
exact-head CI. Starting this branch does not cancel or replace #259 CI.

## Operator workflow

Open a unit and choose Buyer, reservation & sale. For an available unit,
Add buyer & reserve opens the same reservation form as the Sales register.
Choose an existing buyer, search by name/reference, or add a buyer in place with
name, phone and email. Confirm sole ownership to create the named purchaser at
100% together with the buyer. For joint ownership, clear the checkbox and use
Buyers to record the parties and shares before activating the reservation.

Enter reservation expiry and price-lock dates explicitly. Prepare reservation
saves a draft at the server's live unit price. It does not hold the unit. Review
the terms and deposit gate, then choose Reserve this unit. Unfinished drafts
remain accessible from the unit; an active commitment takes precedence over a
draft. Cancellation uses the existing reasoned cancellation route, and expired
reservations use Close as expired. Unit status is never edited directly.

Sales Operations converts a live reservation to Sale / SPA, saves the SPA
number and contract date, and submits for signature. Legal records the existing
SPA preparation/issue milestones and each party's signing date under SPA &
registry. The shortcut buttons select a milestone for the dated form; they do
not bypass prerequisites or record an event by themselves. Once both signatures
and the required payment evidence exist, Sales Operations chooses Complete sale.
The backend alone decides whether activation is permitted.

Buyer contact, SPA signatures, land registry lodging date, authority reference,
lodging document and registration date are shown on the unit. The deal file
also places these dates above the contract and legal timeline. Only legal events
included in the server's effective_event_ids appear as current facts. Withdrawn
milestones remain on the timeline and disappear from the current summary.

Khalil's reference emphasizes lodging as the buyer's important legal milestone.
It is prominent here, while the established separate commercial and legal states
remain intact: signing, contracted, lodged, registered and title transferred do
not overwrite each other. Handover retains Legal, Collections and Delivery
clearances. Contract termination retains its approval/withdrawal/refund process.

The existing payment-plan summary stays alongside the sale. Editing the SPA
payment schedule and the receipt journal belongs to batch 3.

## Contracts and control

POST /projects/{id}/sales/clients accepts optional sole_purchaser_name (1–200
characters, at least one non-whitespace character). When supplied it creates a
primary purchaser with share_fraction 1.000000 in the same transaction. Omitted
or null preserves existing registration behavior. No new table, migration,
dependency, price formula, role or status is introduced.

The purchaser's name is explicit input, not inferred from display_name. The
service records client.created and client_party.created using existing audit
snapshots, without copying contact or identity details into the party audit.
Registration retains project access, operational-state requirements, role gates
and automatic ownership for a creating advisor. Subsequent purchaser updates
and submitted sale snapshots retain their existing rules.

Frontend components compose existing Sales APIs. Financial amounts, ownership
reconciliation, approvals, legal prerequisites and legal standing remain server
owned. Client responses retain backend PII redaction. Design/Engineering never
requests the sales record. Buyer searches and mutations run only from permitted
commercial workflows. Failed writes keep form inputs available for correction.

## Validation and rollout

Focused PostgreSQL tests cover sole-buyer reconciliation, redacted reads,
authorization, joint-buyer compatibility, invalid inputs and rollback if the
ownership audit fails. Existing legal, security, price-lock, cancellation,
handover and product-experience regression tests cover the retained controls.
Browser validation covers the buyer-to-sale workflow, legal dates and responsive
layouts. Exact-head CI and independent review remain required before merge.

No data backfill or production action is required. Rolling back this application
change leaves buyer and purchaser records in the existing schema; older code can
continue reading and managing them.
