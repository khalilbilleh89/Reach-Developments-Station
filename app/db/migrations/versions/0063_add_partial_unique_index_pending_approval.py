"""add partial unique index for one pending approval per project

Revision ID: 0063
Revises: 0062
Create Date: 2026-04-04

PR-V7-08A — Strategy Approval Hardening

Changes
-------
strategy_approvals
  Adds a partial unique index that enforces the single-pending-approval
  invariant at the database level.

  ix_strategy_approvals_one_pending_per_project
    UNIQUE on (project_id) WHERE status = 'pending'

  This prevents concurrent POST requests from both passing the application-
  layer check and both inserting a pending row.  The service layer still
  performs an optimistic check first (for a clean 409 response), and the
  repository translates any IntegrityError that slips through concurrent
  races into ConflictError.

  The partial index is a PostgreSQL feature.  On SQLite (used in tests) the
  postgresql_where clause is ignored, so the behaviour on SQLite is a plain
  index on project_id and the service-layer guard alone prevents duplicates.

No destructive changes.  Existing rows are unaffected.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: Union[str, None] = "0062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_strategy_approvals_one_pending_per_project",
        "strategy_approvals",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_approvals_one_pending_per_project",
        table_name="strategy_approvals",
    )
