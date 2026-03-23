"""add milestone progress fields

Revision ID: 0047
Revises: 0046
Create Date: 2026-03-23

PR-CONSTR-041 — Construction Progress Tracking & Schedule Variance

Changes
-------
construction_milestones
  actual_start_day          INTEGER        NULL  actual start day relative to project day 0
  actual_finish_day         INTEGER        NULL  actual finish day relative to project day 0
  progress_percent          FLOAT          NULL  0.0–100.0 completion percentage
  last_progress_update_at   TIMESTAMP      NULL  UTC timestamp of the most recent progress update

No destructive changes.  Existing milestone rows remain valid; all new
columns default to NULL until explicitly set via the progress endpoint.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "construction_milestones",
        sa.Column("actual_start_day", sa.Integer, nullable=True),
    )
    op.add_column(
        "construction_milestones",
        sa.Column("actual_finish_day", sa.Integer, nullable=True),
    )
    op.add_column(
        "construction_milestones",
        sa.Column("progress_percent", sa.Float, nullable=True),
    )
    op.add_column(
        "construction_milestones",
        sa.Column("last_progress_update_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("construction_milestones", "last_progress_update_at")
    op.drop_column("construction_milestones", "progress_percent")
    op.drop_column("construction_milestones", "actual_finish_day")
    op.drop_column("construction_milestones", "actual_start_day")
