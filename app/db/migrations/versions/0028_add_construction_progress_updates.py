"""add construction progress updates table

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-18

PR-C3 — Construction Progress Tracking

Adds the construction_progress_updates table which records periodic
site-progress entries linked to a ConstructionMilestone.  Each row
captures percent complete, an optional status note, the reporter name,
and the timestamp of the report.

This migration is fully additive and non-breaking — it does not alter
any existing table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "construction_progress_updates",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "milestone_id",
            sa.String(36),
            sa.ForeignKey("construction_milestones.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("progress_percent", sa.Integer, nullable=False),
        sa.Column("status_note", sa.Text, nullable=True),
        sa.Column("reported_by", sa.String(255), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_construction_progress_updates_milestone_id",
        "construction_progress_updates",
        ["milestone_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_progress_updates_milestone_id",
        table_name="construction_progress_updates",
    )
    op.drop_table("construction_progress_updates")
