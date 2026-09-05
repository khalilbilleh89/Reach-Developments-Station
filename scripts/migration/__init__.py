"""One-time cutover tooling: legacy data into Reach Developments Station.

This package is operational, not a product surface. It exists to take an
approved extract of a real development's history, prove it before writing
anything, apply it in one transaction, and then reconcile every material
operational and financial truth against the system it came from. When the
cutover is done it stops being used; it is not an ETL platform and must never
grow into one.

**"Migration" here is not an Alembic migration.** The repository already uses
that word for schema revisions under ``app/db/migrations/``, and the ten
``tests/modules/test_migration_*.py`` files are their tests, one per domain.
Nothing in this package changes a schema. The tests for this package are named
``test_cutover_*`` and belong to the ``cutover`` domain in the fast selector,
because a ``migration`` domain would have claimed those ten files away from the
domains that own them.

Two layers, kept apart on purpose:

    the client's actual workbook or export
        ↓   a thin deterministic adapter, written only once the real source
        │   exists and its semantics are documented
    the canonical intake bundle
        ↓   everything in this package
    validate → apply → reconcile

The canonical bundle is derived from what this application's own services
require to reconstruct a project honestly. The adapter is derived from the
client's source and nothing else. Keeping them apart is what lets the machinery
be built and proved before anybody has seen the workbook, and it is why nothing
here invents a worksheet name, a column, a status vocabulary or a currency.

What this package will not do, in any version:

- infer a source column's business meaning
- turn a missing historical value into zero, today, or "unknown"
- fabricate an approver, a preparer or an approval date so a row will insert
- write anything on import unless the operator asked for ``apply`` explicitly
- recompute a figure the application already derives
"""

from __future__ import annotations

#: Bumped when the canonical intake contract changes shape in a way that makes
#: a previously valid bundle invalid, or changes what a column means. Recorded
#: in every manifest and every report, because "which contract was this batch
#: validated against?" is a question an auditor will ask about a batch applied
#: months earlier.
CONTRACT_VERSION = "1"

__all__ = ["CONTRACT_VERSION"]
