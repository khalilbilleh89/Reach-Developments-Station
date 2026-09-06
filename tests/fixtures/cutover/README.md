# The synthetic cutover bundle

Nine files, one fictional project, obviously fictional people. This is what a
canonical intake bundle looks like when it is correct — the shape the importer
will be tested against, and the shape an operator preparing a real batch has to
match.

**Nothing here came from anybody's system.** Every name is a placeholder, every
email address ends in `.invalid` (reserved by RFC 2606 and unresolvable by
design), every telephone number sits in the `555-01xx` range reserved for
fiction, and every identity document reads `ID-SAMPLE-nnnn`. That is asserted by
`tests/modules/test_cutover_fixture.py`, not merely intended: a fixture that
drifted into containing something real-looking would be a fixture somebody
eventually mistakes for real, and this data is committed to a public history.

**A run against this bundle is not a trial migration.** It exercises the
machinery on data whose answers are known in advance. A trial migration is the
same machinery pointed at the client's real extract, and it is blocked, because
the extract does not exist yet.

The bundle covers groups A and B of `docs/CANONICAL_INTAKE_CONTRACT.md`. Groups
C and D — sale contracts, their parties, the signed payment schedule and
receipts — are absent because they are blocked on the B+ legacy commercial
provenance seam, and a fixture for a file nobody may import yet would be a
statement that the design is settled.

There is no `projects.csv`. The project is a prerequisite, resolved by the
batch and never created by it; `GALINI-BLU` is the fictional project this
repository's own test suite already sets up, reused here so the bundle can be
preflighted against a real target without inventing a second one.
