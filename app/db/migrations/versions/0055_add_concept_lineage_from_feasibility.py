"""add concept lineage from feasibility

Revision ID: 0055
Revises: 0054
Create Date: 2026-03-25

PR-CONCEPT-064 — Seed Concept Option from Feasibility Run

Changes
-------
concept_options
  source_feasibility_run_id  VARCHAR(36), nullable — ID of the feasibility run
                              that seeded this concept option, when
                              seed_source_type='feasibility_run'

This column establishes the reverse lineage trail from feasibility runs back
into concept options, completing the bidirectional design-finance loop:

    Concept → Feasibility → Concept

A NULL value indicates a concept option created without reverse-seeding
(the original top-down path) and is valid for all legacy rows.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: Union[str, None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "concept_options",
        sa.Column(
            "source_feasibility_run_id",
            sa.String(36),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_concept_options_source_feasibility_run_id",
        "concept_options",
        ["source_feasibility_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_concept_options_source_feasibility_run_id",
        table_name="concept_options",
    )
    op.drop_column("concept_options", "source_feasibility_run_id")
