"""add strategy execution outcomes table

Revision ID: 0065
Revises: 0064
Create Date: 2026-04-05

PR-V7-10 — Execution Outcome Capture & Feedback Loop Closure

Changes
-------
strategy_execution_outcomes
  New table.  Persists the realized execution outcome for a triggered
  project strategy.  Outcome records are immutable snapshots; re-recording
  creates a new 'recorded' row and marks prior rows for the same trigger
  as 'superseded' so the full outcome history is retained.

  Columns:
    id                          VARCHAR(36)   NOT NULL  PRIMARY KEY
    project_id                  VARCHAR(36)   NOT NULL  FK → projects.id CASCADE
    execution_trigger_id        VARCHAR(36)   NULL      FK → strategy_execution_triggers.id SET NULL
    approval_id                 VARCHAR(36)   NULL      FK → strategy_approvals.id SET NULL
    status                      VARCHAR(50)   NOT NULL  DEFAULT 'recorded'
    actual_price_adjustment_pct FLOAT         NULL
    actual_phase_delay_months   FLOAT         NULL
    actual_release_strategy     VARCHAR(100)  NULL
    execution_summary           TEXT          NULL
    outcome_result              VARCHAR(50)   NOT NULL
    outcome_notes               TEXT          NULL
    recorded_by_user_id         VARCHAR(36)   NOT NULL
    recorded_at                 TIMESTAMPTZ   NOT NULL
    created_at                  TIMESTAMPTZ   NOT NULL
    updated_at                  TIMESTAMPTZ   NOT NULL

  Indexes:
    ix_strategy_execution_outcomes_project_id
    ix_strategy_execution_outcomes_execution_trigger_id
    ix_strategy_execution_outcomes_approval_id

  Constraints:
    fk_strategy_execution_outcomes_project_id         → projects.id ON DELETE CASCADE
    fk_strategy_execution_outcomes_execution_trigger_id → strategy_execution_triggers.id ON DELETE SET NULL
    fk_strategy_execution_outcomes_approval_id        → strategy_approvals.id ON DELETE SET NULL

  Status lifecycle:
    recorded → superseded  (when a newer outcome is recorded for the same trigger)

  Outcome result values:
    matched_strategy | partially_matched | diverged | cancelled_execution | insufficient_data

No destructive changes.  Existing tables are unmodified.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0065"
down_revision: Union[str, None] = "0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_execution_outcomes",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("execution_trigger_id", sa.String(36), nullable=True),
        sa.Column("approval_id", sa.String(36), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="recorded",
        ),
        sa.Column(
            "actual_price_adjustment_pct",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "actual_phase_delay_months",
            sa.Float(),
            nullable=True,
        ),
        sa.Column("actual_release_strategy", sa.String(100), nullable=True),
        sa.Column("execution_summary", sa.Text(), nullable=True),
        sa.Column("outcome_result", sa.String(50), nullable=False),
        sa.Column("outcome_notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", sa.String(36), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
            ["execution_trigger_id"],
            ["strategy_execution_triggers.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["strategy_approvals.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_strategy_execution_outcomes_project_id",
        "strategy_execution_outcomes",
        ["project_id"],
    )
    op.create_index(
        "ix_strategy_execution_outcomes_execution_trigger_id",
        "strategy_execution_outcomes",
        ["execution_trigger_id"],
    )
    op.create_index(
        "ix_strategy_execution_outcomes_approval_id",
        "strategy_execution_outcomes",
        ["approval_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_execution_outcomes_approval_id",
        table_name="strategy_execution_outcomes",
    )
    op.drop_index(
        "ix_strategy_execution_outcomes_execution_trigger_id",
        table_name="strategy_execution_outcomes",
    )
    op.drop_index(
        "ix_strategy_execution_outcomes_project_id",
        table_name="strategy_execution_outcomes",
    )
    op.drop_table("strategy_execution_outcomes")
