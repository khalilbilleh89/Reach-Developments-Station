"""add milestone cost fields

Revision ID: 0048
Revises: 0047
Create Date: 2026-03-23

PR-CONSTR-042 — Construction Cost Tracking & Budget Variance

Changes
-------
construction_milestones
  planned_cost            NUMERIC(18,2)  NULL  budgeted cost for the milestone
  actual_cost             NUMERIC(18,2)  NULL  actual recorded cost for the milestone
  cost_last_updated_at    TIMESTAMP      NULL  UTC timestamp of the most recent cost update

No destructive changes.  Existing milestone rows remain valid; all new
columns default to NULL until explicitly set via the cost endpoint.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "construction_milestones",
        sa.Column("planned_cost", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "construction_milestones",
        sa.Column("actual_cost", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "construction_milestones",
        sa.Column("cost_last_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("construction_milestones", "cost_last_updated_at")
    op.drop_column("construction_milestones", "actual_cost")
    op.drop_column("construction_milestones", "planned_cost")
