"""add construction schedule tables

Revision ID: 0046
Revises: 0045
Create Date: 2026-03-23

PR-CONSTR-040 — Construction Schedule Engine

Changes
-------
construction_milestones
  duration_days               INTEGER        NULL  planned duration of milestone in calendar days

construction_milestone_dependencies
  id                          VARCHAR(36)    PK (UUID)
  predecessor_id              VARCHAR(36)    FK → construction_milestones.id (CASCADE on delete)
  successor_id                VARCHAR(36)    FK → construction_milestones.id (CASCADE on delete)
  lag_days                    INTEGER        0 = Finish-to-Start with no lag
  created_at                  TIMESTAMP
  updated_at                  TIMESTAMP

Indexes / Constraints
---------------------
  construction_milestone_dependencies(predecessor_id)
  construction_milestone_dependencies(successor_id)
  UNIQUE construction_milestone_dependencies(predecessor_id, successor_id)

No destructive changes.  Existing milestone rows remain valid; duration_days
defaults to NULL until explicitly set.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Add duration_days to construction_milestones
    # ------------------------------------------------------------------
    op.add_column(
        "construction_milestones",
        sa.Column("duration_days", sa.Integer, nullable=True),
    )

    # ------------------------------------------------------------------
    # construction_milestone_dependencies
    # ------------------------------------------------------------------
    op.create_table(
        "construction_milestone_dependencies",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "predecessor_id",
            sa.String(36),
            sa.ForeignKey("construction_milestones.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "successor_id",
            sa.String(36),
            sa.ForeignKey("construction_milestones.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "lag_days",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
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
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "predecessor_id",
            "successor_id",
            name="uq_milestone_dependency",
        ),
    )


def downgrade() -> None:
    op.drop_table("construction_milestone_dependencies")
    op.drop_column("construction_milestones", "duration_days")
