# Go-live

**Status: NO-GO.** Not as a caution — as a fact about what does not exist.

A cutover moves a developer's live commercial history into Reach: units, buyers,
signed contracts, the money already collected against them. Getting it wrong is
not a bug report. It is a buyer whose payments have vanished, a unit sold twice,
or a revenue figure nobody can reconcile against the bank.

This directory is the operational half of that: what has to be true before a
batch runs, how to run one, and what each refusal means at two in the morning
when the person reading it did not write any of this.

## What is blocked, and on what

| | |
|---|---|
| **Source workbook** | **MISSING.** Nobody on this side has seen it. |
| **Source-specific mapping** | **BLOCKED** on the workbook. |
| **Trial migration** | **BLOCKED** on the mapping. |
| **The seven reconciliations' expected values** | **BLOCKED**, individually. Every one is source-derived. |
| **`apply`** | **DOES NOT EXIST.** The CLI accepts `preflight` and nothing else. |
| **Legacy sale contracts** | **BLOCKED** on the B+ legacy commercial provenance seam. |

A run against the synthetic fixture is **not a trial migration**. It exercises
the machinery on data whose answers are known in advance. A trial migration is
the same machinery pointed at the client's real extract.

## What exists and works today

* The **canonical intake contract** — [`../CANONICAL_INTAKE_CONTRACT.md`](../CANONICAL_INTAKE_CONTRACT.md)
  — deciding, for all 91 tables, what a batch may write.
* A **sealed manifest**: every bundle file hashed at validation, re-verified
  before anything is applied. One changed byte refuses.
* **Batch identity** over `audit_events.correlation_id`: a batch applies once,
  and a batch that never landed can be retried.
* **Source-side and target-side preflight**, with a result vocabulary that
  refuses to call half a check a pass.
* **Reject reports** a spreadsheet will not execute, and **log lines** that
  cannot carry a name, an address or a document number.
* A **reconciliation orchestrator** that runs the checks the application already
  owns and computes nothing itself.

## The gate

Go-live is a decision somebody signs, not a state the tooling reports. Nothing
in this repository will ever print "ready". What the tooling can do is refuse,
and every refusal below is a gate that has not been met.

1. The source workbook exists and has been inspected.
2. The source mapping is written, reviewed, and maps onto the canonical intake
   contract without inventing a column, a status or a currency.
3. A trial migration has run against a copy of production.
4. All seven reconciliations pass on that trial, each with an expected value
   derived from the source rather than from the migration.
5. UAT has been signed by somebody who will use the system.
6. The rollback procedure has been rehearsed, not merely written.

**None of these is met.** Items 1 and 2 block 3, which blocks 4 and 5.
