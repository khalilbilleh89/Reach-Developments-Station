"""add strategy approvals table

Revision ID: 0061
Revises: 0060
Create Date: 2026-04-04

PR-V7-08 — Strategy Review & Approval Workflow

Changes
-------
strategy_approvals
  New table.  Persists the governance approval state for a project strategy
  recommendation.

  Columns:
    id                          VARCHAR(36)     NOT NULL  PRIMARY KEY
    project_id                  VARCHAR(36)     NOT NULL  FK → projects.id CASCADE
    strategy_snapshot           JSON            NULL
    execution_package_snapshot  JSON            NULL
    status                      VARCHAR(50)     NOT NULL  DEFAULT 'pending'
    approved_by_user_id         VARCHAR(36)     NULL
    approved_at                 TIMESTAMPTZ     NULL
    rejection_reason            TEXT            NULL
    created_at                  TIMESTAMPTZ     NOT NULL
    updated_at                  TIMESTAMPTZ     NOT NULL

  Indexes:
    ix_strategy_approvals_project_id

  Constraints:
    fk_strategy_approvals_project_id → projects.id ON DELETE CASCADE

  At most one pending row per project_id is enforced by a partial unique
  index added in migration 0062.  The application layer translates any
  IntegrityError from a concurrent race into ConflictError for a clean
  HTTP 409 response.

No destructive changes.  Existing tables are unmodified.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0061"
down_revision: Union[str, None] = "0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_approvals",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("strategy_snapshot", sa.JSON(), nullable=True),
        sa.Column("execution_package_snapshot", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("approved_by_user_id", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_strategy_approvals_project_id",
        "strategy_approvals",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_approvals_project_id",
        table_name="strategy_approvals",
    )
    op.drop_table("strategy_approvals")
