"""MVP 1.0 baseline.

This revision intentionally contains no DDL. Its only job is to declare where
MVP 1.0 starts, so that every future migration has a common, unambiguous root
that is unrelated to the demolished V1 history.

The only table PostgreSQL should hold after upgrading to this revision is
Alembic's own ``alembic_version`` bookkeeping table.

Business schema begins in the roadmap PRs listed in docs/MVP_ROADMAP.md:
PR-MVP-01 governance, PR-MVP-02 project/land/permits, and onwards.

Revision ID: 0000_mvp_baseline
Revises:
Create Date: 2026-08-25

"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0000_mvp_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish the MVP 1.0 migration root. No domain DDL by design."""


def downgrade() -> None:
    """Return to an empty database. Nothing to undo."""
