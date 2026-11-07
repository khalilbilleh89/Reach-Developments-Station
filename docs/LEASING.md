# Leasing

Leasing is an owner-service workspace at `/leasing/`, directly below Projects
in the navigation. It spans the projects the reader can access in full. It owns
letting instructions and tenancy terms, independently of development sales.

## Working flow

1. Choose New instruction, a project and an existing active unit. Search and
   paginate the unit register. The physical profile comes from Inventory;
   the buyer on an active sale is suggested as the instructing owner.
2. Confirm the owner using the project's existing client register. Missing
   ownership or approved area stays explicitly missing. A sale buyer is a
   source reference, not a certification of title.
3. Save an Instruction while details are incomplete. To move to On market,
   Negotiating or Leased, supply an owner, mandate date/reference and positive
   monthly asking rent.
4. Leased also requires tenant name, positive agreed monthly rent, start/end
   dates and agreement reference. Deposit is optional. Terms do not post cash,
   generate receivables, calculate taxes or change development status.
5. Record the next action and follow-up date. The register provides scoped
   stage counts, due follow-ups and leases ending within 60 days of the stated
   as-at date. Ended leases remain Leased with a review flag until updated.
6. Close the cycle and start a new instruction for a later tenancy. Only one
   non-deleted open instruction may exist per unit. Closed cycles cannot be
   reopened; corrections to their recorded details require a reason.

## Source and money boundaries

Inventory and Sales expose narrow read contracts. Leasing does not update
either source. Unit labels, physical facts and client names remain live links;
the selected owner and tenancy terms remain on the instruction. A detail
warning identifies a difference from the current active sale's buyer.
No passports, phone numbers, email addresses or identity documents are copied.
Tenant name is a tenancy field visible only to the Leasing reader roles.

Rent and deposit use NUMERIC(18,2), exact Decimal API strings, and the currency
captured from the project when the instruction is created. Later project-base
correction preserves existing Leasing denominations. No cross-currency totals,
annualization, commission assumptions or payment claims are introduced.

## Access, retention and concurrency

Readers: system administrator, project manager, sales operations, legal,
collections, finance, approver/CFO, executive viewer and auditor.
Writers: system administrator, project manager and sales operations.
Everyone except system administrators needs active whole-project access.
Selected-phase memberships and assigned-only sales advisors do not gain a
portfolio-wide client view. Source queries and register joins narrow in SQL.

Create/update/delete serialize under the project lock. Edits and deletions
require the expected version; edits and deletions record a reason and full
before/after audit. Delete appears on the full-page instruction and removes
it from registers while retaining its data and references. It works for drafts.
No source record is cascaded or physically erased.

Migration `0064_leasing` follows `0063_plan_sources`. It adds one table,
same-project composite foreign keys, lifecycle constraints and a partial
unique index. Empty downgrade is supported; any retained instruction blocks
downgrade. The table is excluded from legacy intake. No backfill is needed.

## Validation and first-version scope

`tests/modules/test_leasing.py` covers source prefill, independent unit status,
validation, duplicate open instructions, versions, permissions, scope, filters,
retained draft/closed deletion and migration roundtrip/drift.
Frontend tests cover owner prefill, exact amounts, error states and save failures.

This first version records instructions and tenancy terms. Viewing appointments,
document uploads, tenant identity files, commissions and a rental payments ledger
are future product changes, not hidden calculations or fabricated records.
