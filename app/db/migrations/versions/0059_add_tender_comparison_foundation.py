"""add tender comparison foundation

Revision ID: 0059
Revises: 0058
Create Date: 2026-03-28

PR-V6-11 — Tender Comparison & Cost Variance Foundation

Changes
-------
construction_cost_comparison_sets
  New table for project-owned comparison sets grouping a baseline-to-comparison
  cost review event.

  id                  VARCHAR(36)     PK (UUID)
  project_id          VARCHAR(36)     FK → projects.id CASCADE DELETE
  title               VARCHAR(255)    NOT NULL
  comparison_stage    VARCHAR(50)     NOT NULL
  baseline_label      VARCHAR(255)    NOT NULL DEFAULT 'Baseline'
  comparison_label    VARCHAR(255)    NOT NULL DEFAULT 'Tender'
  notes               TEXT            NULL
  is_active           BOOLEAN         NOT NULL DEFAULT TRUE
  created_at          TIMESTAMPTZ     NOT NULL
  updated_at          TIMESTAMPTZ     NOT NULL

construction_cost_comparison_lines
  New table for individual cost category comparison lines within a set.

  id                  VARCHAR(36)     PK (UUID)
  comparison_set_id   VARCHAR(36)     FK → construction_cost_comparison_sets.id CASCADE DELETE
  cost_category       VARCHAR(50)     NOT NULL
  baseline_amount     NUMERIC(20, 2)  NOT NULL DEFAULT 0.00
  comparison_amount   NUMERIC(20, 2)  NOT NULL DEFAULT 0.00
  variance_amount     NUMERIC(20, 2)  NOT NULL DEFAULT 0.00
  variance_pct        NUMERIC(10, 4)  NULL
  variance_reason     VARCHAR(50)     NOT NULL
  notes               TEXT            NULL
  created_at          TIMESTAMPTZ     NOT NULL
  updated_at          TIMESTAMPTZ     NOT NULL

Indexes
  ix_construction_cost_comparison_sets_project_id
  ix_construction_cost_comparison_sets_comparison_stage
  ix_construction_cost_comparison_sets_is_active
  ix_construction_cost_comparison_lines_comparison_set_id
  ix_construction_cost_comparison_lines_cost_category

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Comparison Sets table ─────────────────────────────────────────────────
    op.create_table(
        "construction_cost_comparison_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("comparison_stage", sa.String(50), nullable=False),
        sa.Column(
            "baseline_label",
            sa.String(255),
            nullable=False,
            server_default="Baseline",
        ),
        sa.Column(
            "comparison_label",
            sa.String(255),
            nullable=False,
            server_default="Tender",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
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
    )

    op.create_index(
        "ix_construction_cost_comparison_sets_project_id",
        "construction_cost_comparison_sets",
        ["project_id"],
    )
    op.create_index(
        "ix_construction_cost_comparison_sets_comparison_stage",
        "construction_cost_comparison_sets",
        ["comparison_stage"],
    )
    op.create_index(
        "ix_construction_cost_comparison_sets_is_active",
        "construction_cost_comparison_sets",
        ["is_active"],
    )

    # ── Comparison Lines table ────────────────────────────────────────────────
    op.create_table(
        "construction_cost_comparison_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "comparison_set_id",
            sa.String(36),
            sa.ForeignKey(
                "construction_cost_comparison_sets.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("cost_category", sa.String(50), nullable=False),
        sa.Column(
            "baseline_amount",
            sa.Numeric(20, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "comparison_amount",
            sa.Numeric(20, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "variance_amount",
            sa.Numeric(20, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("variance_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("variance_reason", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
    )

    op.create_index(
        "ix_construction_cost_comparison_lines_comparison_set_id",
        "construction_cost_comparison_lines",
        ["comparison_set_id"],
    )
    op.create_index(
        "ix_construction_cost_comparison_lines_cost_category",
        "construction_cost_comparison_lines",
        ["cost_category"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_cost_comparison_lines_cost_category",
        table_name="construction_cost_comparison_lines",
    )
    op.drop_index(
        "ix_construction_cost_comparison_lines_comparison_set_id",
        table_name="construction_cost_comparison_lines",
    )
    op.drop_table("construction_cost_comparison_lines")

    op.drop_index(
        "ix_construction_cost_comparison_sets_is_active",
        table_name="construction_cost_comparison_sets",
    )
    op.drop_index(
        "ix_construction_cost_comparison_sets_comparison_stage",
        table_name="construction_cost_comparison_sets",
    )
    op.drop_index(
        "ix_construction_cost_comparison_sets_project_id",
        table_name="construction_cost_comparison_sets",
    )
    op.drop_table("construction_cost_comparison_sets")
