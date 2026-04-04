"""add strategy execution triggers table

Revision ID: 0063
Revises: 0062
Create Date: 2026-04-04

PR-V7-09 — Approved Strategy Execution Trigger & Handoff Records

Changes
-------
strategy_execution_triggers
  New table.  Persists the formal execution handoff record for an approved
  project strategy recommendation.

  Columns:
    id                          VARCHAR(36)     NOT NULL  PRIMARY KEY
    project_id                  VARCHAR(36)     NOT NULL  FK → projects.id CASCADE
    approval_id                 VARCHAR(36)     NULL      FK → strategy_approvals.id SET NULL
    strategy_snapshot           JSON            NULL
    execution_package_snapshot  JSON            NULL
    status                      VARCHAR(50)     NOT NULL  DEFAULT 'triggered'
    triggered_by_user_id        VARCHAR(36)     NOT NULL
    triggered_at                TIMESTAMPTZ     NOT NULL
    completed_at                TIMESTAMPTZ     NULL
    cancelled_at                TIMESTAMPTZ     NULL
    cancellation_reason         TEXT            NULL
    created_at                  TIMESTAMPTZ     NOT NULL
    updated_at                  TIMESTAMPTZ     NOT NULL

  Indexes:
    ix_strategy_execution_triggers_project_id
    ix_strategy_execution_triggers_approval_id

  Constraints:
    fk_strategy_execution_triggers_project_id   → projects.id ON DELETE CASCADE
    fk_strategy_execution_triggers_approval_id  → strategy_approvals.id ON DELETE SET NULL

  Status lifecycle: triggered → in_progress → completed (terminal)
                    triggered → cancelled (terminal)
                    in_progress → cancelled (terminal)

  At most one active (triggered or in_progress) trigger per project is
  enforced by the service layer.  The application translates ConflictError
  into HTTP 409.

No destructive changes.  Existing tables are unmodified.

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
    op.create_table(
        "strategy_execution_triggers",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("approval_id", sa.String(36), nullable=True),
        sa.Column("strategy_snapshot", sa.JSON(), nullable=True),
        sa.Column("execution_package_snapshot", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="triggered",
        ),
        sa.Column("triggered_by_user_id", sa.String(36), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["strategy_approvals.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_strategy_execution_triggers_project_id",
        "strategy_execution_triggers",
        ["project_id"],
    )
    op.create_index(
        "ix_strategy_execution_triggers_approval_id",
        "strategy_execution_triggers",
        ["approval_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_execution_triggers_approval_id",
        table_name="strategy_execution_triggers",
    )
    op.drop_index(
        "ix_strategy_execution_triggers_project_id",
        table_name="strategy_execution_triggers",
    )
    op.drop_table("strategy_execution_triggers")
