"""add tender baseline governance fields

Revision ID: 0060
Revises: 0059
Create Date: 2026-03-28

PR-V6-13 — Approved Tender Baseline Governance

Changes
-------
construction_cost_comparison_sets
  Three additive nullable/defaulted columns that record approved-baseline state
  for each comparison set.

  is_approved_baseline  BOOLEAN         NOT NULL DEFAULT FALSE
  approved_at           TIMESTAMPTZ     NULL
  approved_by_user_id   VARCHAR(36)     NULL

  New index:
    ix_construction_cost_comparison_sets_is_approved_baseline

At most one row per project_id should have is_approved_baseline = TRUE.
This invariant is enforced in the service layer, not via a DB constraint, so
that existing rows default safely to FALSE.

Migration Required: Yes
Backfill Required: No  (all existing rows default to is_approved_baseline=FALSE)
Destructive Change: No
Rollback Safe: Yes  (drop columns / index on downgrade)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "construction_cost_comparison_sets",
        sa.Column(
            "is_approved_baseline",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "construction_cost_comparison_sets",
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "construction_cost_comparison_sets",
        sa.Column(
            "approved_by_user_id",
            sa.String(36),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_construction_cost_comparison_sets_is_approved_baseline",
        "construction_cost_comparison_sets",
        ["is_approved_baseline"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_cost_comparison_sets_is_approved_baseline",
        table_name="construction_cost_comparison_sets",
    )
    op.drop_column("construction_cost_comparison_sets", "approved_by_user_id")
    op.drop_column("construction_cost_comparison_sets", "approved_at")
    op.drop_column("construction_cost_comparison_sets", "is_approved_baseline")
