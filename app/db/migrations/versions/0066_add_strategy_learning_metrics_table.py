"""add strategy learning metrics table

Revision ID: 0066
Revises: 0065
Create Date: 2026-04-05

PR-V7-11 — Strategy Learning & Confidence Recalibration Engine

Changes
-------
strategy_learning_metrics
  New table.  Persists aggregated, deterministically derived learning signals
  for a (project_id, strategy_type) pair.  Rows are upserted — never appended
  — so each row always represents the current best estimate.

  Columns:
    id                         VARCHAR(36)    NOT NULL  PRIMARY KEY
    project_id                 VARCHAR(36)    NOT NULL  FK → projects.id CASCADE
    strategy_type              VARCHAR(100)   NOT NULL
    sample_size                INTEGER        NOT NULL  DEFAULT 0
    match_rate                 FLOAT          NOT NULL  DEFAULT 0.0
    partial_rate               FLOAT          NOT NULL  DEFAULT 0.0
    divergence_rate            FLOAT          NOT NULL  DEFAULT 0.0
    confidence_score           FLOAT          NOT NULL  DEFAULT 0.0
    pricing_accuracy_score     FLOAT          NULL
    phasing_accuracy_score     FLOAT          NULL
    overall_strategy_accuracy  FLOAT          NOT NULL  DEFAULT 0.0
    trend_direction            VARCHAR(50)    NOT NULL  DEFAULT 'insufficient_data'
    last_updated               TIMESTAMPTZ    NOT NULL
    created_at                 TIMESTAMPTZ    NOT NULL
    updated_at                 TIMESTAMPTZ    NOT NULL

  Indexes:
    ix_strategy_learning_metrics_project_id
    uq_strategy_learning_metrics_project_strategy_type  (unique per project + strategy_type)

  Constraints:
    fk_strategy_learning_metrics_project_id  → projects.id ON DELETE CASCADE

No destructive changes.  Existing tables are unmodified.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0066"
down_revision: Union[str, None] = "0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_learning_metrics",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("strategy_type", sa.String(100), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("partial_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("divergence_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pricing_accuracy_score", sa.Float(), nullable=True),
        sa.Column("phasing_accuracy_score", sa.Float(), nullable=True),
        sa.Column(
            "overall_strategy_accuracy",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "trend_direction",
            sa.String(50),
            nullable=False,
            server_default="insufficient_data",
        ),
        sa.Column(
            "last_updated",
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
            name="fk_strategy_learning_metrics_project_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_strategy_learning_metrics_project_id",
        "strategy_learning_metrics",
        ["project_id"],
    )
    # Unique constraint: one row per (project, strategy_type).
    op.create_index(
        "uq_strategy_learning_metrics_project_strategy_type",
        "strategy_learning_metrics",
        ["project_id", "strategy_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_strategy_learning_metrics_project_strategy_type",
        table_name="strategy_learning_metrics",
    )
    op.drop_index(
        "ix_strategy_learning_metrics_project_id",
        table_name="strategy_learning_metrics",
    )
    op.drop_table("strategy_learning_metrics")
