"""add feasibility run lineage fields

Revision ID: 0054
Revises: 0053
Create Date: 2026-03-25

PR-CONCEPT-063 — Seed Feasibility Run from Concept Option

Changes
-------
feasibility_runs
  source_concept_option_id  VARCHAR(36), nullable — ID of the concept option
                             that seeded this run, when seed_source_type='concept_option'
  seed_source_type          VARCHAR(50), nullable — how the run was created
                             ('concept_option' | 'manual' | null for legacy runs)

These columns establish a deterministic lineage trail between concept options
and the feasibility runs they seed.  A NULL seed_source_type indicates a run
created before this migration (legacy) or created manually without seeding.

No destructive changes. Existing rows remain valid with both columns NULL.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feasibility_runs",
        sa.Column(
            "source_concept_option_id",
            sa.String(36),
            nullable=True,
        ),
    )
    op.add_column(
        "feasibility_runs",
        sa.Column(
            "seed_source_type",
            sa.String(50),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_feasibility_runs_source_concept_option_id",
        "feasibility_runs",
        ["source_concept_option_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_feasibility_runs_source_concept_option_id",
        table_name="feasibility_runs",
    )
    op.drop_column("feasibility_runs", "seed_source_type")
    op.drop_column("feasibility_runs", "source_concept_option_id")
